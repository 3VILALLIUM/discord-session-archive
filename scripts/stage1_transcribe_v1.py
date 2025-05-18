#!/usr/bin/env python3
"""
stage1_transcribe_v1.py
----------------------
A campaign-agnostic, local Whisper (faster-whisper) audio chunker and transcriber.

- Uses Tkinter to let user choose the raw_audio folder
- Detects campaign/session names from folder structure
- Chunks and transcribes all supported audio files in the chosen folder
- Outputs per-chunk JSON and combined JSON to matching dotmm_transcripts/ folder under the campaign root
- Fully compatible with LoreBot pipeline naming conventions

Save in: C:/Users/Brigh/LoreBot/scripts/
"""

import argparse
import concurrent.futures as cf
import io
import json
import logging
import os
import sys
import tempfile
import time
import threading
import queue
import shutil
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterator, List, Dict, Any, Tuple

from dotenv import load_dotenv
from faster_whisper import WhisperModel
import tenacity

try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None

__version__ = "1.2.0"

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
SUPPORTED = {".aac", ".wav", ".m4a", ".mp3", ".flac"}
CHUNK_SEC = 2 * 60
OVERLAP_SEC = 5.0
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL_PATH", "large-v3")

# --------- Max workers setup ---------------------
def get_max_workers(default=4):
    env_val = os.environ.get("LOREBOT_MAX_WORKERS")
    if env_val:
        try:
            return int(env_val)
        except Exception:
            pass
    return default

# --------- ffmpeg tool check ---------
def check_ffmpeg_tools():
    missing = []
    for tool in ["ffmpeg", "ffprobe"]:
        if not shutil.which(tool):
            missing.append(tool)
    if missing:
        msg = f"Required tool(s) not found on PATH: {', '.join(missing)}.\nPlease install ffmpeg (https://ffmpeg.org/download.html) and ensure it is available in your system PATH."
        print(msg)
        logging.error(msg)
        sys.exit(1)

@dataclass(frozen=True)
class ChunkMeta:
    idx: int
    start_ms: int
    path: Path

# --------- Efficient ffmpeg chunking -------------
def ffmpeg_chunk(src_path: Path, start_ms: int, duration_ms: int, out_path: Path):
    import subprocess
    start_sec = start_ms / 1000
    duration_sec = duration_ms / 1000
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", str(start_sec),
        "-t", str(duration_sec),
        "-i", str(src_path),
        "-ar", "16000",
        "-ac", "1",
        "-vn", "-f", "flac",
        str(out_path)
    ]
    subprocess.run(cmd, check=True)

def iter_chunks_ffmpeg(src_path: Path, tmp_dir: Path, stem: str) -> Iterator[ChunkMeta]:
    import subprocess, json
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(src_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    duration_sec = float(json.loads(result.stdout)["format"]["duration"])
    length_ms = int(duration_sec * 1000)
    step = CHUNK_SEC * 1000
    offset = int(OVERLAP_SEC * 1000)
    pos = idx = 0
    while pos < length_ms:
        start = max(0, pos - offset)
        chunk_path = tmp_dir / f"{stem}_chunk_{idx:03}.flac"
        ffmpeg_chunk(src_path, start, CHUNK_SEC * 1000, chunk_path)
        yield ChunkMeta(idx=idx, start_ms=start, path=chunk_path)
        pos += step
        idx += 1

# --------- Campaign/session parsing with user guidance ---------
def parse_campaign_session(raw_audio_folder: Path) -> Tuple[str, str, Path, Path]:
    parts = list(raw_audio_folder.parts)
    if "campaigns" not in parts:
        print(f"Error: The selected folder {raw_audio_folder} is not under a 'campaigns' directory.")
        print("Please ensure you pick a folder within the campaigns directory structure.")
        sys.exit(1)
    try:
        idx = parts.index("campaigns")
        campaign_name = parts[idx + 1]
        session_name = raw_audio_folder.name.replace("_audio", "_transcript")
    except Exception:
        print("Error: Could not infer campaign/session names. Please check the folder structure.")
        sys.exit(1)
    transcript_root = ROOT / "campaigns" / campaign_name / "dotmm_transcripts"
    log_root = ROOT / "campaigns" / campaign_name / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    transcript_root.mkdir(parents=True, exist_ok=True)
    return campaign_name, session_name, transcript_root, log_root

# --------- Enhanced logger: add StreamHandler for console output -------------
def setup_logger(log_file, session_name):
    log_fmt = "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"
    session_logger = logging.getLogger(session_name)
    session_logger.handlers.clear()
    session_logger.propagate = False
    session_logger.setLevel(logging.INFO)
    fh = RotatingFileHandler(str(log_file), maxBytes=1_048_576, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter(log_fmt, date_fmt))
    session_logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(log_fmt, date_fmt))
    session_logger.addHandler(ch)
    return session_logger

