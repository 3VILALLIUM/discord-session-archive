#!/usr/bin/env python3
"""
Stage 1 – Dungeon of the Mad Mage transcription (v6.0)

Key upgrades
------------
✓ transcripts live under dotmm_transcripts/
✓ dynamic session-specific logging in logs/session_###.log
✓ retries only for OpenAI-side errors
✓ concurrent transcription of files
✓ chunks in temp directory (raw_audio untouched)
✓ type hints and explicit logging setup
✓ console handler uses UTF-8 with replacement to avoid encoding errors
✓ log format uses ASCII hyphens only
✓ CLI accepts both folder names and full paths for session

ChunkMeta now embeds the chunk file path directly when yielding.
"""

from __future__ import annotations
import argparse
import concurrent.futures as cf
import io
import json
import logging
import os
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterator, List, Dict, Any, cast

from dotenv import load_dotenv
from pydub import AudioSegment
from openai import OpenAI, OpenAIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None
    filedialog = None  # type: ignore

__version__ = "5.0.0"

# ── config ─────────────────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    sys.exit("ERROR: set OPENAI_API_KEY in .env or environment")
client = OpenAI(api_key=API_KEY)

ROOT = Path(__file__).resolve().parent.parent
RAW_AUDIO_ROOT = ROOT / "dotmm_sessions" / "raw_audio"
TRANSCRIPT_ROOT = ROOT / "dotmm_transcripts"
LOG_ROOT = ROOT / "logs"

# Use 2-minute chunks for lower latency and reduced retry cost
CHUNK_SEC = 2 * 60
OVERLAP_SEC = 5.0
SUPPORTED = {".aac", ".wav", ".m4a", ".mp3", ".flac"}
MAX_WORKERS = min(4, os.cpu_count() or 1)

# ── data class ───────────────────────────────────────────────
@dataclass(frozen=True)
class ChunkMeta:
    idx: int
    start_ms: int
    path: Path

# ── chunk helper ─────────────────────────────────────────────
def iter_chunks(audio: AudioSegment, tmp_dir: Path, stem: str) -> Iterator[ChunkMeta]:
    step = CHUNK_SEC * 1000
    offset = int(OVERLAP_SEC * 1000)
    pos = idx = 0
    while pos < len(audio):
        start = max(0, pos - offset)
        chunk_path = tmp_dir / f"{stem}_chunk_{idx:03}.flac"
        # Help static analyzers: ensure slice is treated as an AudioSegment
        segment = cast(AudioSegment, audio[start : start + CHUNK_SEC * 1000])
        segment.export(chunk_path, format="flac")
        yield ChunkMeta(idx=idx, start_ms=start, path=chunk_path)
        pos += step
        idx += 1

# ── whisper wrapper ─────────────────────────────────────────
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(OpenAIError),
    reraise=True
)
def whisper(flac: Path):
    with flac.open("rb") as f:
        return client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json"
        )

