#!/usr/bin/env python3
"""
discord_session_archive.py

Single-run Craig -> whisper-1 -> cleaned transcript pipeline.

User-facing behavior:
- One paid transcription pass.
- One cleaned transcript plus one run log file in _local/runs/<run_id>/
- Unified name replacement map: _local/config/name_replace_map.json
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
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Match, Optional, Pattern, Sequence, Set, Tuple, TypeVar

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover

    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:  # type: ignore[misc]  # noqa: D103  # pyright: ignore
        return False

AudioSegment: Any = None  # lazy import; set by ensure_pydub_loaded()


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
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        BadRequestError,
        InternalServerError,
        OpenAI,
        OpenAIError,
        RateLimitError,
    )
except ImportError:  # pragma: no cover
    print("ERROR: openai package not installed. pip install openai", file=sys.stderr)
    sys.exit(1)

try:
    from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential
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
DEFAULT_MAX_WORKERS = min(4, os.cpu_count() or 1)  # per-track chunk pool
DEFAULT_TRACK_WORKERS = 4  # track-level pool
DEFAULT_API_WORKERS = 4  # global paid call cap
MAX_DISCOVERY_AUDIO_FILES = 10_000
MAX_DISCOVERY_DIRS = 5_000
MAX_INFO_SEARCH_DIRS = 5_000
MAX_INFO_ASCENT_LEVELS = 4
WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
TRANSIENT_FILE_ACCESS_WINERRORS = {5, 32, 33}
TRANSIENT_FILE_ACCESS_RETRY_ATTEMPTS = 3
TRANSIENT_FILE_ACCESS_RETRY_BASE_DELAY_SEC = 0.75
VERSION = "1.0.0"
NAME_MAP_MODES = ("replace", "none")
QUALITY_FILTER_MODES = ("balanced", "strict", "off")
NAME_REPLACE_MAP_PATH = Path("_local/config/name_replace_map.json")
LANGUAGE_CODE_RE = re.compile(r"^[a-z]{2,3}(?:-[a-z]{2})?$", flags=re.IGNORECASE)
LOW_SIGNAL_ONE_WORD_TOKENS = {
    "ah",
    "eh",
    "er",
    "hmm",
    "huh",
    "mhm",
    "mm",
    "uh",
    "uhh",
    "um",
    "you",
}
LOW_INFORMATION_ONE_WORD_TOKENS = LOW_SIGNAL_ONE_WORD_TOKENS | {
    "a",
    "an",
    "and",
    "but",
    "for",
    "i",
    "in",
    "it",
    "of",
    "ok",
    "okay",
    "on",
    "or",
    "right",
    "so",
    "that",
    "the",
    "this",
    "to",
    "we",
    "yeah",
    "yep",
}
LANGUAGE_NAME_TO_CODE = {
    "arabic": "ar",
    "chinese": "zh",
    "dutch": "nl",
    "english": "en",
    "french": "fr",
    "german": "de",
    "greek": "el",
    "hebrew": "he",
    "hindi": "hi",
    "italian": "it",
    "japanese": "ja",
    "korean": "ko",
    "polish": "pl",
    "portuguese": "pt",
    "russian": "ru",
    "spanish": "es",
    "swedish": "sv",
    "turkish": "tr",
    "ukrainian": "uk",
    "welsh": "cy",
}

LOG_FORMAT = "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
T = TypeVar("T")


@dataclass
class ChunkSpec:
    index: int
    start_ms: int
    end_ms: int
    file_path: Path
    offset_sec: float


@dataclass
class CraigInfoMetadata:
    path: Optional[Path] = None
    guild: Optional[str] = None
    start_time_raw: Optional[str] = None
    start_time_utc: Optional[datetime] = None
    requester: Optional[str] = None
    channel: Optional[str] = None
    tracks: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    raw_fields: Dict[str, List[str]] = field(default_factory=dict)


def find_repo_root(start: Path) -> Path:
    cur = start
    for _ in range(12):
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start


def format_segment_timestamp(seconds: float) -> str:
    return f"{max(0.0, seconds):.2f}s"


def sanitize_label(label: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", label.strip())
    clean = clean.strip("-._")
    return clean or "run"


def sanitize_run_component(text: str) -> str:
    clean = text.strip()
    clean = re.sub(r"[:/\\|?*<>\"']+", "-", clean)
    clean = re.sub(r"\s+", "_", clean)
    clean = re.sub(r"[^A-Za-z0-9._-]+", "", clean)
    clean = re.sub(r"_+", "_", clean)
    clean = clean.strip("._-")
    return clean or "session"


def path_for_display(path: Path) -> str:
    return path.name or str(path)


def is_link_or_reparse_point(path: Path) -> bool:
    try:
        stat_result = path.lstat()
    except OSError:
        return False
    if path.is_symlink():
        return True
    return bool(getattr(stat_result, "st_file_attributes", 0) & WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT)


def find_link_or_reparse_descendant(root: Path) -> Optional[Path]:
    for current_root, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current_root)
        kept_dirs: List[str] = []
        for dirname in sorted(dirs):
            child_dir = current_path / dirname
            if is_link_or_reparse_point(child_dir):
                return child_dir
            kept_dirs.append(dirname)
        dirs[:] = kept_dirs

        for filename in sorted(files):
            child_file = current_path / filename
            if is_link_or_reparse_point(child_file):
                return child_file
    return None


def ensure_safe_force_delete_target(run_dir: Path, output_root: Path) -> None:
    if not run_dir.exists():
        return

    if is_link_or_reparse_point(run_dir):
        raise ValueError(f"refusing --force delete for linked run directory: {path_for_display(run_dir)}")

    resolved_root = output_root.resolve()
    resolved_run_dir = run_dir.resolve()

    if os.path.commonpath([str(resolved_root), str(resolved_run_dir)]) != str(resolved_root):
        raise ValueError(
            f"refusing --force delete outside output root: {path_for_display(resolved_run_dir)}"
        )

    if resolved_run_dir == resolved_root:
        raise ValueError(f"refusing --force delete of output root: {path_for_display(resolved_root)}")

    linked_descendant = find_link_or_reparse_descendant(run_dir)
    if linked_descendant is not None:
        raise ValueError(
            f"refusing --force delete with linked content: {path_for_display(linked_descendant)}"
        )


def strip_discord_snowflake_tokens(text: str) -> str:
    # Remove standalone Discord-like snowflake IDs from human-readable guild names.
    cleaned = re.sub(r"(?<!\d)\d{17,20}(?!\d)", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or text


def normalize_speaker(name: str) -> str:
    text = name.replace("_", " ").replace("-", " ").strip()
    text = re.sub(r"\s+", " ", text)
    # Craig per-track stems can look like "<track_index> <handle> <channel_index>".
    wrapped = re.match(r"^\d+\s+(.+?)\s+\d+$", text)
    if wrapped:
        text = wrapped.group(1).strip()
    return text or "Unknown Speaker"


def normalize_name_map_key(text: str) -> str:
    key = text.replace("_", " ").replace("-", " ").strip().lower()
    # Treat @handle and handle as the same alias key.
    key = re.sub(r"(^|\s)@+", r"\1", key)
    key = re.sub(r"\s+", " ", key)
    return key


def is_name_map_comment_key(text: str) -> bool:
    return text.strip().lower().startswith("__comment")


def map_path_for_mode(mode: str) -> Optional[Path]:
    if mode == "replace":
        return NAME_REPLACE_MAP_PATH
    if mode == "none":
        return None
    return None


def load_name_map(mode: str) -> Dict[str, str]:
    map_path = map_path_for_mode(mode)
    if map_path is None:
        return {}
    if not map_path.exists():
        print(
            f"ERROR: name map file not found for mode '{mode}': {map_path}. "
            "Create it with .\\scripts\\init_local_config.ps1 (PowerShell) or "
            "bash ./scripts/init_local_config.sh and retry.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        payload = json.loads(
            run_with_transient_file_retry(
                lambda: map_path.read_text(encoding="utf-8-sig"),
                logger=logging.getLogger("discord_session_archive"),
                operation=f"Reading name map file {map_path}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed reading name map file {map_path}: {exc}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(payload, dict):
        print(f"ERROR: name map file must be a JSON object: {map_path}", file=sys.stderr)
        sys.exit(1)

    mapped: Dict[str, str] = {}
    for raw_key, raw_value in payload.items():
        if isinstance(raw_key, str) and is_name_map_comment_key(raw_key):
            if not isinstance(raw_value, str):
                print(f"ERROR: name map comment values must be strings: {map_path}", file=sys.stderr)
                sys.exit(1)
            continue
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
    direct = name_map.get(normalize_name_map_key(label))
    if direct:
        return direct

    # Fallback for decorated labels that still contain wrapper tokens.
    best: Optional[Tuple[int, str]] = None
    for alias, replacement in name_map.items():
        pattern = compile_alias_pattern(alias)
        if pattern is None or not pattern.search(label):
            continue
        score = len(alias)
        if best is None or score > best[0]:
            best = (score, replacement)
    return best[1] if best else label


def compile_alias_pattern(alias: str) -> Optional[Pattern[str]]:
    key = normalize_name_map_key(alias)
    if not key:
        return None
    tokens = [re.escape(token) for token in key.split(" ") if token]
    if not tokens:
        return None
    first = rf"@?{tokens[0]}"
    joined = first if len(tokens) == 1 else first + r"[-_\s]*" + r"[-_\s]*".join(tokens[1:])
    return re.compile(rf"(?<![A-Za-z0-9]){joined}(?![A-Za-z0-9])", flags=re.IGNORECASE)


def apply_name_map_to_text(text: str, name_map: Dict[str, str]) -> str:
    if not text or not name_map:
        return text
    updated = text
    for alias, replacement in sorted(name_map.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = compile_alias_pattern(alias)
        if pattern is None:
            continue
        # Use literal replacement so user map values are never treated as regex syntax.
        def literal_sub(_match: Match[str], rep: str = replacement) -> str:
            return rep

        updated = pattern.sub(literal_sub, updated)
    return updated


def apply_name_map_to_metadata(meta: CraigInfoMetadata, name_map: Dict[str, str]) -> CraigInfoMetadata:
    if not name_map:
        return meta
    return CraigInfoMetadata(
        path=meta.path,
        guild=apply_name_map_to_text(meta.guild or "", name_map) or meta.guild,
        start_time_raw=meta.start_time_raw,
        start_time_utc=meta.start_time_utc,
        requester=apply_name_map_to_text(meta.requester or "", name_map) or meta.requester,
        channel=apply_name_map_to_text(meta.channel or "", name_map) or meta.channel,
        tracks=[apply_name_map_to_text(item, name_map) for item in meta.tracks],
        notes=[apply_name_map_to_text(item, name_map) for item in meta.notes],
        raw_fields={key: [apply_name_map_to_text(item, name_map) for item in values] for key, values in meta.raw_fields.items()},
    )


def apply_name_map_to_segments(segments: List[Dict[str, Any]], name_map: Dict[str, str]) -> List[Dict[str, Any]]:
    if not name_map:
        return segments

    mapped_segments: List[Dict[str, Any]] = []
    for segment in segments:
        updated = dict(segment)
        updated["text"] = apply_name_map_to_text(str(segment.get("text", "")), name_map)
        mapped_segments.append(updated)
    return mapped_segments


def clean_text(text: str) -> str:
    stripped = re.sub(r"\s+", " ", text).strip()
    stripped = stripped.replace("`", "'")
    stripped = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]+", "", stripped)
    stripped = stripped.strip()
    if stripped.lower() in {"uh", "um", "er", "ah"}:
        return ""
    return stripped


def normalize_for_dedupe(text: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", collapsed).strip()


def extract_single_word_token(text: str) -> Optional[str]:
    tokens = re.findall(r"[a-z0-9']+", text.lower())
    if len(tokens) != 1:
        return None
    return tokens[0]


def count_word_tokens(text: str) -> int:
    return len(re.findall(r"[a-z0-9']+", text.lower()))


def looks_hallucinated_text(text: str, strict: bool) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return True

    tokens = re.findall(r"[a-z0-9']+", lowered)
    if len(tokens) >= 8:
        counts = Counter(tokens)
        if counts.most_common(1)[0][1] / len(tokens) > (0.50 if strict else 0.65):
            return True
    if len(tokens) >= 10 and len(set(tokens)) <= 2:
        return True

    squashed = re.sub(r"\s+", "", lowered)
    if re.search(r"(..+)\1{3,}", squashed):
        return True

    return False


def segment_passes_quality_filter(segment: Dict[str, Any], mode: str) -> bool:
    if mode == "off":
        return True

    strict = mode == "strict"
    avg_logprob = segment.get("avg_logprob")
    no_speech_prob = segment.get("no_speech_prob")
    compression_ratio = segment.get("compression_ratio")

    if isinstance(no_speech_prob, float) and isinstance(avg_logprob, float):
        if no_speech_prob >= (0.65 if strict else 0.80) and avg_logprob <= (-1.0 if strict else -1.5):
            return False
    if isinstance(compression_ratio, float):
        if compression_ratio >= (2.4 if strict else 3.0):
            return False

    return not looks_hallucinated_text(str(segment.get("text", "")), strict=strict)


def dedupe_overlap_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    for seg in segments:
        if not deduped:
            deduped.append(seg)
            continue
        prev = deduped[-1]
        prev_norm = normalize_for_dedupe(str(prev.get("text", "")))
        curr_norm = normalize_for_dedupe(str(seg.get("text", "")))
        if (
            prev.get("speaker") == seg.get("speaker")
            and prev_norm
            and curr_norm
            and (curr_norm == prev_norm or curr_norm in prev_norm or prev_norm in curr_norm)
            and abs(float(seg.get("start", 0.0)) - float(prev.get("start", 0.0))) <= 2.0
            and float(seg.get("start", 0.0)) <= float(prev.get("end", 0.0)) + 0.75
        ):
            continue
        deduped.append(seg)
    return deduped


def suppress_low_signal_one_word_noise(segments: List[Dict[str, Any]], strict: bool) -> List[Dict[str, Any]]:
    if not segments:
        return segments

    flagged: Set[int] = set()
    cross_speaker_window = 1.25 if not strict else 1.0
    cross_speaker_threshold = 3 if not strict else 2
    same_speaker_window = 6.0 if not strict else 8.0
    overlap_scan_window = 2.5
    overlap_match_padding = 0.2
    overlap_recurrence_threshold = 3 if not strict else 2
    overlap_other_min_words = 3 if not strict else 2
    loop_window = 8.0 if not strict else 10.0
    loop_min_len = 4 if not strict else 3

    by_token: Dict[str, List[Tuple[int, float, str]]] = {}
    by_speaker_token: Dict[Tuple[str, str], List[Tuple[int, float]]] = {}
    by_speaker_one_word: Dict[str, List[Tuple[int, float, str]]] = {}
    for idx, seg in enumerate(segments):
        start = float(seg.get("start", 0.0))
        speaker = str(seg.get("speaker", ""))
        token = extract_single_word_token(str(seg.get("text", "")))
        if token not in LOW_SIGNAL_ONE_WORD_TOKENS:
            if token is not None:
                by_speaker_one_word.setdefault(speaker, []).append((idx, start, token))
            continue
        by_token.setdefault(token, []).append((idx, start, speaker))
        by_speaker_token.setdefault((speaker, token), []).append((idx, start))
        by_speaker_one_word.setdefault(speaker, []).append((idx, start, token))

    # Remove repeated low-signal one-word bursts across multiple speakers.
    for occurrences in by_token.values():
        left = 0
        for right in range(len(occurrences)):
            while occurrences[right][1] - occurrences[left][1] > cross_speaker_window:
                left += 1
            if right - left + 1 < cross_speaker_threshold:
                continue
            speakers = {occurrences[k][2] for k in range(left, right + 1)}
            if len(speakers) < 2:
                continue
            for k in range(left, right + 1):
                flagged.add(occurrences[k][0])

    # Remove repeated low-signal one-word echoes from the same speaker.
    for speaker_occurrences in by_speaker_token.values():
        if len(speaker_occurrences) < 2:
            continue
        repeat_indices: List[int] = [speaker_occurrences[0][0]]
        prev_start = speaker_occurrences[0][1]
        for idx, start in speaker_occurrences[1:]:
            if start - prev_start <= same_speaker_window:
                repeat_indices.append(idx)
            else:
                if len(repeat_indices) >= 2:
                    # Keep the first, suppress repeated echoes.
                    flagged.update(repeat_indices[1:])
                repeat_indices = [idx]
            prev_start = start
        if len(repeat_indices) >= 2:
            flagged.update(repeat_indices[1:])

    # Remove recurrent low-signal one-word stubs when a richer segment
    # from another speaker overlaps the same moment.
    for idx, seg in enumerate(segments):
        token = extract_single_word_token(str(seg.get("text", "")))
        if token not in LOW_SIGNAL_ONE_WORD_TOKENS:
            continue
        speaker = str(seg.get("speaker", ""))
        if len(by_speaker_token.get((speaker, token), [])) < overlap_recurrence_threshold:
            continue
        seg_start = float(seg.get("start", 0.0))
        seg_end = float(seg.get("end", seg_start))
        if seg_end < seg_start:
            seg_end = seg_start

        has_richer_overlap = False
        j = idx - 1
        while j >= 0:
            other = segments[j]
            other_start = float(other.get("start", 0.0))
            if other_start < seg_start - overlap_scan_window:
                break
            if str(other.get("speaker", "")) != speaker:
                other_end = float(other.get("end", other_start))
                if other_end < other_start:
                    other_end = other_start
                overlaps = seg_start <= other_end + overlap_match_padding and other_start <= seg_end + overlap_match_padding
                if overlaps and count_word_tokens(str(other.get("text", ""))) >= overlap_other_min_words:
                    has_richer_overlap = True
                    break
            j -= 1

        if not has_richer_overlap:
            j = idx + 1
            while j < len(segments):
                other = segments[j]
                other_start = float(other.get("start", 0.0))
                if other_start > seg_end + overlap_scan_window:
                    break
                if str(other.get("speaker", "")) != speaker:
                    other_end = float(other.get("end", other_start))
                    if other_end < other_start:
                        other_end = other_start
                    overlaps = seg_start <= other_end + overlap_match_padding and other_start <= seg_end + overlap_match_padding
                    if overlaps and count_word_tokens(str(other.get("text", ""))) >= overlap_other_min_words:
                        has_richer_overlap = True
                        break
                j += 1

        if has_richer_overlap:
            flagged.add(idx)

    # Remove alternating one-word loops (for example: Ah/Five/Ah/Five) when the
    # loop includes at least one known low-signal token.
    def flag_low_signal_loop(loop_entries: List[Tuple[int, float, str]]) -> None:
        if len(loop_entries) < loop_min_len:
            return
        unique_tokens = {item[2] for item in loop_entries}
        if len(unique_tokens) > 2:
            return
        if not any(token in LOW_SIGNAL_ONE_WORD_TOKENS for token in unique_tokens):
            return
        flagged.update(item[0] for item in loop_entries[2:])

    for occurrences in by_speaker_one_word.values():
        if len(occurrences) < loop_min_len:
            continue
        loop_entries: List[Tuple[int, float, str]] = [occurrences[0]]
        prev_start = occurrences[0][1]
        for occurrence in occurrences[1:]:
            idx, start, token = occurrence
            if start - prev_start <= loop_window:
                loop_entries.append((idx, start, token))
            else:
                flag_low_signal_loop(loop_entries)
                loop_entries = [(idx, start, token)]
            prev_start = start
        flag_low_signal_loop(loop_entries)

    if not flagged:
        return segments
    return [seg for idx, seg in enumerate(segments) if idx not in flagged]


def suppress_repeated_short_line_noise(segments: List[Dict[str, Any]], strict: bool) -> List[Dict[str, Any]]:
    if not segments:
        return segments

    # Throttle repeated short-line artifacts from the same speaker while
    # leaving longer natural lines untouched.
    repeat_window_sec = 6.0 if not strict else 8.0
    max_short_duration_sec = 2.6 if not strict else 2.2
    long_one_word_repeat_window_sec = 35.0 if not strict else 50.0
    long_one_word_min_occurrences = 5 if not strict else 4
    strong_one_word_repeat_window_sec = 90.0 if not strict else 120.0
    strong_one_word_min_occurrences = 10 if not strict else 8
    strong_short_phrase_repeat_window_sec = 90.0 if not strict else 120.0
    strong_short_phrase_min_occurrences = 6 if not strict else 5
    strong_one_word_tokens = {"you", "ok", "okay"}
    strong_short_phrases = {"thank you"}
    very_aggressive_token_repeat_windows: Dict[str, float] = {
        "you": 180.0 if not strict else 240.0,
        "ok": 120.0 if not strict else 160.0,
        "okay": 120.0 if not strict else 160.0,
    }
    very_aggressive_token_min_occurrences: Dict[str, int] = {
        "you": 8 if not strict else 6,
        "ok": 10 if not strict else 8,
        "okay": 10 if not strict else 8,
    }
    high_frequency_cap_min_occurrences: Dict[str, int] = {
        "you": 8 if not strict else 6,
        "ok": 7 if not strict else 6,
        "okay": 7 if not strict else 6,
        "thank you": 4 if not strict else 3,
    }
    high_frequency_cap_max_kept: Dict[str, int] = {
        "you": 3,
        "ok": 3,
        "okay": 3,
        "thank you": 2,
    }

    one_word_counts: Dict[Tuple[str, str], int] = {}
    short_line_key_counts: Dict[Tuple[str, str], int] = {}
    for seg in segments:
        speaker = str(seg.get("speaker", ""))
        text = str(seg.get("text", ""))
        norm = normalize_for_dedupe(text)
        if not norm:
            continue

        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        if end < start:
            end = start
        duration = end - start
        words = count_word_tokens(text)

        token_opt = extract_single_word_token(text)
        is_low_info_one_word = token_opt is not None and token_opt in LOW_INFORMATION_ONE_WORD_TOKENS
        is_targeted_phrase = norm in strong_short_phrases and words <= 3
        is_short_line = words <= 4 and duration <= max_short_duration_sec

        if is_short_line or is_low_info_one_word or is_targeted_phrase:
            short_key = (speaker, norm)
            short_line_key_counts[short_key] = short_line_key_counts.get(short_key, 0) + 1

        if token_opt is None:
            continue
        token: str = token_opt
        speaker_token_key: Tuple[str, str] = (speaker, token)
        one_word_counts[speaker_token_key] = one_word_counts.get(speaker_token_key, 0) + 1

    kept: List[Dict[str, Any]] = []
    last_kept_start: Dict[Tuple[str, str], float] = {}
    for seg in segments:
        speaker = str(seg.get("speaker", ""))
        text = str(seg.get("text", ""))
        norm = normalize_for_dedupe(text)
        if not norm:
            continue

        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        if end < start:
            end = start
        duration = end - start
        words = count_word_tokens(text)
        short_token = extract_single_word_token(text)
        is_low_info_one_word = short_token is not None and short_token in LOW_INFORMATION_ONE_WORD_TOKENS
        is_targeted_phrase = norm in strong_short_phrases and words <= 3

        key = (speaker, norm)
        is_short_line = words <= 4 and duration <= max_short_duration_sec
        if is_short_line or is_low_info_one_word or is_targeted_phrase:
            effective_window = repeat_window_sec
            if (
                is_low_info_one_word
                and short_token is not None
                and one_word_counts.get((speaker, short_token), 0) >= long_one_word_min_occurrences
            ):
                effective_window = long_one_word_repeat_window_sec
                if (
                    short_token in strong_one_word_tokens
                    and one_word_counts.get((speaker, short_token), 0) >= strong_one_word_min_occurrences
                ):
                    effective_window = max(effective_window, strong_one_word_repeat_window_sec)
                if (
                    short_token in very_aggressive_token_repeat_windows
                    and one_word_counts.get((speaker, short_token), 0)
                    >= very_aggressive_token_min_occurrences.get(short_token, 999_999)
                ):
                    effective_window = max(
                        effective_window,
                        very_aggressive_token_repeat_windows[short_token],
                    )

            if norm in strong_short_phrases and short_line_key_counts.get(key, 0) >= strong_short_phrase_min_occurrences:
                effective_window = max(effective_window, strong_short_phrase_repeat_window_sec)

            prev = last_kept_start.get(key)
            if prev is not None and start - prev < effective_window:
                continue

        kept.append(seg)
        last_kept_start[key] = start
    if not kept:
        return kept

    capped: List[Dict[str, Any]] = []
    capped_seen: Dict[Tuple[str, str], int] = {}
    for seg in kept:
        speaker = str(seg.get("speaker", ""))
        norm = normalize_for_dedupe(str(seg.get("text", "")))
        if not norm:
            continue
        key = (speaker, norm)
        trigger = high_frequency_cap_min_occurrences.get(norm)
        cap = high_frequency_cap_max_kept.get(norm)
        if trigger is not None and cap is not None and short_line_key_counts.get(key, 0) >= trigger:
            seen = capped_seen.get(key, 0)
            if seen >= cap:
                continue
            capped_seen[key] = seen + 1
        capped.append(seg)
    return capped


def suppress_numeric_counting_noise(segments: List[Dict[str, Any]], strict: bool) -> List[Dict[str, Any]]:
    if not segments:
        return segments

    min_run_len = 14 if not strict else 12
    max_gap_sec = 2.5 if not strict else 3.0
    min_step_like_ratio = 0.65 if not strict else 0.55
    min_value_span = 10 if not strict else 8
    overlap_scan_window = 0.4
    overlap_required_ratio = 0.12 if not strict else 0.10
    very_long_run_len = 30 if not strict else 24
    overlap_min_words = 3

    by_speaker: Dict[str, List[Tuple[int, float, int]]] = {}
    for idx, seg in enumerate(segments):
        token = extract_single_word_token(str(seg.get("text", "")))
        if token is None or not token.isdigit():
            continue
        speaker = str(seg.get("speaker", ""))
        start = float(seg.get("start", 0.0))
        by_speaker.setdefault(speaker, []).append((idx, start, int(token)))

    if not by_speaker:
        return segments

    def has_richer_overlap(idx: int) -> bool:
        seg = segments[idx]
        seg_start = float(seg.get("start", 0.0))
        speaker = str(seg.get("speaker", ""))

        j = idx - 1
        while j >= 0:
            other = segments[j]
            other_start = float(other.get("start", 0.0))
            if seg_start - other_start > overlap_scan_window:
                break
            if str(other.get("speaker", "")) != speaker and count_word_tokens(str(other.get("text", ""))) >= overlap_min_words:
                return True
            j -= 1

        j = idx + 1
        while j < len(segments):
            other = segments[j]
            other_start = float(other.get("start", 0.0))
            if other_start - seg_start > overlap_scan_window:
                break
            if str(other.get("speaker", "")) != speaker and count_word_tokens(str(other.get("text", ""))) >= overlap_min_words:
                return True
            j += 1

        return False

    flagged: Set[int] = set()

    def evaluate_run(run: List[Tuple[int, float, int]]) -> None:
        if len(run) < min_run_len:
            return
        values = [item[2] for item in run]
        pair_count = len(values) - 1
        if pair_count <= 0:
            return
        step_like_pairs = sum(1 for i in range(1, len(values)) if abs(values[i] - values[i - 1]) <= 1)
        step_like_ratio = step_like_pairs / pair_count
        value_span = max(values) - min(values)
        if step_like_ratio < min_step_like_ratio or value_span < min_value_span:
            return

        overlap_hits = sum(1 for item in run if has_richer_overlap(item[0]))
        overlap_required = max(2, int(len(run) * overlap_required_ratio))
        if overlap_hits < overlap_required and len(run) < very_long_run_len:
            return

        # Keep the first token in the run and suppress the repetitive tail.
        flagged.update(item[0] for item in run[1:])

    for occurrences in by_speaker.values():
        if len(occurrences) < min_run_len:
            continue
        run: List[Tuple[int, float, int]] = [occurrences[0]]
        prev_start = occurrences[0][1]
        for occurrence in occurrences[1:]:
            idx, start, number = occurrence
            if start - prev_start <= max_gap_sec:
                run.append((idx, start, number))
            else:
                evaluate_run(run)
                run = [(idx, start, number)]
            prev_start = start
        evaluate_run(run)

    if not flagged:
        return segments
    return [seg for idx, seg in enumerate(segments) if idx not in flagged]


def apply_quality_filter(segments: List[Dict[str, Any]], mode: str) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for seg in segments:
        normalized = clean_text(str(seg.get("text", "")))
        if not normalized:
            continue
        candidate = {**seg, "text": normalized}
        if segment_passes_quality_filter(candidate, mode):
            cleaned.append(candidate)
    cleaned.sort(key=lambda row: (row["start"], row["end"], row["speaker"]))
    if mode != "off":
        cleaned = suppress_low_signal_one_word_noise(cleaned, strict=(mode == "strict"))
        cleaned = suppress_repeated_short_line_noise(cleaned, strict=(mode == "strict"))
        cleaned = suppress_numeric_counting_noise(cleaned, strict=(mode == "strict"))
    return dedupe_overlap_segments(cleaned)


def check_ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg"))


def setup_logger(quiet: bool, log_path: Optional[Path] = None) -> logging.Logger:
    logger = logging.getLogger("discord_session_archive")
    logger.setLevel(logging.INFO)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    if log_path is not None:
        try:
            run_with_transient_file_retry(
                lambda: log_path.parent.mkdir(parents=True, exist_ok=True),
                logger=logger,
                operation=f"Preparing log directory {log_path.parent}",
            )
            fh = run_with_transient_file_retry(
                lambda: logging.FileHandler(log_path, encoding="utf-8"),
                logger=logger,
                operation=f"Opening log file {log_path}",
            )
            fh.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATEFMT))
            logger.addHandler(fh)
        except Exception as exc:  # noqa: BLE001
            print(
                f"WARNING: failed to open log file {path_for_display(log_path)} ({exc}); continuing without file logging.",
                file=sys.stderr,
            )

    if not quiet:
        sh = logging.StreamHandler(stream=sys.stdout)
        sh.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATEFMT))
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
    limit_reached = False
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            print(f"WARNING: path not found: {path_for_display(path)}", file=sys.stderr)
            continue
        if path.is_file():
            if path.suffix.lower() in SUPPORTED_EXTS:
                discovered.append(path)
            continue

        scanned_dirs = 0
        for root, dirs, files in os.walk(path, topdown=True, followlinks=False):
            scanned_dirs += 1
            if scanned_dirs > MAX_DISCOVERY_DIRS:
                print(
                    f"WARNING: directory scan limit reached under: {path_for_display(path)}",
                    file=sys.stderr,
                )
                break

            kept_dirs: List[str] = []
            for dirname in sorted(dirs):
                child_dir = Path(root) / dirname
                if is_link_or_reparse_point(child_dir):
                    print(
                        f"WARNING: skipped linked directory during scan: {path_for_display(child_dir)}",
                        file=sys.stderr,
                    )
                    continue
                kept_dirs.append(dirname)
            dirs[:] = kept_dirs

            for filename in sorted(files):
                child = Path(root) / filename
                if child.suffix.lower() in SUPPORTED_EXTS and child.is_file():
                    discovered.append(child.resolve())
                    if len(discovered) >= MAX_DISCOVERY_AUDIO_FILES:
                        print(
                            f"WARNING: audio discovery limit reached ({MAX_DISCOVERY_AUDIO_FILES}); "
                            "skipping remaining files.",
                            file=sys.stderr,
                        )
                        limit_reached = True
                        break

            if limit_reached:
                break

        if limit_reached:
            break

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


def find_info_txt(input_paths: Sequence[str], audio_files: Sequence[Path]) -> Optional[Path]:
    candidates: List[Path] = []
    for raw in input_paths:
        path = Path(raw).expanduser().resolve()
        if path.is_file() and path.name.lower() == "info.txt":
            candidates.append(path)
        if path.is_dir():
            root_info = path / "info.txt"
            if root_info.exists():
                candidates.append(root_info.resolve())

            scanned_dirs = 0
            found_nested_info = False
            for root, dirs, files in os.walk(path, topdown=True, followlinks=False):
                scanned_dirs += 1
                if scanned_dirs > MAX_INFO_SEARCH_DIRS:
                    print(
                        f"WARNING: info.txt scan limit reached under: {path_for_display(path)}",
                        file=sys.stderr,
                    )
                    break

                kept_dirs: List[str] = []
                for dirname in sorted(dirs):
                    child_dir = Path(root) / dirname
                    if is_link_or_reparse_point(child_dir):
                        continue
                    kept_dirs.append(dirname)
                dirs[:] = kept_dirs

                for filename in sorted(files):
                    if filename.lower() != "info.txt":
                        continue
                    child = Path(root) / filename
                    if child.resolve() != root_info.resolve():
                        candidates.append(child.resolve())
                        found_nested_info = True
                    break

                if found_nested_info:
                    break

    for audio in audio_files:
        cur = audio.parent
        for _ in range(MAX_INFO_ASCENT_LEVELS):
            candidate = cur / "info.txt"
            if candidate.exists():
                candidates.append(candidate.resolve())
                break
            if cur.parent == cur:
                break
            cur = cur.parent

    seen = set()
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        if item.exists() and item.is_file():
            return item
    return None


def normalize_info_key(key: str) -> str:
    return re.sub(r"\s+", " ", key.strip().lower())


def is_note_key(key: str) -> bool:
    normalized = normalize_info_key(key)
    return normalized in {"note", "notes"} or normalized.startswith("note ") or normalized.startswith("notes ")


def looks_like_timestamp_note_line(line: str) -> bool:
    return bool(
        re.match(
            r"^\s*(?:[-*]\s*)?\d{1,2}:\d{2}(?::\d{2})?(?:\s+.*)?$",
            line,
        )
    )


def yaml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def parse_start_time(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None

    maybe_iso = text.replace(" UTC", "+00:00")
    if maybe_iso.endswith("Z"):
        maybe_iso = maybe_iso[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(maybe_iso)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%a %b %d %H:%M:%S %Y", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def parse_craig_info(path: Path) -> CraigInfoMetadata:
    payload = run_with_transient_file_retry(
        lambda: path.read_text(encoding="utf-8-sig", errors="replace"),
        logger=logging.getLogger("discord_session_archive"),
        operation=f"Reading metadata file {path}",
    )
    raw_fields: Dict[str, List[str]] = {}
    current_key: Optional[str] = None
    for line in payload.splitlines():
        if not line.strip():
            current_key = None
            continue

        if current_key and is_note_key(current_key):
            if line.startswith((" ", "\t")) or looks_like_timestamp_note_line(line):
                raw_fields[current_key].append(line.strip())
                continue

        match = re.match(r"^\s*([^:]{1,80}):\s*(.*)$", line)
        if match:
            current_key = normalize_info_key(match.group(1))
            raw_fields.setdefault(current_key, []).append(match.group(2).strip())
            continue
        if current_key and line.startswith((" ", "\t")):
            raw_fields[current_key][-1] = (raw_fields[current_key][-1] + " " + line.strip()).strip()
            continue
        if current_key and is_note_key(current_key):
            raw_fields[current_key].append(line.strip())

    def first_value(*keys: str) -> Optional[str]:
        for key in keys:
            values = raw_fields.get(normalize_info_key(key), [])
            for value in values:
                if value.strip():
                    return value.strip()
        return None

    tracks: List[str] = []
    for key, values in raw_fields.items():
        if key == "tracks":
            for value in values:
                parts = [item.strip() for item in re.split(r"[;,]", value) if item.strip()]
                tracks.extend(parts if parts else [value])
        elif key.startswith("track"):
            tracks.extend([item for item in values if item.strip()])

    notes: List[str] = []
    for key, values in raw_fields.items():
        if is_note_key(key):
            notes.extend([item for item in values if item.strip()])

    start_time_raw = first_value("Start time", "Start", "Started")
    return CraigInfoMetadata(
        path=path,
        guild=first_value("Guild", "Server"),
        start_time_raw=start_time_raw,
        start_time_utc=parse_start_time(start_time_raw),
        requester=first_value("Requester", "Requested by", "Requestor"),
        channel=first_value("Channel", "Voice channel", "Text channel"),
        tracks=tracks,
        notes=notes,
        raw_fields=raw_fields,
    )


def safe_iso_timestamp(dt: datetime) -> str:
    utc = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    utc = utc.astimezone(timezone.utc)
    millis = int(utc.microsecond / 1000)
    return f"{utc.strftime('%Y-%m-%dT%H-%M-%S')}.{millis:03d}Z"


def build_run_id(label: Optional[str], info: CraigInfoMetadata) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if label:
        return f"{sanitize_label(label)}_{stamp}"

    if info.guild:
        guild_source = strip_discord_snowflake_tokens(info.guild)
        guild = sanitize_run_component(guild_source)
        if guild == "session":
            guild = sanitize_run_component(info.guild)
        if info.start_time_utc:
            return f"{guild}_{safe_iso_timestamp(info.start_time_utc)}"
        if info.start_time_raw:
            return f"{guild}_{sanitize_run_component(info.start_time_raw.replace(':', '-'))}"

    return stamp


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


def read_obj_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_language_hint(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    hint = value.strip().lower()
    if not hint or hint == "auto":
        return None
    hint = hint.replace("_", "-")
    if LANGUAGE_CODE_RE.fullmatch(hint):
        return hint
    hint = re.sub(r"\([^)]*\)", "", hint)
    hint = re.sub(r"[\s_-]+", " ", hint).strip()
    if not hint:
        return None
    return LANGUAGE_NAME_TO_CODE.get(hint)


def is_language_hint_error(exc: Exception) -> bool:
    text = str(exc).lower()
    if "language" not in text:
        return False
    return any(token in text for token in ("invalid", "unsupported", "not a valid", "must be", "iso"))


def parse_segment_obj(obj: Any, offset: float) -> Dict[str, Any]:
    start_raw = parse_float(read_obj_value(obj, "start", 0.0)) or 0.0
    end_raw = parse_float(read_obj_value(obj, "end", start_raw)) or start_raw
    text = str(read_obj_value(obj, "text", "")).strip()
    return {
        "start": start_raw + offset,
        "end": end_raw + offset,
        "text": text,
        "avg_logprob": parse_float(read_obj_value(obj, "avg_logprob")),
        "no_speech_prob": parse_float(read_obj_value(obj, "no_speech_prob")),
        "compression_ratio": parse_float(read_obj_value(obj, "compression_ratio")),
    }


def should_retry_openai_error(exc: BaseException) -> bool:
    if not isinstance(exc, OpenAIError):
        return False
    if isinstance(exc, BadRequestError):
        return False
    if isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)):
        return True
    if isinstance(exc, APIStatusError):
        status_code = getattr(exc, "status_code", None)
        return isinstance(status_code, int) and status_code >= 500
    return False


def is_transient_file_access_error(exc: BaseException) -> bool:
    if not isinstance(exc, OSError):
        return False
    winerror = getattr(exc, "winerror", None)
    if isinstance(winerror, int) and winerror in TRANSIENT_FILE_ACCESS_WINERRORS:
        return True
    errno_value = getattr(exc, "errno", None)
    if errno_value == 13:
        return True
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "access is denied",
            "permission denied",
            "being used by another process",
            "sharing violation",
            "access denied",
        )
    )


def run_with_transient_file_retry(
    action: Callable[[], T],
    *,
    logger: logging.Logger,
    operation: str,
    attempts: int = TRANSIENT_FILE_ACCESS_RETRY_ATTEMPTS,
    base_delay_sec: float = TRANSIENT_FILE_ACCESS_RETRY_BASE_DELAY_SEC,
) -> T:
    if attempts < 1:
        attempts = 1
    for attempt in range(1, attempts + 1):
        try:
            return action()
        except Exception as exc:  # noqa: BLE001
            if not is_transient_file_access_error(exc) or attempt >= attempts:
                raise
            delay = base_delay_sec * attempt
            logger.warning(
                "%s hit transient file access error (%s). Retry %d/%d in %.2fs.",
                operation,
                exc,
                attempt,
                attempts - 1,
                delay,
            )
            time.sleep(delay)
    raise RuntimeError("Retry helper exhausted without returning.")


def read_chunk_bytes(path: Path) -> bytes:
    return run_with_transient_file_retry(
        lambda: path.read_bytes(),
        logger=logging.getLogger("discord_session_archive"),
        operation=f"Reading chunk file {path.name}",
    )


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    retry=retry_if_exception(should_retry_openai_error),
)
def call_whisper(
    client: OpenAI,
    chunk: ChunkSpec,
    api_semaphore: threading.BoundedSemaphore,
    language: Optional[str],
) -> Dict[str, Any]:
    payload = read_chunk_bytes(chunk.file_path)
    request_args: Dict[str, Any] = {
        "model": "whisper-1",
        "file": (chunk.file_path.name, payload, "audio/flac"),
        "response_format": "verbose_json",
    }
    if language:
        request_args["language"] = language

    with api_semaphore:
        response = client.audio.transcriptions.create(**request_args)

    segments_raw = read_obj_value(response, "segments", []) or []
    response_language = read_obj_value(response, "language")

    segments = [parse_segment_obj(seg, chunk.offset_sec) for seg in segments_raw]
    return {
        "chunk_file": chunk.file_path.name,
        "offset_sec": chunk.offset_sec,
        "duration_sec": (chunk.end_ms - chunk.start_ms) / 1000.0,
        "language": str(response_language).strip() if response_language else None,
        "segments": segments,
    }


def select_dominant_language(values: List[str]) -> Optional[str]:
    candidates = [val.strip().lower() for val in values if val and val.strip()]
    if not candidates:
        return None
    return Counter(candidates).most_common(1)[0][0]


def call_whisper_with_language_fallback(
    client: OpenAI,
    chunk: ChunkSpec,
    api_semaphore: threading.BoundedSemaphore,
    language: Optional[str],
    logger: logging.Logger,
) -> Dict[str, Any]:
    try:
        return call_whisper(client, chunk, api_semaphore, language=language)
    except Exception as exc:  # noqa: BLE001
        if language and is_language_hint_error(exc):
            logger.warning(
                "Chunk %s rejected language hint '%s'; retrying without explicit language.",
                chunk.file_path.name,
                language,
            )
            return call_whisper(client, chunk, api_semaphore, language=None)
        raise


def add_result_segments(
    track_segments: List[Dict[str, Any]],
    result: Dict[str, Any],
    speaker: str,
    source_file: str,
) -> None:
    for segment in result.get("segments", []):
        if not segment.get("text"):
            continue
        track_segments.append(
            {
                "start": segment["start"],
                "end": segment["end"],
                "speaker": speaker,
                "text": segment["text"],
                "source_file": source_file,
                "avg_logprob": segment.get("avg_logprob"),
                "no_speech_prob": segment.get("no_speech_prob"),
                "compression_ratio": segment.get("compression_ratio"),
                "language": result.get("language"),
            }
        )


def transcribe_track(
    client: Optional[OpenAI],
    audio_path: Path,
    name_map: Dict[str, str],
    chunk_sec: int,
    overlap_sec: float,
    max_workers: int,
    language: str,
    dry_run: bool,
    api_semaphore: threading.BoundedSemaphore,
    logger: logging.Logger,
) -> Dict[str, Any]:
    speaker = apply_name_map_to_speaker(normalize_speaker(audio_path.stem), name_map)
    ensure_pydub_loaded()
    if AudioSegment is None:  # pragma: no cover
        raise RuntimeError("Audio backend unavailable after pydub initialization.")
    audio = run_with_transient_file_retry(
        lambda: AudioSegment.from_file(str(audio_path)),
        logger=logger,
        operation=f"Loading track {audio_path.name}",
    )
    duration_ms = len(audio)
    duration_sec = duration_ms / 1000.0

    bounds = compute_chunks(duration_ms, int(chunk_sec * 1000), int(overlap_sec * 1000))
    logger.info("Track %s loaded (%.2fs), %d chunks", audio_path.name, duration_sec, len(bounds))

    if dry_run:
        return {
            "source_file": audio_path.name,
            "speaker": speaker,
            "duration_sec": duration_sec,
            "segments": [],
            "errors": [],
            "planned_chunks": len(bounds),
        }
    if client is None:
        raise RuntimeError("OpenAI client is required for non-dry runs.")

    with tempfile.TemporaryDirectory(prefix="discord_session_archive_chunks_") as tmp:
        temp_dir = Path(tmp)
        _audio_ref = audio  # local alias so lambda is not invalidated by del
        specs = run_with_transient_file_retry(
            lambda: export_chunks(_audio_ref, bounds, temp_dir, audio_path.stem),
            logger=logger,
            operation=f"Exporting chunks for {audio_path.name}",
        )
        del audio

        all_segments: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        observed_languages: List[str] = []

        warmup_specs: List[ChunkSpec] = []
        worker_specs = list(specs)
        worker_language: Optional[str]

        if language == "auto" and specs:
            warmup_specs = specs[: min(2, len(specs))]
            worker_specs = specs[len(warmup_specs) :]
            worker_language = None
        else:
            worker_language = language

        for warmup in warmup_specs:
            try:
                result = call_whisper(client, warmup, api_semaphore, language=None)
                add_result_segments(all_segments, result, speaker, audio_path.name)
                if result.get("language"):
                    observed_languages.append(str(result["language"]))
            except Exception as exc:  # noqa: BLE001
                errors.append({"chunk_file": warmup.file_path.name, "error": f"{exc.__class__.__name__}: {exc}"})

        if language == "auto":
            dominant = select_dominant_language(observed_languages)
            if dominant:
                mapped = normalize_language_hint(dominant)
                if mapped:
                    worker_language = mapped
                    logger.info(
                        "Track %s language auto-detected as '%s' (using hint '%s')",
                        audio_path.name,
                        dominant,
                        mapped,
                    )
                else:
                    worker_language = None
                    logger.info(
                        "Track %s language auto-detected as '%s' (no safe hint mapping; keeping auto)",
                        audio_path.name,
                        dominant,
                    )

        progress_step = max(1, len(worker_specs) // 5)
        with cf.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {
                executor.submit(
                    call_whisper_with_language_fallback,
                    client,
                    spec,
                    api_semaphore,
                    worker_language,
                    logger,
                ): spec
                for spec in worker_specs
            }
            done = len(warmup_specs)
            total = len(specs)
            for future in cf.as_completed(future_to_chunk):
                spec = future_to_chunk[future]
                try:
                    result = future.result()
                    add_result_segments(all_segments, result, speaker, audio_path.name)
                except Exception as exc:  # noqa: BLE001
                    errors.append({"chunk_file": spec.file_path.name, "error": f"{exc.__class__.__name__}: {exc}"})
                done += 1
                if done == total or done % progress_step == 0:
                    logger.info("Track %s progress: %d/%d chunks", audio_path.name, done, total)
        if errors:
            logger.warning("Track %s completed with %d chunk errors.", audio_path.name, len(errors))

    all_segments.sort(key=lambda row: (row["start"], row["end"], row["speaker"]))
    return {
        "source_file": audio_path.name,
        "speaker": speaker,
        "duration_sec": duration_sec,
        "segments": all_segments,
        "errors": errors,
        "planned_chunks": len(bounds),
    }


def render_transcript_markdown(
    run_id: str,
    segments: List[Dict[str, Any]],
    metadata: CraigInfoMetadata,
    track_count: int,
    quality_filter: str,
    language_mode: str,
    runtime_sec: float,
    error_count: int,
) -> str:
    lines: List[str] = ["---", f"session: {run_id}"]
    if metadata.guild:
        lines.append(f"guild: {yaml_quote(metadata.guild)}")
    if metadata.channel:
        lines.append(f"channel: {yaml_quote(metadata.channel)}")
    if metadata.requester:
        lines.append(f"requester: {yaml_quote(metadata.requester)}")
    if metadata.start_time_raw:
        lines.append(f"start_time: {yaml_quote(metadata.start_time_raw)}")
    if metadata.path:
        lines.append(f"source_info_file: {yaml_quote(metadata.path.name)}")
    if metadata.tracks:
        lines.append("tracks:")
        for track in metadata.tracks:
            lines.append(f"  - {yaml_quote(track)}")
    if metadata.notes:
        lines.append("craig_notes:")
        for note in metadata.notes:
            lines.append(f"  - {yaml_quote(note)}")
    lines.append("tags: [transcription]")
    lines.append("---")
    lines.append("")
    lines.append("summary: |")
    lines.append("  Auto-generated transcript cleaned in single-run newbie mode.")
    lines.append(
        "  "
        + f"tracks={track_count}, segments={len(segments)}, errors={error_count}, "
        + f"quality_filter={quality_filter}, language={language_mode}, runtime_sec={runtime_sec:.2f}."
    )
    lines.append("")

    for seg in segments:
        lines.append(f"[{format_segment_timestamp(float(seg['start']))} {seg['speaker']}] {seg['text']}")
    lines.append("")
    return "\n".join(lines)


def write_text(path: Path, content: str, logger: Optional[logging.Logger] = None) -> None:
    active_logger = logger or logging.getLogger("discord_session_archive")
    run_with_transient_file_retry(
        lambda: path.parent.mkdir(parents=True, exist_ok=True),
        logger=active_logger,
        operation=f"Preparing output directory {path.parent}",
    )
    run_with_transient_file_retry(
        lambda: path.write_text(content, encoding="utf-8"),
        logger=active_logger,
        operation=f"Writing output file {path.name}",
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Single-run Craig -> whisper-1 -> cleaned transcript pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", "-i", nargs="+", help="Craig export folder(s) or audio file path(s).")
    parser.add_argument(
        "--pick-folder",
        action="store_true",
        help="Open a folder picker for input (also used automatically when --input is omitted).",
    )
    parser.add_argument("--output-root", default="_local/runs", help="Output root directory.")
    parser.add_argument("--label", help="Optional label to include in run folder name.")
    parser.add_argument(
        "--name-map-mode",
        default="replace",
        help="Name map mode: replace (use _local/config/name_replace_map.json) or none.",
    )
    parser.add_argument("--chunk-sec", type=int, default=DEFAULT_CHUNK_SEC, help="Chunk duration in seconds.")
    parser.add_argument("--overlap-sec", type=float, default=DEFAULT_OVERLAP_SEC, help="Chunk overlap in seconds.")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, help="Per-track chunk worker count.")
    parser.add_argument("--track-workers", type=int, default=DEFAULT_TRACK_WORKERS, help="Parallel track worker count.")
    parser.add_argument("--api-workers", type=int, default=DEFAULT_API_WORKERS, help="Global max concurrent paid API calls.")
    parser.add_argument("--language", default="auto", help="Language mode: auto or explicit language code (for example: en).")
    parser.add_argument("--quality-filter", choices=QUALITY_FILTER_MODES, default="balanced", help="Quality filtering profile.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing run directory.")
    parser.add_argument("--dry-run", action="store_true", help="Preview work without writing files.")
    parser.add_argument("--quiet", action="store_true", help="Suppress console logs.")
    parser.add_argument("--version", action="store_true", help="Print version and exit.")

    parser.add_argument("--clean", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--notebooklm", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args(argv)

    if args.clean or args.json or args.notebooklm:
        parser.error(
            "Removed flags detected. --clean/--json/--notebooklm were removed. "
            "The CLI now always writes one cleaned transcript Markdown file and one run log Markdown file."
        )
    if args.name_map_mode in {"handle", "real"}:
        parser.error(
            "Removed name-map mode detected. Use --name-map-mode replace with "
            "_local/config/name_replace_map.json."
        )
    if args.name_map_mode not in NAME_MAP_MODES:
        parser.error("Invalid --name-map-mode. Supported values are: replace, none.")

    for key in ("chunk_sec", "max_workers", "track_workers", "api_workers"):
        if int(getattr(args, key)) < 1:
            parser.error(f"--{key.replace('_', '-')} must be >= 1.")
    if float(args.overlap_sec) < 0:
        parser.error("--overlap-sec must be >= 0.")
    if args.language != "auto":
        normalized_language = normalize_language_hint(args.language)
        if not normalized_language:
            parser.error(
                "--language must be 'auto' or a supported ISO-639 language code (for example: en, es, cy)."
            )
        args.language = normalized_language

    return args


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
    if args.pick_folder or not input_paths:
        input_paths.append(str(pick_folder_via_gui(repo_root)))

    audio_files = discover_audio(input_paths)
    if not audio_files:
        print("ERROR: no supported audio files found.", file=sys.stderr)
        sys.exit(1)

    info_path = find_info_txt(input_paths, audio_files)
    metadata = parse_craig_info(info_path) if info_path else CraigInfoMetadata()
    mapped_metadata = apply_name_map_to_metadata(metadata, name_map)

    run_id = build_run_id(args.label, metadata)
    output_root = Path(args.output_root).resolve()
    run_dir = output_root / run_id
    transcript_path = run_dir / f"{run_id}_transcript.md"
    log_path = run_dir / f"{run_id}_log.md"

    if run_dir.exists() and not args.force and not args.dry_run:
        print(f"ERROR: output run directory exists: {run_dir} (use --force)", file=sys.stderr)
        sys.exit(1)
    if run_dir.exists() and args.force and not args.dry_run:
        try:
            ensure_safe_force_delete_target(run_dir=run_dir, output_root=output_root)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        run_with_transient_file_retry(
            lambda: shutil.rmtree(run_dir),
            logger=logging.getLogger("discord_session_archive"),
            operation=f"Removing existing run directory {run_dir}",
        )
    if not args.dry_run:
        run_with_transient_file_retry(
            lambda: run_dir.mkdir(parents=True, exist_ok=True),
            logger=logging.getLogger("discord_session_archive"),
            operation=f"Creating run directory {run_dir}",
        )

    logger = setup_logger(quiet=args.quiet, log_path=None if args.dry_run else log_path)
    logger.info("Run ID: %s", run_id)
    if not args.dry_run:
        logger.info("Log file: %s", log_path)
    logger.info("Inputs: %d audio file(s)", len(audio_files))
    logger.info("Name map mode: %s", args.name_map_mode)
    logger.info("Quality filter: %s", args.quality_filter)
    logger.info("Language mode: %s", args.language)
    logger.info(
        "Workers: track=%d, per-track chunks=%d, global-api=%d",
        args.track_workers,
        args.max_workers,
        args.api_workers,
    )

    start = time.time()
    api_semaphore = threading.BoundedSemaphore(value=args.api_workers)

    client: Optional[OpenAI] = None
    if not args.dry_run:
        api_key = load_api_key()
        client = build_client(api_key)

    tracks: List[Dict[str, Any]] = []
    with cf.ThreadPoolExecutor(max_workers=args.track_workers) as executor:
        future_to_track = {
            executor.submit(
                transcribe_track,
                client,
                audio_file,
                name_map,
                args.chunk_sec,
                args.overlap_sec,
                args.max_workers,
                args.language,
                args.dry_run,
                api_semaphore,
                logger,
            ): audio_file
            for audio_file in audio_files
        }
        for future in cf.as_completed(future_to_track):
            audio_file = future_to_track[future]
            try:
                track = future.result()
                tracks.append(track)
                logger.info("Track complete: %s (%d segments)", audio_file.name, len(track["segments"]))
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed processing %s: %s", audio_file.name, exc)
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

    filtered_segments = apply_quality_filter(all_segments, mode=args.quality_filter)
    render_segments = apply_name_map_to_segments(filtered_segments, name_map)
    runtime = time.time() - start

    if args.dry_run:
        logger.info("[dry-run] Would write %s", transcript_path)
        logger.info(
            "[dry-run] Raw segments=%d, cleaned segments=%d, errors=%d",
            len(all_segments),
            len(filtered_segments),
            len(all_errors),
        )
        logger.info("Finished in %.2fs", runtime)
        return

    transcript_md = render_transcript_markdown(
        run_id=run_id,
        segments=render_segments,
        metadata=mapped_metadata,
        track_count=len(tracks),
        quality_filter=args.quality_filter,
        language_mode=args.language,
        runtime_sec=runtime,
        error_count=len(all_errors),
    )
    write_text(transcript_path, transcript_md, logger=logger)
    logger.info("Wrote %s", transcript_path)
    logger.info("Finished in %.2fs", runtime)
    print(f"Transcript run complete: {transcript_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