# --------- Per-thread WhisperModel reuse & model cleanup -------------
thread_local = threading.local()
def get_thread_model(model_path: str, device: str):
    if not hasattr(thread_local, "model") or thread_local.model is None:
        try:
            thread_local.model = WhisperModel(
                model_path, device=device, compute_type="float16" if device == "cuda" else "int8"
            )
        except Exception as e:
            logging.error(
                f"Failed to load WhisperModel on device '{device}'. CUDA unavailable or invalid device. Error: {e}"
            )
            thread_local.model = None
            raise RuntimeError(
                f"Could not initialize WhisperModel on device '{device}'.\n"
                f"Error: {e}\n"
                f"Check your CUDA/GPU setup and try again."
            )
    return thread_local.model

@tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_fixed(2), reraise=True)
def whisper_chunk(flac: Path, model_path: str, device: str) -> Dict[str, Any]:
    try:
        model = get_thread_model(model_path, device)
        segments = []
        for segment in model.transcribe(str(flac), beam_size=5, vad_filter=True)[0]:
            segments.append({
                "start": float(segment.start),
                "end": float(segment.end),
                "text": segment.text,
                "confidence": float(getattr(segment, "avg_logprob", 1.0)),
            })
        return {"segments": segments}
    except Exception as e:
        thread_local.model = None
        raise e

# --- GUI picker for raw_audio folder ---
def pick_raw_audio_folder() -> Path:
    if not tk:
        sys.exit("Tkinter not available. Please run with Python that supports Tkinter.")
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Select a raw_audio folder (any campaign)", initialdir=str(ROOT / "campaigns"))
    if not folder:
        sys.exit("No folder selected. Aborting.")
    return Path(folder)

