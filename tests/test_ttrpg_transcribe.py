"""Tests for ttrpg_transcribe.py

These tests mock external dependencies (OpenAI, pydub/ffmpeg) so they run fast and offline.
Run with: pytest -q
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys
import pytest  # type: ignore

# Locate script
SCRIPT_PATH = Path(__file__).resolve().parent.parent / "campaigns" / "dungeon_of_the_mad_mage" / "dotmm_scripts" / "ttrpg_transcribe.py"
spec = importlib.util.spec_from_file_location("ttrpg_transcribe", SCRIPT_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)  # type: ignore


class FakeAudioSegment:
    """Minimal stand‑in for pydub.AudioSegment supporting slicing, len(), and export."""

    def __init__(self, duration_ms: int):
        self._duration = duration_ms

    def __len__(self):
        return self._duration

    def __getitem__(self, item):
        if isinstance(item, slice):
            start = item.start or 0
            stop = item.stop or self._duration
            return FakeAudioSegment(stop - start)
        return self

    def export(self, dst, format="flac"):
        with open(dst, "wb") as f:
            f.write(b"fakedata")


class FakeOpenAIClient:
    class audio:
        class transcriptions:
            @staticmethod
            def create(model, file, response_format):  # noqa: D401
                return SimpleNamespace(segments=[
                    {"start": 0.0, "end": 1.5, "text": "Hello"},
                    {"start": 1.5, "end": 3.0, "text": "World"},
                ])


@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch):
    monkeypatch.setattr(mod, "check_ffmpeg", lambda: True)
    monkeypatch.setattr(mod, "AudioSegment", SimpleNamespace(from_file=lambda p: FakeAudioSegment(12_345)))
    monkeypatch.setattr(mod, "build_client", lambda api_key: FakeOpenAIClient())
    monkeypatch.setattr(mod, "load_api_key", lambda: "sk-test")


def test_compute_chunks_basic():
    chunks = mod.compute_chunks(duration_ms=10_000, chunk_ms=4_000, overlap_ms=1_000)
    assert chunks == [(0, 4000), (3000, 7000), (6000, 10000)]


def test_session_name_from_audio_folder(tmp_path: Path):
    folder = tmp_path / "session_010_audio"
    folder.mkdir()
    dummy = folder / "file.mp3"
    dummy.write_bytes(b"fake")
    inputs = [dummy]
    name = mod.derive_session_name(inputs)
    assert name == "session_010_transcript"


def test_process_file_creates_outputs(tmp_path: Path):
    audio_file = tmp_path / "adventure.mp3"
    audio_file.write_bytes(b"fake")
    out_root = tmp_path / "out"
    session = "adventure_transcript"
    logger = mod.setup_logger(tmp_path / "test.log", verbose=False)
    mod.process_file(
        client=FakeOpenAIClient(),
        audio_path=audio_file,
        out_root=out_root,
        session_name=session,
        chunk_sec=5,
        overlap_sec=1.0,
        max_workers=2,
        dry_run=False,
        force=True,
        logger=logger,
    )
    stem_dir = out_root / session / audio_file.stem
    combined = stem_dir / f"{audio_file.stem}.json"
    assert combined.exists()
    data = json.loads(combined.read_text(encoding="utf-8"))
    assert data["segments"]
    chunk_files = sorted(stem_dir.glob(f"{audio_file.stem}_chunk_*.json"))
    assert chunk_files


def test_dry_run_writes_nothing(tmp_path: Path):
    audio_file = tmp_path / "quest.mp3"
    audio_file.write_bytes(b"fake")
    out_root = tmp_path / "out"
    logger = mod.setup_logger(tmp_path / "dry.log", verbose=False)
    mod.process_file(
        client=FakeOpenAIClient(),
        audio_path=audio_file,
        out_root=out_root,
        session_name="quest_transcript",
        chunk_sec=10,
        overlap_sec=2.0,
        max_workers=1,
        dry_run=True,
        force=False,
        logger=logger,
    )
    assert not (out_root / "quest_transcript").exists()
