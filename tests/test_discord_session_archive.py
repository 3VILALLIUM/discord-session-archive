"""Tests for src/discord_session_archive.py.

These tests mock external dependencies (OpenAI, pydub/ffmpeg) so they run fast and offline.
Run with: pytest -q
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest  # type: ignore

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "src" / "discord_session_archive.py"
spec = importlib.util.spec_from_file_location("discord_session_archive", SCRIPT_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)  # type: ignore


class FakeAudioSegment:
    """Small stand-in for pydub.AudioSegment supporting len/slice/export."""

    def __init__(self, duration_ms: int):
        self._duration = duration_ms

    def __len__(self):
        return self._duration

    def __getitem__(self, item):
        if isinstance(item, slice):
            start = item.start or 0
            stop = item.stop or self._duration
            return FakeAudioSegment(max(0, stop - start))
        return self

    def export(self, dst, format="flac"):
        with open(dst, "wb") as handle:
            handle.write(b"fakechunk")


class FakeOpenAIClient:
    class audio:
        class transcriptions:
            @staticmethod
            def create(model, file, response_format):
                return SimpleNamespace(
                    segments=[
                        {"start": 0.0, "end": 1.0, "text": "hello"},
                        {"start": 1.0, "end": 2.0, "text": "world"},
                    ]
                )


@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch):
    monkeypatch.setattr(mod, "check_ffmpeg", lambda: True)
    monkeypatch.setattr(mod, "load_api_key", lambda: "sk-test")
    monkeypatch.setattr(mod, "build_client", lambda api_key: FakeOpenAIClient())
    monkeypatch.setattr(mod, "AudioSegment", SimpleNamespace(from_file=lambda p: FakeAudioSegment(11_000)))


def test_compute_chunks_basic():
    chunks = mod.compute_chunks(duration_ms=10_000, chunk_ms=4_000, overlap_ms=1_000)
    assert chunks == [(0, 4000), (3000, 7000), (6000, 10000)]


def test_discover_audio_recursive(tmp_path: Path):
    folder = tmp_path / "craig_export"
    folder.mkdir()
    nested = folder / "nested"
    nested.mkdir()
    (folder / "speaker_a.mp3").write_bytes(b"a")
    (nested / "speaker_b.wav").write_bytes(b"b")
    (nested / "notes.txt").write_text("ignore me", encoding="utf-8")
    results = mod.discover_audio([str(folder)])
    assert len(results) == 2
    assert all(p.suffix.lower() in {".mp3", ".wav"} for p in results)


def test_main_writes_expected_outputs(tmp_path: Path):
    input_dir = tmp_path / "craig_export"
    input_dir.mkdir()
    (input_dir / "speaker_one.mp3").write_bytes(b"a")
    (input_dir / "speaker_two.mp3").write_bytes(b"b")

    out_root = tmp_path / "out"
    mod.main(
        [
            "--input",
            str(input_dir),
            "--output-root",
            str(out_root),
            "--clean",
            "--json",
            "--notebooklm",
            "--label",
            "demo",
            "--force",
            "--quiet",
        ]
    )

    run_dirs = list(out_root.glob("demo_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "transcript.md").exists()
    assert (run_dir / "transcript.cleaned.md").exists()
    assert (run_dir / "transcript.json").exists()
    assert (run_dir / "notebooklm.md").exists()

    payload = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))
    assert payload["engine"] == "whisper-1"
    assert payload["segments"]


def test_main_dry_run_writes_nothing(tmp_path: Path):
    input_dir = tmp_path / "craig_export"
    input_dir.mkdir()
    (input_dir / "speaker_one.mp3").write_bytes(b"a")

    out_root = tmp_path / "out"
    mod.main(
        [
            "--input",
            str(input_dir),
            "--output-root",
            str(out_root),
            "--dry-run",
            "--quiet",
        ]
    )

    assert not out_root.exists()