# --- transcribe a single audio file ---
def transcribe_file(transcript_root: Path, session_name: str, src: Path, logger: logging.Logger, model_path: str, device: str, summary_q=None) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{session_name}_chunks_") as tmp:
        tmp_dir = Path(tmp)
        out_dir = transcript_root / session_name / src.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Processing %s", src.name)
        metas = list(iter_chunks_ffmpeg(src, tmp_dir, src.stem))
        total_chunks = len(metas)
        all_segments: List[Dict[str, Any]] = []
        failed_chunks = []

        with cf.ThreadPoolExecutor(max_workers=get_max_workers()) as chunk_executor:
            future_to_meta = {chunk_executor.submit(whisper_chunk, m.path, model_path, device): m for m in metas}
            completed = 0
            for future in cf.as_completed(future_to_meta):
                meta = future_to_meta[future]
                try:
                    resp = future.result()
                    offset = meta.start_ms / 1000
                    seglist = [
                        {"start": s["start"] + offset, "end": s["end"] + offset, "text": s["text"]}
                        for s in resp["segments"]
                    ]
                    record = {"chunk_file": meta.path.name, "segments": seglist}
                    all_segments.extend(seglist)
                except Exception as e:
                    logger.error("Error on %s: %s", meta.path.name, e)
                    record = {"chunk_file": meta.path.name, "error": str(e)}
                    failed_chunks.append(meta.path.name)

                chunk_json = out_dir / f"{meta.path.stem}.json"
                chunk_json.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info("Saved %s", chunk_json.name)

                completed += 1
                logger.info("Progress: %d/%d chunks saved for %s", completed, total_chunks, src.name)

        combined = out_dir / f"{src.stem}.json"
        combined.write_text(
            json.dumps({"file": src.name, "segments": all_segments}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info("Saved combined transcript -> %s", combined.name)
        # Report failed chunks at the end (via summary queue for multi-file summary)
        if summary_q is not None:
            summary_q.put({"file": src.name, "failed_chunks": failed_chunks})

# --- main ---
def main() -> None:
    start = time.time()
    parser = argparse.ArgumentParser(description="Campaign-agnostic local whisper transcription for LoreBot.")
    parser.add_argument("--model-path", help="Optional: Path to whisper-large-v3 model or model name (default: large-v3)")
    parser.add_argument("--device", default="cuda", help="Device to run on (cuda or cpu; default: cuda)")
    parser.add_argument("--max-workers", type=int, help="Override for max worker threads (default: auto)")
    parser.add_argument("--max-files", type=int, help="Limit the number of audio files processed (for very large folders)")
    args = parser.parse_args()

    check_ffmpeg_tools()
    raw_audio_folder = pick_raw_audio_folder()
    if not raw_audio_folder.exists():
        sys.exit(f"Raw audio folder {raw_audio_folder} does not exist.")

    campaign_name, session_name, transcript_root, log_root = parse_campaign_session(raw_audio_folder)
    log_file = log_root / f"{session_name}.log"
    session_logger = setup_logger(log_file, session_name)

    model_path = args.model_path or WHISPER_MODEL_NAME
    device = args.device or "cuda"
    if args.max_workers:
        os.environ["LOREBOT_MAX_WORKERS"] = str(args.max_workers)

    audio_files = [p for p in raw_audio_folder.iterdir() if p.suffix.lower() in SUPPORTED]
    if args.max_files:
        audio_files = audio_files[:args.max_files]
    if not audio_files:
        sys.exit(f"No supported audio files in {raw_audio_folder}.")

    try:
        from tqdm import tqdm
        use_tqdm = True
    except ImportError:
        use_tqdm = False

    summary_q = queue.Queue()
    with cf.ThreadPoolExecutor(max_workers=get_max_workers()) as executor:
        if use_tqdm:
            pbar = tqdm(total=len(audio_files), desc="Files")
        futures = {executor.submit(transcribe_file, transcript_root, session_name, af, session_logger, model_path, device, summary_q): af for af in audio_files}
        for i, future in enumerate(cf.as_completed(futures)):
            src = futures[future]
            if err := future.exception():
                session_logger.error("Failed %s: %s", src.name, err)
            if use_tqdm:
                pbar.update(1)
        if use_tqdm:
            pbar.close()

    # Collect and report failed chunks summary
    failed_overall = []
    while not summary_q.empty():
        summary = summary_q.get()
        if summary["failed_chunks"]:
            session_logger.warning(f"{summary['file']}: Failed chunks: {summary['failed_chunks']}")
            failed_overall.extend([(summary["file"], c) for c in summary["failed_chunks"]])
    if failed_overall:
        print(f"WARNING: {len(failed_overall)} chunk(s) failed. See log for details.")
        session_logger.warning(f"WARNING: {len(failed_overall)} chunk(s) failed. See above for details.")
    else:
        print("All files and chunks processed successfully.")
        session_logger.info("All files and chunks processed successfully.")

    session_logger.info("Finished in %.2f s", time.time() - start)

if __name__ == "__main__":
    main()
