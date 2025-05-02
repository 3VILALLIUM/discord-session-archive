
#!/usr/bin/env python3
"""
Robust Stage 1 transcription for Dungeon of the Mad Mage

• Folder‑picker or --session argument
• 5‑minute chunks with 5‑second overlap (API‑safe size)
• Streams chunks to OpenAI Whisper v1
• Saves *each* chunk as its own verbose‑JSON plus a combined JSON
• Prints live progress and writes a log file
"""

from __future__ import annotations
import argparse, io, json, logging, math, os
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator, List, Tuple

import openai
from pydub import AudioSegment
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# simple folder picker (suppressed on CLI-only systems)
import tkinter as tk
from tkinter import filedialog

from dotenv import load_dotenv
load_dotenv()

ROOT_RAW_AUDIO = Path("campaigns/dungeon_of_the_mad_mage/dotmm_sessions/raw_audio")

@dataclass(frozen=True)
class Config:
    chunk_seconds: int = 300         # 5‑minute chunks
    chunk_overlap: float = 5.0       # 5‑second overlap
    sample_rate: int = 16_000
    model: str = "whisper-1"
    max_retries: int = 5
    loglevel: str = "INFO"

cfg = Config()

# ---------- helpers ----------------------------------------------------------

def iter_chunks(audio: AudioSegment) -> Iterator[Tuple[AudioSegment, int]]:
    """Yield (chunk, start_ms) pairs with safe overlap; guard against loops."""
    step_ms = cfg.chunk_seconds * 1000
    overlap_ms = int(cfg.chunk_overlap * 1000)
    start = 0
    total = len(audio)

    while start < total:
        end = min(start + step_ms, total)
        yield audio[start:end], start
        new_start = end - overlap_ms
        if new_start <= start:
            break                    # safety – never stall
        start = new_start

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
    return openai.audio.transcriptions.create(
        model=cfg.model,
        file=("chunk.wav", chunk_bytes, "audio/wav"),
        response_format="text",
    ).strip()

# ---------- core -------------------------------------------------------------

def transcribe_file(path: Path, out_folder: Path) -> List[dict]:
    logging.info("Loading %s", path.name)
    audio = AudioSegment.from_file(path)
    transcripts: List[dict] = []

    # accurate progress estimate
    step_ms = cfg.chunk_seconds * 1000 - int(cfg.chunk_overlap * 1000)
    total_chunks_est = max(1, math.ceil((len(audio) - 1) / step_ms) + 1)

    for idx, (chunk, start_ms) in enumerate(iter_chunks(audio), 1):
        logging.info("Chunk %d/%d (%d ms)", idx, total_chunks_est, start_ms)
        try:
            txt = whisper(wav_bytes(chunk))
        except Exception as exc:
            logging.error("Failed chunk %d: %s", idx, exc)
            continue

        record = {"index": idx, "start_ms": start_ms, "text": txt}
        transcripts.append(record)

        # per‑chunk file
        chunk_file = out_folder / f"{path.stem}_chunk{idx:03d}.json"
        chunk_file.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Saved chunk {idx:03d} → {chunk_file.name}  (chars {len(txt)})")

    return transcripts

def pick_session_folder() -> Path:
    try:
        root = tk.Tk(); root.withdraw()
        folder = filedialog.askdirectory(title="Select session_xxx_audio", initialdir=ROOT_RAW_AUDIO)
    except tk.TclError:
        folder = ""
    if not folder:
        raise SystemExit("No folder selected.")
    return Path(folder).resolve()

def output_folder_for(session_audio_folder: Path) -> Path:
    base = session_audio_folder.parent.parent
    return base / "dotmm_transcripts" / session_audio_folder.name.replace("_audio", "_transcript")

# ---------- entry ------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Transcribe a DOTMM session folder")
    ap.add_argument("--session", type=Path, help="Path to session_xxx_audio folder")
    args = ap.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=getattr(logging, cfg.loglevel, logging.INFO),
    )

    session_folder = args.session or pick_session_folder()
    if not session_folder.is_dir():
        raise SystemExit(f"{session_folder} is not a directory")

    log_root = session_folder.parents[2] / "dotmm_logs"
    log_root.mkdir(parents=True, exist_ok=True)
    log_path = log_root / f"dotmm_stage1_{session_folder.name}.log"
    fh = logging.FileHandler(log_path, mode="a", encoding="utf-8"); fh.setLevel(logging.INFO)
    logging.getLogger().addHandler(fh)

    logging.info("=== Transcribing %s ===", session_folder)
    audio_files = sorted(p for p in session_folder.iterdir() if p.suffix.lower() in {".aac", ".m4a", ".wav"})
    if not audio_files:
        raise SystemExit("No audio files found.")

    out_folder = output_folder_for(session_folder); out_folder.mkdir(parents=True, exist_ok=True)

    for audio_path in audio_files:
        print(f"Processing file: {audio_path.name}")
        transcripts = transcribe_file(audio_path, out_folder)
        combined = out_folder / f"{audio_path.stem}.json"
        combined.write_text(json.dumps(transcripts, indent=2, ensure_ascii=False), encoding="utf-8")
        logging.info("Saved combined → %s", combined.name)

    logging.info("All done — transcripts in %s", out_folder)

if __name__ == "__main__":
    main()
