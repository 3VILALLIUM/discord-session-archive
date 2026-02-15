#!/usr/bin/env python3
"""
discord_session_archive.py

Turnkey Craig -> whisper-1 -> transcript pipeline.

This script is source-agnostic and domain-agnostic:
- Accepts Craig export folders or direct audio file paths.
- Produces timestamped Markdown transcripts.
- Optionally writes cleaned Markdown, JSON, and NotebookLM-friendly Markdown.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = lambda: None  # type: ignore

AudioSegment = None  # lazy import


def ensure_pydub_loaded() -> None:
    """Import pydub lazily so unit tests can patch AudioSegment."""
    global AudioSegment
    if AudioSegment is not None:
        return
    try:
        from pydub import AudioSegment as _AS  # type: ignore

        AudioSegment = _AS  # noqa: N816
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: failed importing pydub: {exc}", file=sys.stderr)
        sys.exit(1)


try:
    from openai import OpenAI, OpenAIError
except ImportError:  # pragma: no cover
    print("ERROR: openai package not installed. pip install openai", file=sys.stderr)
    sys.exit(1)

try:
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
except ImportError:  # pragma: no cover
    print("ERROR: tenacity not installed. pip install tenacity", file=sys.stderr)
    sys.exit(1)

try:  # pragma: no cover
    import tkinter as tk
    from tkinter import filedialog
except Exception:  # pragma: no cover
    tk = None  # type: ignore
    filedialog = None  # type: ignore

SUPPORTED_EXTS = {".aac", ".flac", ".m4a", ".mp3", ".wav"}
DEFAULT_CHUNK_SEC = 120
DEFAULT_OVERLAP_SEC = 5.0
DEFAULT_MAX_WORKERS = min(4, os.cpu_count() or 1)
VERSION = "1.0.0"
NAME_MAP_MODES = ("none", "handle", "real")
HANDLE_MAP_PATH = Path("_local/config/handle_map.json")
REALNAME_MAP_PATH = Path("_local/config/realname_map.json")

LOG_FORMAT = "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


@dataclass
class ChunkSpec:
    index: int
    start_ms: int
    end_ms: int
    file_path: Path
    offset_sec: float


def find_repo_root(start: Path) -> Path:
    cur = start
    for _ in range(12):
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start


def format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hh = total // 3600
    mm = (total % 3600) // 60
    ss = total % 60
    return f"{hh:02}:{mm:02}:{ss:02}"


def sanitize_label(label: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", label.strip())
    clean = clean.strip("-._")
    return clean or "run"


def build_run_id(label: Optional[str]) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if label:
        return f"{sanitize_label(label)}_{stamp}"
    return stamp


def normalize_speaker(name: str) -> str:
    text = name.replace("_", " ").replace("-", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text or "Unknown Speaker"


def normalize_name_map_key(text: str) -> str:
    key = text.replace("_", " ").replace("-", " ").strip().lower()
    key = re.sub(r"\s+", " ", key)
    return key


def map_path_for_mode(mode: str) -> Optional[Path]:
    if mode == "handle":
        return HANDLE_MAP_PATH
    if mode == "real":
        return REALNAME_MAP_PATH
    return None


def load_name_map(mode: str) -> Dict[str, str]:
    map_path = map_path_for_mode(mode)
    if map_path is None:
        return {}
    if not map_path.exists():
        print(
            f"ERROR: name map file not found for mode '{mode}': {map_path}. "
            "Create it with .\\scripts\\init_local_config.ps1 and retry.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        payload = json.loads(map_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed reading name map file {map_path}: {exc}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(payload, dict):
        print(f"ERROR: name map file must be a JSON object: {map_path}", file=sys.stderr)
        sys.exit(1)

    mapped: Dict[str, str] = {}
    for raw_key, raw_value in payload.items():
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            print(f"ERROR: name map entries must be string:string pairs: {map_path}", file=sys.stderr)
            sys.exit(1)
        key = normalize_name_map_key(raw_key)
        value = raw_value.strip()
        if not key or not value:
            print(f"ERROR: name map keys/values must be non-empty strings: {map_path}", file=sys.stderr)
            sys.exit(1)
        if key in mapped and mapped[key] != value:
            print(f"ERROR: duplicate normalized key with conflicting values: '{raw_key}'", file=sys.stderr)
            sys.exit(1)
        mapped[key] = value
    return mapped


def apply_name_map_to_speaker(label: str, name_map: Dict[str, str]) -> str:
    if not name_map:
        return label
    return name_map.get(normalize_name_map_key(label), label)


def clean_text(text: str) -> str:
    stripped = re.sub(r"\s+", " ", text).strip()
    if stripped.lower() in {"uh", "um", "er", "ah"}:
        return ""
    stripped = stripped.replace("`", "'")
    stripped = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]+", "", stripped)
    return stripped.strip()


def check_ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg"))


def setup_logger(log_path: Optional[Path], quiet: bool) -> logging.Logger:
    logger = logging.getLogger("discord_session_archive")
    logger.setLevel(logging.INFO)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    formatter = logging.Formatter(LOG_FORMAT, LOG_DATEFMT)

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    if not quiet:
        sh = logging.StreamHandler(stream=sys.stdout)
        sh.setFormatter(formatter)
        logger.addHandler(sh)

    return logger


def load_api_key() -> str:
    load_dotenv()
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("ERROR: OPENAI_API_KEY not set (set env var or .env).", file=sys.stderr)
        sys.exit(1)
    return key


def build_client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key)


def discover_audio(paths: Sequence[str]) -> List[Path]:
    discovered: List[Path] = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            print(f"WARNING: path not found: {path}", file=sys.stderr)
            continue
        if path.is_file():
            if path.suffix.lower() in SUPPORTED_EXTS:
                discovered.append(path)
            else:
                print(f"WARNING: unsupported extension skipped: {path}", file=sys.stderr)
            continue

        for child in sorted(path.rglob("*")):
            if child.is_file() and child.suffix.lower() in SUPPORTED_EXTS:
                discovered.append(child.resolve())

    unique: List[Path] = []
    seen = set()
    for item in discovered:
        if item not in seen:
            unique.append(item)
            seen.add(item)
    return unique


def pick_folder_via_gui(initial_dir: Path) -> Path:  # pragma: no cover
    if tk is None or filedialog is None:
        print("ERROR: Tkinter unavailable. Use --input <path> instead.", file=sys.stderr)
        sys.exit(1)
    root = tk.Tk()
    root.withdraw()
    choice = filedialog.askdirectory(
        title="Select Craig export folder",
        initialdir=str(initial_dir),
    )
    if not choice:
        print("ERROR: no folder selected.", file=sys.stderr)
        sys.exit(1)
    return Path(choice).resolve()


def compute_chunks(duration_ms: int, chunk_ms: int, overlap_ms: int) -> List[Tuple[int, int]]:
    chunks: List[Tuple[int, int]] = []
    start = 0
    while start < duration_ms:
        end = min(start + chunk_ms, duration_ms)
        chunks.append((start, end))
        if end >= duration_ms:
            break
        start = max(0, end - overlap_ms)
        if len(chunks) > 100_000:
            break
    return chunks


def export_chunks(audio: Any, bounds: List[Tuple[int, int]], temp_dir: Path, stem: str) -> List[ChunkSpec]:
    specs: List[ChunkSpec] = []
    for idx, (start, end) in enumerate(bounds):
        chunk = audio[start:end]
        chunk_path = temp_dir / f"{stem}_chunk_{idx:03d}.flac"
        chunk.export(chunk_path, format="flac")  # type: ignore[attr-defined]
        specs.append(
            ChunkSpec(
                index=idx,
                start_ms=start,
                end_ms=end,
                file_path=chunk_path,
                offset_sec=start / 1000.0,
            )
        )
    return specs


def parse_segment_obj(obj: Any, offset: float) -> Dict[str, Any]:
    if isinstance(obj, dict):
        start = float(obj.get("start", 0.0)) + offset
        end = float(obj.get("end", start)) + offset
        text = str(obj.get("text", "")).strip()
        return {"start": start, "end": end, "text": text}
    start = float(getattr(obj, "start", 0.0)) + offset
    end = float(getattr(obj, "end", start)) + offset
    text = str(getattr(obj, "text", "")).strip()
    return {"start": start, "end": end, "text": text}


def read_chunk_bytes(path: Path) -> bytes:
    with path.open("rb") as handle:
        return handle.read()


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    retry=retry_if_exception_type(OpenAIError),
)
def call_whisper(client: OpenAI, chunk: ChunkSpec) -> Dict[str, Any]:
    payload = read_chunk_bytes(chunk.file_path)
    response = client.audio.transcriptions.create(
        model="whisper-1",
        file=(chunk.file_path.name, payload, "audio/flac"),
        response_format="verbose_json",
    )
    segments_raw = getattr(response, "segments", None)
    if segments_raw is None and isinstance(response, dict):
        segments_raw = response.get("segments", [])

    segments = [parse_segment_obj(seg, chunk.offset_sec) for seg in (segments_raw or [])]
    return {
        "chunk_file": chunk.file_path.name,
        "offset_sec": chunk.offset_sec,
        "duration_sec": (chunk.end_ms - chunk.start_ms) / 1000.0,
        "segments": segments,
    }


def transcribe_track(
    client: OpenAI,
    audio_path: Path,
    name_map: Dict[str, str],
    chunk_sec: int,
    overlap_sec: float,
    max_workers: int,
    dry_run: bool,
    logger: logging.Logger,
) -> Dict[str, Any]:
    speaker = apply_name_map_to_speaker(normalize_speaker(audio_path.stem), name_map)
    ensure_pydub_loaded()
    if AudioSegment is None:  # pragma: no cover
        raise RuntimeError("Audio backend unavailable after pydub initialization.")
    audio = AudioSegment.from_file(str(audio_path))
    duration_ms = len(audio)
    duration_sec = duration_ms / 1000.0

    bounds = compute_chunks(duration_ms, int(chunk_sec * 1000), int(overlap_sec * 1000))
    logger.info("Loaded %s (%.2fs), planned %d chunks", audio_path.name, duration_sec, len(bounds))

    if dry_run:
        return {
            "source_file": audio_path.name,
            "speaker": speaker,
            "duration_sec": duration_sec,
            "segments": [],
            "errors": [],
            "planned_chunks": len(bounds),
        }

    with tempfile.TemporaryDirectory(prefix="discord_session_archive_chunks_") as tmp:
        temp_dir = Path(tmp)
        specs = export_chunks(audio, bounds, temp_dir, audio_path.stem)
        del audio

        all_segments: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        with cf.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {executor.submit(call_whisper, client, spec): spec for spec in specs}
            done = 0
            total = len(specs)
            for future in cf.as_completed(future_to_chunk):
                spec = future_to_chunk[future]
                try:
                    result = future.result()
                    for segment in result["segments"]:
                        if not segment["text"]:
                            continue
                        all_segments.append(
                            {
                                "start": segment["start"],
                                "end": segment["end"],
                                "speaker": speaker,
                                "text": segment["text"],
                                "source_file": audio_path.name,
                            }
                        )
                except Exception as exc:  # noqa: BLE001
                    errors.append({"chunk_file": spec.file_path.name, "error": f"{exc.__class__.__name__}: {exc}"})
                done += 1
                logger.info("Track %s progress: %d/%d chunks", audio_path.name, done, total)

    all_segments.sort(key=lambda row: (row["start"], row["end"], row["speaker"]))
    return {
        "source_file": audio_path.name,
        "speaker": speaker,
        "duration_sec": duration_sec,
        "segments": all_segments,
        "errors": errors,
        "planned_chunks": len(bounds),
    }


def render_markdown(segments: List[Dict[str, Any]], title: str) -> str:
    lines = [
        f"# {title}",
        "",
        f"Generated UTC: {datetime.utcnow().isoformat()}Z",
        "",
    ]
    for seg in segments:
        timestamp = format_timestamp(float(seg["start"]))
        lines.append(f"- [{timestamp}] **{seg['speaker']}**: {seg['text']}")
    lines.append("")
    return "\n".join(lines)


def render_notebooklm_markdown(run_id: str, segments: List[Dict[str, Any]]) -> str:
    lines = [
        "# NotebookLM Input Notes",
        "",
        "This transcript was generated from a Discord recording export.",
        f"Run ID: {run_id}",
        "",
        "## Suggested prompts",
        "- Summarize the conversation in 10 bullet points.",
        "- Extract action items and owners.",
        "- Identify unresolved questions and follow-ups.",
        "",
        "## Transcript",
        "",
    ]
    for seg in segments:
        lines.append(f"- [{format_timestamp(float(seg['start']))}] {seg['speaker']}: {seg['text']}")
    lines.append("")
    return "\n".join(lines)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Turnkey Craig -> whisper-1 -> transcript pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", "-i", nargs="+", help="Craig export folder(s) or audio file path(s).")
    parser.add_argument("--pick-folder", action="store_true", help="Open a folder picker for input.")
    parser.add_argument("--output-root", default="_local/runs", help="Output root directory.")
    parser.add_argument("--label", help="Optional label to include in run folder name.")
    parser.add_argument(
        "--name-map-mode",
        choices=NAME_MAP_MODES,
        default="none",
        help="Optional speaker-label mapping mode. none=disabled, handle=_local/config/handle_map.json, real=_local/config/realname_map.json.",
    )
    parser.add_argument("--clean", action="store_true", help="Write cleaned Markdown transcript.")
    parser.add_argument("--json", action="store_true", dest="write_json", help="Write transcript JSON.")
    parser.add_argument("--notebooklm", action="store_true", help="Write NotebookLM-friendly Markdown.")
    parser.add_argument("--chunk-sec", type=int, default=DEFAULT_CHUNK_SEC, help="Chunk duration in seconds.")
    parser.add_argument("--overlap-sec", type=float, default=DEFAULT_OVERLAP_SEC, help="Chunk overlap in seconds.")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, help="Max worker threads.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing run directory.")
    parser.add_argument("--dry-run", action="store_true", help="Preview work without writing files.")
    parser.add_argument("--quiet", action="store_true", help="Suppress console logs.")
    parser.add_argument("--version", action="store_true", help="Print version and exit.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    if args.version:
        print(f"discord_session_archive {VERSION}")
        return

    if not check_ffmpeg():
        print("ERROR: ffmpeg not found in PATH. Install ffmpeg and retry.", file=sys.stderr)
        sys.exit(1)

    script_path = Path(__file__).resolve()
    repo_root = find_repo_root(script_path.parent)
    os.chdir(repo_root)
    name_map = load_name_map(args.name_map_mode)

    input_paths = list(args.input or [])
    if args.pick_folder:
        input_paths.append(str(pick_folder_via_gui(repo_root)))
    if not input_paths:
        print("ERROR: provide --input <path> or use --pick-folder.", file=sys.stderr)
        sys.exit(1)

    audio_files = discover_audio(input_paths)
    if not audio_files:
        print("ERROR: no supported audio files found.", file=sys.stderr)
        sys.exit(1)

    run_id = build_run_id(args.label)
    run_dir = Path(args.output_root).resolve() / run_id
    log_path = None if args.dry_run else (run_dir / "run.log")
    logger = setup_logger(log_path=log_path, quiet=args.quiet)

    logger.info("Run ID: %s", run_id)
    logger.info("Inputs: %d audio file(s)", len(audio_files))
    logger.info("Name map mode: %s", args.name_map_mode)
    for file_path in audio_files:
        logger.info("  %s", file_path)

    if run_dir.exists() and not args.force and not args.dry_run:
        print(f"ERROR: output run directory exists: {run_dir} (use --force)", file=sys.stderr)
        sys.exit(1)
    if not args.dry_run:
        run_dir.mkdir(parents=True, exist_ok=True)

    api_key = load_api_key()
    client = build_client(api_key)

    start = time.time()
    tracks: List[Dict[str, Any]] = []
    for audio_file in audio_files:
        try:
            track = transcribe_track(
                client=client,
                audio_path=audio_file,
                name_map=name_map,
                chunk_sec=args.chunk_sec,
                overlap_sec=args.overlap_sec,
                max_workers=args.max_workers,
                dry_run=args.dry_run,
                logger=logger,
            )
            tracks.append(track)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed processing %s: %s", audio_file, exc)
            tracks.append(
                {
                    "source_file": audio_file.name,
                    "speaker": apply_name_map_to_speaker(normalize_speaker(audio_file.stem), name_map),
                    "duration_sec": 0.0,
                    "segments": [],
                    "errors": [{"error": f"{exc.__class__.__name__}: {exc}"}],
                    "planned_chunks": 0,
                }
            )

    all_segments: List[Dict[str, Any]] = []
    all_errors: List[Dict[str, Any]] = []
    for track in tracks:
        all_segments.extend(track["segments"])
        all_errors.extend(track["errors"])
    all_segments.sort(key=lambda row: (row["start"], row["end"], row["speaker"]))

    cleaned_segments = []
    for seg in all_segments:
        cleaned = clean_text(seg["text"])
        if not cleaned:
            continue
        cleaned_segments.append({**seg, "text": cleaned})

    if args.dry_run:
        logger.info("[dry-run] Would write outputs to %s", run_dir)
        logger.info("[dry-run] Segments: %d, errors: %d", len(all_segments), len(all_errors))
        logger.info("Finished in %.2fs", time.time() - start)
        return

    transcript_md = render_markdown(all_segments, "Transcript")
    write_text(run_dir / "transcript.md", transcript_md)
    logger.info("Wrote %s", run_dir / "transcript.md")

    if args.clean:
        cleaned_md = render_markdown(cleaned_segments, "Transcript (Cleaned)")
        write_text(run_dir / "transcript.cleaned.md", cleaned_md)
        logger.info("Wrote %s", run_dir / "transcript.cleaned.md")

    if args.write_json:
        payload = {
            "version": VERSION,
            "engine": "whisper-1",
            "run_id": run_id,
            "created_utc": datetime.utcnow().isoformat() + "Z",
            "inputs": [str(p) for p in audio_files],
            "segments": all_segments,
            "errors": all_errors,
            "tracks": tracks,
        }
        write_json(run_dir / "transcript.json", payload)
        logger.info("Wrote %s", run_dir / "transcript.json")

    if args.notebooklm:
        notebooklm_md = render_notebooklm_markdown(run_id, cleaned_segments if args.clean else all_segments)
        write_text(run_dir / "notebooklm.md", notebooklm_md)
        logger.info("Wrote %s", run_dir / "notebooklm.md")

    logger.info("Finished in %.2fs", time.time() - start)
    print(f"Transcript run complete: {run_dir}")


if __name__ == "__main__":  # pragma: no cover
    main()
