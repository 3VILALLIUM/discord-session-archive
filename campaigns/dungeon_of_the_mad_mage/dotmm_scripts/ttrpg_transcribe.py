"""
ttrpg_transcribe.py
Universal Stage 1 transcription tool for TTRPG session audio.

Features:
  * Accepts one or more audio files OR a folder containing audio (extensions: .aac .m4a .mp3 .wav .flac)
  * Splits each source into overlapping chunks (default 120s with 5s overlap)
  * Sends chunks to OpenAI Whisper (whisper-1) with verbose_json output
  * Writes per-chunk JSON plus a combined JSON with global (file) timestamps
  * Concurrency with retry/backoff (tenacity) and robust logging
  * Safe UTF-8 I/O, does not overwrite existing combined JSON unless --force
  * Dry-run mode to preview actions
  * Session name auto-derived (folder_name_audio -> folder_name_transcript else + "_transcript")

CLI examples:
  python ttrpg_transcribe.py --input path/to/folder_or_file
  python ttrpg_transcribe.py --input file1.m4a file2.mp3 --chunk-sec 90 --overlap-sec 3
  python ttrpg_transcribe.py  (opens folder picker if no --input and Tk available)

Requires env var OPENAI_API_KEY (can be loaded from .env at repo root).

Exit codes:
  0 success (even if some chunks errored)
  1 setup/config error (missing key, ffmpeg, no inputs, etc.)
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple, Dict, Any, Optional

# Third-party (fail fast with helpful message)
try:
	from dotenv import load_dotenv
except ImportError:  # pragma: no cover
	load_dotenv = lambda: None  # type: ignore

# NOTE: pydub is lazy-imported because Python 3.13 removed the stdlib 'audioop'
# which older pydub versions attempt to import; we only need pydub when actually
# processing real audio (tests patch AudioSegment). This prevents import-time
# failure during unit tests or environments without ffmpeg configured yet.
AudioSegment = None  # type: ignore

def ensure_pydub_loaded() -> None:
	"""Import pydub's AudioSegment on demand.

	Separated so tests can patch 'AudioSegment' before this runs.
	"""
	global AudioSegment
	if AudioSegment is not None:  # already provided (either real or patched)
		return
	try:
		from pydub import AudioSegment as _AS  # type: ignore
		AudioSegment = _AS  # noqa: N816
	except ImportError:
		print("ERROR: pydub not installed. pip install pydub", file=sys.stderr)
		sys.exit(1)
	except Exception as e:  # pragma: no cover
		print(f"ERROR: failed importing pydub: {e}", file=sys.stderr)
		sys.exit(1)

try:
	from openai import OpenAI, OpenAIError
except ImportError:
	print("ERROR: openai package not installed. pip install openai", file=sys.stderr)
	sys.exit(1)

try:
	from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
except ImportError:
	print("ERROR: tenacity not installed. pip install tenacity", file=sys.stderr)
	sys.exit(1)

# Optional GUI fallback
try:  # pragma: no cover
	import tkinter as tk
	from tkinter import filedialog
except Exception:  # pragma: no cover
	tk = None  # type: ignore
	filedialog = None  # type: ignore

SUPPORTED_EXTS = {".aac", ".m4a", ".mp3", ".wav", ".flac"}
DEFAULT_CHUNK_SEC = 120
DEFAULT_OVERLAP_SEC = 5.0
MAX_DEFAULT_WORKERS = min(4, os.cpu_count() or 1)

LOG_FORMAT = "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

VERSION = "1.0.0"


# ── Dataclasses ──────────────────────────────────────────────────────────────
@dataclass
class ChunkSpec:
	index: int
	start_ms: int
	end_ms: int
	file_path: Path  # exported chunk path
	offset_sec: float


# ── Utility Functions ────────────────────────────────────────────────────────
def find_repo_root(start: Path) -> Path:
	"""Walk upward up to a small depth looking for repo markers."""
	cur = start
	markers = {".git", "dotmm_transcripts"}
	for _ in range(12):
		if any((cur / m).exists() for m in markers):
			return cur
		if cur.parent == cur:
			break
		cur = cur.parent
	return start  # fallback


def build_session_name(parents: List[Path]) -> str:
	if not parents:
		return "session_transcript"
	first = parents[0]
	base = first.name
	if base.endswith("_audio"):
		# Preserve underscore before suffix: '_audio' (6 chars) -> '_transcript'
		return base[:-6] + "_transcript"
	if not base.endswith("_transcript"):
		return base + "_transcript"
	return base


def derive_session_name(inputs: Sequence[Path]) -> str:
	parents = {p.parent for p in inputs}
	return build_session_name(list(parents))


def check_ffmpeg() -> bool:
	return bool(shutil.which("ffmpeg"))


def setup_logger(log_path: Path, verbose: bool = True) -> logging.Logger:
	logger = logging.getLogger("ttrpg_transcribe")
	logger.setLevel(logging.INFO)
	# Clear old handlers
	for h in list(logger.handlers):
		logger.removeHandler(h)
	log_path.parent.mkdir(parents=True, exist_ok=True)
	fh = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
	fmt = logging.Formatter(LOG_FORMAT, LOG_DATEFMT)
	fh.setFormatter(fmt)
	logger.addHandler(fh)
	if verbose:
		ch = logging.StreamHandler(stream=sys.stdout)
		ch.setFormatter(fmt)
		logger.addHandler(ch)
	logger.info("Log start for session")
	return logger


def load_api_key() -> str:
	load_dotenv()
	key = os.getenv("OPENAI_API_KEY")
	if not key:
		print("ERROR: OPENAI_API_KEY not set (add to environment or .env).", file=sys.stderr)
		sys.exit(1)
	return key


def discover_audio(paths: Sequence[str]) -> List[Path]:
	out: List[Path] = []
	for p_str in paths:
		p = Path(p_str).expanduser().resolve()
		if not p.exists():
			print(f"WARNING: path not found: {p}", file=sys.stderr)
			continue
		if p.is_dir():
			for child in sorted(p.iterdir()):
				if child.suffix.lower() in SUPPORTED_EXTS and child.is_file():
					out.append(child)
		else:
			if p.suffix.lower() in SUPPORTED_EXTS:
				out.append(p)
			else:
				print(f"WARNING: unsupported extension skipped: {p}", file=sys.stderr)
	# Deduplicate preserving order
	seen = set()
	dedup: List[Path] = []
	for f in out:
		if f not in seen:
			dedup.append(f)
			seen.add(f)
	return dedup


def gui_pick_inputs(default_root: Path) -> List[Path]:  # pragma: no cover
	if not tk:
		print("ERROR: Tk not available; specify --input.", file=sys.stderr)
		sys.exit(1)
	root = tk.Tk(); root.withdraw()
	if filedialog is None:  # safety
		print("ERROR: filedialog not available; specify --input.", file=sys.stderr)
		sys.exit(1)
	folder = filedialog.askdirectory(title="Select folder containing audio files", initialdir=str(default_root))
	if not folder:
		print("ERROR: no folder selected.", file=sys.stderr)
		sys.exit(1)
	return discover_audio([folder])


def compute_chunks(duration_ms: int, chunk_ms: int, overlap_ms: int) -> List[Tuple[int, int]]:
	res = []
	start = 0
	while start < duration_ms:
		end = min(start + chunk_ms, duration_ms)
		res.append((start, end))
		if end >= duration_ms:
			break
		start = end - overlap_ms
		if start < 0:
			start = 0
		if len(res) > 100_000:  # safety guard
			break
	return res


def export_chunks(audio: Any, chunk_bounds: List[Tuple[int, int]],
			  temp_dir: Path, stem: str) -> List[ChunkSpec]:
	specs: List[ChunkSpec] = []
	for idx, (a, b) in enumerate(chunk_bounds):
		chunk = audio[a:b]
		chunk_name = f"{stem}_chunk_{idx:03d}.flac"
		chunk_path = temp_dir / chunk_name
		# Export inside loop (indent fix)
		chunk.export(chunk_path, format="flac")  # type: ignore[attr-defined]
		specs.append(ChunkSpec(index=idx, start_ms=a, end_ms=b, file_path=chunk_path, offset_sec=a / 1000.0))
	return specs


def write_json(path: Path, data: Any, dry: bool, logger: logging.Logger) -> None:
	if dry:
		logger.info(f"[dry-run] Would write {path}")
		return
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=2)


# ── Transcription (with retry) ───────────────────────────────────────────────
RetryExc = (OpenAIError,)


def _read_bytes(path: Path) -> bytes:
	with path.open("rb") as f:
		return f.read()


def _format_err(e: Exception) -> str:
	return f"{e.__class__.__name__}: {e}"


def build_client(api_key: str) -> OpenAI:
	return OpenAI(api_key=api_key)


def transcribe_chunk_callable(client: OpenAI, chunk: ChunkSpec, model: str = "whisper-1") -> Dict[str, Any]:
	"""Executed inside worker thread. Return dict with either 'segments' or 'error'."""
	data = _read_bytes(chunk.file_path)

	@retry(stop=stop_after_attempt(5),
		   wait=wait_exponential(multiplier=1, min=1, max=20),
		   retry=retry_if_exception_type(OpenAIError))
	def _call() -> Dict[str, Any]:
		resp = client.audio.transcriptions.create(
			model=model,
			file=(chunk.file_path.name, data, "audio/flac"),
			response_format="verbose_json"
		)
		segments_raw = getattr(resp, "segments", None)
		if segments_raw is None and isinstance(resp, dict):
			segments_raw = resp.get("segments", [])
		segments: List[Dict[str, Any]] = []
		for seg in segments_raw or []:
			start = float(seg.get("start", 0.0)) + chunk.offset_sec
			end = float(seg.get("end", start)) + chunk.offset_sec
			text = seg.get("text", "").strip()
			segments.append({"start": start, "end": end, "text": text})
		return {
			"chunk_file": chunk.file_path.name,
			"offset_sec": chunk.offset_sec,
			"duration_sec": (chunk.end_ms - chunk.start_ms) / 1000.0,
			"segments": segments
		}

	try:
		return _call()
	except Exception as e:  # noqa: BLE001
		return {
			"chunk_file": chunk.file_path.name,
			"offset_sec": chunk.offset_sec,
			"duration_sec": (chunk.end_ms - chunk.start_ms) / 1000.0,
			"error": _format_err(e)
		}


# ── Main Processing Logic ───────────────────────────────────────────────────
def process_file(
	client: OpenAI,
	audio_path: Path,
	out_root: Path,
	session_name: str,
	chunk_sec: int,
	overlap_sec: float,
	max_workers: int,
	dry_run: bool,
	force: bool,
	logger: logging.Logger
) -> None:
	stem = audio_path.stem
	file_out_dir = out_root / session_name / stem
	combined_json_path = file_out_dir / f"{stem}.json"

	if combined_json_path.exists() and not force:
		if dry_run:
			logger.info(f"[dry-run] Would skip existing (use --force) {combined_json_path}")
		else:
			logger.info(f"Skipping {audio_path.name} (combined JSON exists; use --force to overwrite)")
		return

	if not audio_path.exists():
		logger.error(f"Missing file: {audio_path}")
		return

	logger.info(f"Loading audio: {audio_path}")
	load_start = time.time()
	ensure_pydub_loaded()
	audio = AudioSegment.from_file(audio_path)  # type: ignore[attr-defined]
	duration_ms = len(audio)
	duration_sec = duration_ms / 1000.0
	logger.info(f"Loaded {audio_path.name} ({duration_sec:.2f}s) in {time.time() - load_start:.2f}s")

	chunk_ms = int(chunk_sec * 1000)
	overlap_ms = int(overlap_sec * 1000)
	bounds = compute_chunks(duration_ms, chunk_ms, overlap_ms)
	logger.info(f"Planned {len(bounds)} chunks (chunk={chunk_sec}s overlap={overlap_sec}s)")

	if dry_run:
		logger.info(f"[dry-run] Would export & transcribe {audio_path.name} -> {len(bounds)} chunks")
		return

	with tempfile.TemporaryDirectory(prefix=f"{session_name}_chunks_") as tmpdir:
		tmp_path = Path(tmpdir)
		specs = export_chunks(audio, bounds, tmp_path, stem)
		# Release large object ASAP
		del audio
		logger.info(f"Exported {len(specs)} chunk files to temp dir")

		all_segments: List[Dict[str, Any]] = []
		per_chunk_results: Dict[int, Dict[str, Any]] = {}

		with cf.ThreadPoolExecutor(max_workers=max_workers) as executor:
			fut_to_chunk = {executor.submit(transcribe_chunk_callable, client, spec): spec for spec in specs}
			total = len(specs)
			done_count = 0
			for fut in cf.as_completed(fut_to_chunk):
				spec = fut_to_chunk[fut]
				result = fut.result()
				per_chunk_results[spec.index] = result
				chunk_json_path = file_out_dir / f"{stem}_chunk_{spec.index:03d}.json"
				write_json(chunk_json_path, result, dry=dry_run, logger=logger)
				if "segments" in result:
					all_segments.extend(result["segments"])
				done_count += 1
				logger.info(f"Progress: {done_count}/{total} chunks saved for {audio_path.name}")

		# Normalize & sort segments
		all_segments.sort(key=lambda s: (s["start"], s["end"]))
		last_end = -1.0
		for seg in all_segments:
			if seg["start"] < last_end:
				seg["start"] = last_end + 1e-4
			if seg["end"] < seg["start"]:
				seg["end"] = seg["start"]
			last_end = seg["end"]

		combined = {
			"source_file": audio_path.name,
			"session": session_name,
			"model": "whisper-1",
			"chunk_sec": chunk_sec,
			"overlap_sec": overlap_sec,
			"duration_sec": duration_sec,
			"segments": all_segments,
			"chunks": [per_chunk_results[i] for i in sorted(per_chunk_results)],
			"errors": [r for r in per_chunk_results.values() if "error" in r]
		}
		write_json(combined_json_path, combined, dry=dry_run, logger=logger)
		logger.info(f"Combined JSON written: {combined_json_path} ({len(all_segments)} segments)")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
	p = argparse.ArgumentParser(
		description="Transcribe TTRPG session audio into JSON (per-chunk + combined).",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter
	)
	p.add_argument("--input", "-i", nargs="*", help="Audio file(s) or directory(ies). If omitted, opens GUI picker.")
	p.add_argument("--transcripts-root", default=None, help="Root folder for transcripts (default: <repo>/dotmm_transcripts)")
	p.add_argument("--logs-root", default=None, help="Root folder for logs (default: <repo>/logs)")
	p.add_argument("--chunk-sec", type=int, default=DEFAULT_CHUNK_SEC)
	p.add_argument("--overlap-sec", type=float, default=DEFAULT_OVERLAP_SEC)
	p.add_argument("--max-workers", type=int, default=MAX_DEFAULT_WORKERS)
	p.add_argument("--force", action="store_true", help="Overwrite existing combined JSON.")
	p.add_argument("--dry-run", action="store_true", help="Simulate only; no files written.")
	p.add_argument("--version", action="store_true", help="Print version and exit.")
	return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
	args = parse_args(argv)
	if args.version:
		print(f"ttrpg_transcribe version {VERSION}")
		return

	script_path = Path(__file__).resolve()
	repo_root = find_repo_root(script_path.parent)
	transcripts_root = Path(args.transcripts_root) if args.transcripts_root else (repo_root / "dotmm_transcripts")
	logs_root = Path(args.logs_root) if args.logs_root else (repo_root / "logs")

	if not check_ffmpeg():
		print("ERROR: ffmpeg not found in PATH. Install ffmpeg and retry.", file=sys.stderr)
		sys.exit(1)

	# Input discovery
	if args.input:
		inputs = discover_audio(args.input)
	else:
		default_root = repo_root
		maybe_raw = repo_root / "dotmm_sessions" / "raw_audio"
		if maybe_raw.exists():
			default_root = maybe_raw
		inputs = gui_pick_inputs(default_root)

	if not inputs:
		print("ERROR: no supported audio inputs found.", file=sys.stderr)
		sys.exit(1)

	session_name = derive_session_name(inputs)
	log_file = logs_root / f"{session_name}.log"
	logger = setup_logger(log_file)

	logger.info(f"Session name: {session_name}")
	logger.info(f"Inputs: {len(inputs)} file(s)")
	for f in inputs:
		logger.info(f"  {f}")

	if args.dry_run:
		logger.info("Dry-run mode active (no files will be written).")

	# API client
	api_key = load_api_key()
	client = build_client(api_key)

	start_all = time.time()
	for audio_path in inputs:
		try:
			process_file(
				client=client,
				audio_path=audio_path,
				out_root=transcripts_root,
				session_name=session_name,
				chunk_sec=args.chunk_sec,
				overlap_sec=args.overlap_sec,
				max_workers=args.max_workers,
				dry_run=args.dry_run,
				force=args.force,
				logger=logger
			)
		except Exception as e:  # noqa: BLE001
			logger.error(f"Failed processing {audio_path.name}: {e}")

	elapsed = time.time() - start_all
	logger.info(f"Finished in {elapsed:.2f}s")
	if args.dry_run:
		logger.info("Dry-run complete.")


if __name__ == "__main__":  # pragma: no cover
	main()

