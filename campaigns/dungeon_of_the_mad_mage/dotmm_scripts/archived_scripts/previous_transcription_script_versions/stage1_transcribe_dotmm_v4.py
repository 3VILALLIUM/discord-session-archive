#!/usr/bin/env python3
"""
Stage 1 – Dungeon of the Mad Mage transcription  (v4-improved)

Key upgrades
------------✓ transcripts live under  dotmm_transcripts/  (campaign-scoped)
✓ logging configured explicitly (no duplicate handlers)
✓ retries only for OpenAI-side errors
✓ concurrent transcription of *files* (keeps chunk logic serial)
✓ chunks written to a temp folder → raw_audio stays untouched
✓ type hints, clearer names
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
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
from typing import Iterator, List, Dict, Any

from dotenv import load_dotenv
from pydub import AudioSegment
from openai import OpenAI, OpenAIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None  # headless / minimal install

__version__ = "4.1.0"

# ── config ────────────────────────────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    sys.exit("ERROR: set OPENAI_API_KEY in .env or environment")

client = OpenAI(api_key=API_KEY)

ROOT            = Path("campaigns/dungeon_of_the_mad_mage")
RAW_AUDIO_ROOT  = ROOT / "dotmm_sessions" / "raw_audio"
TRANSCRIPT_ROOT = ROOT / "dotmm_transcripts"
LOG_DIR         = ROOT / "logs"
CHUNK_SEC       = 5 * 60     # 5-minute slices
OVERLAP_SEC     = 5.0
SUPPORTED       = {".aac", ".wav", ".m4a", ".mp3", ".flac"}
MAX_WORKERS     = min(4, (os.cpu_count() or 1))

LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "stage1_transcribe_dotmm_v4.log"

# ── logging ───────────────────────────────────────────────────────────
fmt = "%(asctime)s.%(msecs)03d — %(levelname)s — %(message)s"
datefmt = "%Y-%m-%d %H:%M:%S"
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

file_hdl = RotatingFileHandler(LOG_FILE, maxBytes=1_048_576, backupCount=3)
file_hdl.setFormatter(logging.Formatter(fmt, datefmt))
root_logger.addHandler(file_hdl)

console_hdl = logging.StreamHandler(sys.stdout)
console_hdl.setFormatter(logging.Formatter(fmt, datefmt))
root_logger.addHandler(console_hdl)

log = root_logger  # shorthand

# ── dataclass ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ChunkMeta:
    idx: int
    start_ms: int
    path: Path

# ── helpers ───────────────────────────────────────────────────────────
def iter_chunks(audio: AudioSegment) -> Iterator[ChunkMeta]:
    step   = CHUNK_SEC * 1000
    offset = int(OVERLAP_SEC * 1000)
    pos = idx = 0
    while pos < len(audio):
        yield ChunkMeta(idx, max(0, pos - offset), None)
        pos += step
        idx += 1

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(OpenAIError),
    reraise=True,
)
def whisper(flac: Path):
    with flac.open("rb") as f:
        return client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
        )

# ── core work ─────────────────────────────────────────────────────────
def transcribe_file(session_dir: Path, src: Path) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{session_dir.name}_chunks_") as tmp_str:
        tmp_dir = Path(tmp_str)
        out_dir = TRANSCRIPT_ROOT / session_dir.name / src.stem
        out_dir.mkdir(parents=True, exist_ok=True)

        log.info("Processing %s", src.name)
        audio = AudioSegment.from_file(src)

        metas: List[ChunkMeta] = []
        for meta in iter_chunks(audio):
            chunk = tmp_dir / f"{src.stem}_chunk_{meta.idx:03}.flac"
            audio[meta.start_ms:meta.start_ms + CHUNK_SEC*1000].export(chunk, format="flac")
            metas.append(ChunkMeta(meta.idx, meta.start_ms, chunk))

        all_segments: List[Dict[str, Any]] = []
        for meta in metas:
            log.info("Transcribing %s", meta.path.name)
            chunk_json = out_dir / f"{meta.path.stem}.json"
            try:
                resp = whisper(meta.path)
                offset = meta.start_ms / 1000
                seglist = [
                    {"start": s.start + offset, "end": s.end + offset, "text": s.text}
                    for s in resp.segments
                ]
                record = {"chunk_file": meta.path.name, "segments": seglist}
                all_segments.extend(seglist)
            except OpenAIError as e:
                log.error("API error on %s: %s", meta.path.name, e)
                record = {"chunk_file": meta.path.name, "error": str(e)}
            except Exception:
                log.error("Unexpected error on %s", meta.path.name)
                log.debug(traceback.format_exc())
                record = {"chunk_file": meta.path.name, "error": "unexpected"}

            chunk_json.write_text(json.dumps(record, ensure_ascii=False, indent=2))
            log.info("Saved %s", chunk_json.name)

        combined = out_dir / f"{src.stem}.json"
        combined.write_text(json.dumps({"file": src.name, "segments": all_segments}, ensure_ascii=False, indent=2))
        log.info("Saved combined transcript → %s", combined.name)

# ── CLI entry ─────────────────────────────────────────────────────────
def pick_session_from_gui() -> Path:
    root = tk.Tk()
    root.withdraw()
    chosen = filedialog.askdirectory(title="Select session audio folder", initialdir=str(RAW_AUDIO_ROOT))
    if not chosen:
        sys.exit("No folder selected.")
    return Path(chosen)


def main() -> None:
    start = time.time()
    log.info("Stage 1 transcription (v%s) started", __version__)

    parser = argparse.ArgumentParser(description="Transcribe DOTMM session audio.")
    parser.add_argument("--session", help="Path to session folder under raw_audio")
    args = parser.parse_args()

    session_dir = Path(args.session) if args.session else (pick_session_from_gui() if tk else None)
    if session_dir is None:
        sys.exit("Tkinter not available and no --session provided.")
    if not session_dir.exists():
        sys.exit(f"Session folder {session_dir} does not exist.")

    audio_files = [p for p in session_dir.iterdir() if p.suffix.lower() in SUPPORTED]
    if not audio_files:
        sys.exit(f"No supported audio files in {session_dir}.")

    TRANSCRIPT_ROOT.mkdir(parents=True, exist_ok=True)
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(transcribe_file, session_dir, af): af for af in audio_files}
        for future in cf.as_completed(futures):
            src = futures[future]
            if error := future.exception():
                log.error("Failed %s: %s", src.name, error)

    log.info("Finished in %.2f s", time.time() - start)

if __name__ == "__main__":
    main()
