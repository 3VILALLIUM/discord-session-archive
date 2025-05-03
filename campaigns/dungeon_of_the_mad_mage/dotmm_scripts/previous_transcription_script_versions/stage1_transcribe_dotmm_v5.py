#!/usr/bin/env python3
"""
Stage 1 – Dungeon of the Mad Mage transcription (v5.0)

Key upgrades
------------
✓ transcripts live under dotmm_transcripts/
✓ dynamic session-specific logging in dotmm_logs/session_###.log
✓ retries only for OpenAI-side errors
✓ concurrent transcription of files
✓ chunks in temp directory (raw_audio untouched)
✓ type hints and explicit logging setup
✓ console handler uses UTF-8 with replacement to avoid encoding errors
✓ log format uses ASCII hyphens only
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
from typing import Iterator, List, Dict, Any

from dotenv import load_dotenv
from pydub import AudioSegment
from openai import OpenAI, OpenAIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None

__version__ = "5.0.0"

# ── config ─────────────────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    sys.exit("ERROR: set OPENAI_API_KEY in .env or environment")
client = OpenAI(api_key=API_KEY)

ROOT = Path("campaigns/dungeon_of_the_mad_mage")
RAW_AUDIO_ROOT = ROOT / "dotmm_sessions" / "raw_audio"
TRANSCRIPT_ROOT = ROOT / "dotmm_transcripts"
LOG_ROOT = ROOT / "dotmm_logs"

CHUNK_SEC = 5 * 60
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
def iter_chunks(audio: AudioSegment) -> Iterator[ChunkMeta]:
    step = CHUNK_SEC * 1000
    offset = int(OVERLAP_SEC * 1000)
    pos = idx = 0
    while pos < len(audio):
        yield ChunkMeta(idx, max(0, pos - offset), None)
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
def transcribe_file(session_dir: Path, src: Path, logger: logging.Logger) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{session_dir.name}_chunks_") as tmp:
        tmp_dir = Path(tmp)
        # FIXED: write to correct transcript folder
        out_dir = TRANSCRIPT_ROOT / session_dir.name / src.stem
        out_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Processing %s", src.name)
        audio = AudioSegment.from_file(src)

        metas: List[ChunkMeta] = []
        for meta in iter_chunks(audio):
            chunk_path = tmp_dir / f"{src.stem}_chunk_{meta.idx:03}.flac"
            audio[meta.start_ms:meta.start_ms + CHUNK_SEC * 1000].export(chunk_path, format="flac")
            metas.append(ChunkMeta(meta.idx, meta.start_ms, chunk_path))

        all_segments: List[Dict[str, Any]] = []
        for meta in metas:
            logger.info("Transcribing %s", meta.path.name)
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
                logger.error("API error on %s: %s", meta.path.name, e)
                record = {"chunk_file": meta.path.name, "error": str(e)}
            except Exception:
                logger.error("Unexpected error on %s", meta.path.name)
                logger.debug(traceback.format_exc())
                record = {"chunk_file": meta.path.name, "error": "unexpected"}

            chunk_json.write_text(json.dumps(record, ensure_ascii=False, indent=2))
            logger.info("Saved %s", chunk_json.name)

        # write combined transcript
        combined = out_dir / f"{src.stem}.json"
        combined.write_text(
            json.dumps({"file": src.name, "segments": all_segments}, ensure_ascii=False, indent=2)
        )
        logger.info("Saved combined transcript -> %s", combined.name)

# ── GUI folder picker ─────────────────────────────────────────
def pick_session_from_gui() -> Path:
    root = tk.Tk(); root.withdraw()
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
    parser.add_argument("--session", help="Path to session folder under raw_audio or dotmm_transcripts")
    args = parser.parse_args()
    session_dir = Path(args.session) if args.session else pick_session_from_gui()
    if not session_dir.exists():
        sys.exit(f"Session folder {session_dir} does not exist.")

    # prepare dirs
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT_ROOT.mkdir(parents=True, exist_ok=True)

    # setup logging
    log_file = LOG_ROOT / f"{session_dir.name}.log"
    log_fmt = "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"
    session_logger = logging.getLogger(session_dir.name)
    session_logger.setLevel(logging.INFO)
    fh = RotatingFileHandler(str(log_file), maxBytes=1_048_576, backupCount=3)
    fh.setFormatter(logging.Formatter(log_fmt, date_fmt))
    session_logger.addHandler(fh)
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ch = logging.StreamHandler(utf8_stdout)
    ch.setFormatter(logging.Formatter(log_fmt, date_fmt))
    session_logger.addHandler(ch)

    # process audio
    audio_files = [p for p in session_dir.iterdir() if p.suffix.lower() in SUPPORTED]
    if not audio_files:
        sys.exit(f"No supported audio files in {session_dir}.")

    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(transcribe_file, session_dir, af, session_logger): af for af in audio_files}
        for future in cf.as_completed(futures):
            src = futures[future]
            if err := future.exception():
                session_logger.error("Failed %s: %s", src.name, err)

    session_logger.info("Finished in %.2f s", time.time() - start)

if __name__ == "__main__":
    main()
