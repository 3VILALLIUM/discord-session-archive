#!/usr/bin/env python3
"""
Stage 1 transcription script for Dungeon of the Mad Mage.

• Lets you pick a session _folder_ (not a single file) via a GUI dialog
• Streams in-memory audio chunks to OpenAI Whisper
• Exponential back-off on transient API errors
• Saves per-track JSON into the matching ..._transcript folder
• Drops a session-level log file in dotmm_logs
"""

from __future__ import annotations

from dotenv import load_dotenv
import os

load_dotenv()

import argparse
import io
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Tuple

import openai
from pydub import AudioSegment
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# NEW: simple folder picker
import tkinter as tk
from tkinter import filedialog

# ---------- configuration ----------
# TODO: Consider loading these values from an external config file (e.g., YAML)
# to avoid direct code edits when paths or models change.
ROOT_RAW_AUDIO = Path(
    "campaigns/dungeon_of_the_mad_mage/dotmm_sessions/raw_audio"
)

@dataclass(frozen=True)
class Config:
    chunk_seconds: int = 30
    chunk_overlap: float = 0.25  # seconds
    sample_rate: int = 16_000
    model: str = "whisper-1"
    max_retries: int = 5
    loglevel: str = "INFO"

cfg = Config()

# ---------- helpers (unchanged logic) ----------
def iter_chunks(audio: AudioSegment) -> Iterator[Tuple[AudioSegment, int]]:
    step_ms = cfg.chunk_seconds * 1000
    overlap_ms = int(cfg.chunk_overlap * 1000)
    start = 0
    total = len(audio)
    while start < total:
        end = min(start + step_ms, total)
        yield audio[start:end], start
        start = end - overlap_ms

def wav_bytes(chunk: AudioSegment) -> bytes:
    if chunk.frame_rate != cfg.sample_rate:
        chunk = chunk.set_frame_rate(cfg.sample_rate)
    buf = io.BytesIO()
    chunk.export(buf, format="wav")
    return buf.getvalue()

@retry(
    stop=stop_after_attempt(cfg.max_retries),
    wait=wait_exponential(min=2, max=30),
    retry=retry_if_exception_type(openai.OpenAIError),
    reraise=True,
)
def whisper(chunk_bytes: bytes) -> str:
    res = openai.audio.transcriptions.create(
        model=cfg.model,
        file=("chunk.wav", chunk_bytes, "audio/wav"),
        response_format="text",
    )
    return res.text.strip()

# ---------- core workflow ----------
def transcribe_file(path: Path) -> List[dict]:
    logging.info("Loading %s", path.name)
    audio = AudioSegment.from_file(path)
    transcripts: List[dict] = []
    total_chunks = math.ceil(len(audio) / (cfg.chunk_seconds * 1000))

    # NOTE: For long sessions with many tracks, consider parallelizing these calls
    # (e.g., via concurrent.futures) to utilize your GPU more efficiently.
    for idx, (chunk, start_ms) in enumerate(iter_chunks(audio), 1):
        logging.info("Chunk %d/%d (%d ms)", idx, total_chunks, start_ms)
        try:
            txt = whisper(wav_bytes(chunk))
        except Exception as exc:
            logging.error("Failed chunk %d: %s", idx, exc)
            continue
        transcripts.append({"index": idx, "start_ms": start_ms, "text": txt})

    return transcripts

def pick_session_folder() -> Path:
    root = tk.Tk()
    root.withdraw()  # hide main window
    folder = filedialog.askdirectory(
        title="Select a session_xxx_audio folder",
        initialdir=ROOT_RAW_AUDIO,
    )
    if not folder:
        raise SystemExit("No folder selected — exiting.")
    return Path(folder).resolve()

def output_folder_for(session_audio_folder: Path) -> Path:
    # BUGFIX: build path without non-existent Path.with_parent
    base = session_audio_folder.parent.parent
    transcripts_root = base / "dotmm_transcripts"
    return transcripts_root / session_audio_folder.name.replace("_audio", "_transcript")

def main() -> None:
    ap = argparse.ArgumentParser(description="Transcribe a DOTMM session folder")
    ap.add_argument(
        "--session", type=Path, help="Path to session_xxx_audio folder"
    )
    args = ap.parse_args()

    # safer loglevel fallback
    level_name = cfg.loglevel.upper()
    if level_name not in logging._nameToLevel:
        level_name = "INFO"
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging._nameToLevel[level_name],
    )

    session_folder = args.session or pick_session_folder()
    if not session_folder.is_dir():
        raise SystemExit(f"{session_folder} is not a directory")

    log_root = session_folder.parents[2] / "dotmm_logs"
    log_root.mkdir(parents=True, exist_ok=True)
    log_path = log_root / f"dotmm_stage1_{session_folder.name}.log"
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.INFO)
    logging.getLogger().addHandler(fh)

    logging.info("=== Transcribing folder: %s ===", session_folder)
    audio_files = sorted(
        p for p in session_folder.iterdir()
        if p.suffix.lower() in {".aac", ".m4a", ".wav"}
    )
    if not audio_files:
        raise SystemExit("No audio files found in selected folder.")

    out_folder = output_folder_for(session_folder)
    out_folder.mkdir(parents=True, exist_ok=True)

    for audio_path in audio_files:
        # NOTE: consider skipping if output JSON already exists
        transcripts = transcribe_file(audio_path)
        out_file = out_folder / audio_path.with_suffix(".json").name
        out_file.write_text(
            json.dumps(transcripts, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logging.info("Saved %s", out_file.name)

    logging.info("All done — transcripts saved to %s", out_folder)

if __name__ == "__main__":
    main()