# ── transcribe a single audio file ───────────────────────────
def transcribe_file(session_name: str, src: Path, logger: logging.Logger) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{session_name}_chunks_") as tmp:
        tmp_dir = Path(tmp)
        out_dir = TRANSCRIPT_ROOT / session_name / src.stem
        out_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Processing %s", src.name)
        if not src.exists() or not src.is_file():
            logger.error("Skipping non-file or missing path: %s", src)
            return
        try:
            audio = AudioSegment.from_file(src)
        except Exception as e:
            logger.error("Failed to load %s: %s", src, e)
            return

        # split and prepare chunks
        metas = list(iter_chunks(audio, tmp_dir, src.stem))
        total_chunks = len(metas)
        all_segments: List[Dict[str, Any]] = []

        # transcribe chunks concurrently
        with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as chunk_executor:
            future_to_meta = {chunk_executor.submit(whisper, m.path): m for m in metas}
            completed = 0
            for future in cf.as_completed(future_to_meta):
                meta = future_to_meta[future]
                try:
                    resp = future.result()
                    offset = meta.start_ms / 1000
                    segments = getattr(resp, "segments", None) or []
                    seglist = [
                        {"start": s.start + offset, "end": s.end + offset, "text": s.text}
                        for s in segments
                    ]
                    record = {"chunk_file": meta.path.name, "segments": seglist}
                    all_segments.extend(seglist)
                except Exception as e:
                    logger.error("Error on %s: %s", meta.path.name, e)
                    record = {"chunk_file": meta.path.name, "error": str(e)}

                # write each chunk transcript
                chunk_json = out_dir / f"{meta.path.stem}.json"
                chunk_json.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info("Saved %s", chunk_json.name)

                completed += 1
                logger.info(
                    "Progress: %d/%d chunks saved for %s",
                    completed,
                    total_chunks,
                    src.name
                )

        # combined transcript
        combined = out_dir / f"{src.stem}.json"
        combined.write_text(
            json.dumps({"file": src.name, "segments": all_segments}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info("Saved combined transcript -> %s", combined.name)

# ── GUI folder picker ─────────────────────────────────────────
def pick_session_from_gui() -> Path:
    if not tk or filedialog is None:
        sys.exit("Tkinter not available and no --session provided.")
    root = tk.Tk()
    root.withdraw()
    # At this point, filedialog is not None due to guard above
    choice = filedialog.askdirectory(
        title="Select session audio folder",
        initialdir=str(RAW_AUDIO_ROOT)
    )
    if not choice:
        sys.exit("No folder selected.")
    return Path(choice)

# ── main entry ─────────────────────────────────────────────────
def main() -> None:
    start = time.time()

    parser = argparse.ArgumentParser(description="Transcribe DOTMM session audio.")
    parser.add_argument(
        "--session",
        help="Folder name under raw_audio or full path to session directory"
    )
    args = parser.parse_args()

    # ── locate session folder flexibly ───────────────────────
    if args.session:
        candidate = Path(args.session)
        if candidate.is_dir():
            session_dir = candidate
        elif (RAW_AUDIO_ROOT / args.session).is_dir():
            session_dir = RAW_AUDIO_ROOT / args.session
        else:
            sys.exit(
                f"Session folder {args.session} not found under {RAW_AUDIO_ROOT} or as absolute path."
            )
    else:
        session_dir = pick_session_from_gui()

    if not session_dir.exists():
        sys.exit(f"Session folder {session_dir} does not exist.")

    # ── normalize name: “…_audio” → “…_transcript” ──────────
    session_name = session_dir.name.replace("_audio", "_transcript")

    # ── prepare root dirs ────────────────────────────────────
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT_ROOT.mkdir(parents=True, exist_ok=True)

    # ── set up logging (uses session_name) ───────────────────
    log_file       = LOG_ROOT / f"{session_name}.log"
    log_fmt        = "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s"
    date_fmt       = "%Y-%m-%d %H:%M:%S"
    session_logger = logging.getLogger(session_name)
    session_logger.handlers.clear()
    session_logger.propagate = False
    session_logger.setLevel(logging.INFO)
    fh = RotatingFileHandler(str(log_file), maxBytes=1_048_576, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter(log_fmt, date_fmt))
    session_logger.addHandler(fh)
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ch = logging.StreamHandler(utf8_stdout)
    ch.setFormatter(logging.Formatter(log_fmt, date_fmt))
    session_logger.addHandler(ch)

    # process audio
    # Recursively discover supported audio FILES (ignore directories that happen to end with .aac, etc.)
    audio_files = [
        p for p in session_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED
    ]
    if not audio_files:
        sys.exit(f"No supported audio files in {session_dir}.")

    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(transcribe_file, session_name, af, session_logger): af for af in audio_files}
        for future in cf.as_completed(futures):
            src = futures[future]
            if err := future.exception():
                session_logger.error("Failed %s: %s", src.name, err)

    session_logger.info("Finished in %.2f s", time.time() - start)

if __name__ == "__main__":
    main()
