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


def write_map(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_normalize_name_map_key():
    assert mod.normalize_name_map_key("  Speaker-One__A  ") == "speaker one a"


def test_load_name_map_valid(tmp_path: Path, monkeypatch):
    map_path = tmp_path / "handle_map.json"
    write_map(map_path, {"speaker one": "Player A", "SPEAKER-TWO": "Player B"})
    monkeypatch.setattr(mod, "HANDLE_MAP_PATH", map_path)

    loaded = mod.load_name_map("handle")
    assert loaded == {"speaker one": "Player A", "speaker two": "Player B"}


def test_load_name_map_missing_file_fails(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(mod, "HANDLE_MAP_PATH", tmp_path / "missing.json")
    with pytest.raises(SystemExit):
        mod.load_name_map("handle")


def test_load_name_map_invalid_object_fails(tmp_path: Path, monkeypatch):
    map_path = tmp_path / "handle_map.json"
    write_map(map_path, ["not", "an", "object"])
    monkeypatch.setattr(mod, "HANDLE_MAP_PATH", map_path)
    with pytest.raises(SystemExit):
        mod.load_name_map("handle")


def test_load_name_map_non_string_entry_fails(tmp_path: Path, monkeypatch):
    map_path = tmp_path / "handle_map.json"
    write_map(map_path, {"speaker one": 123})
    monkeypatch.setattr(mod, "HANDLE_MAP_PATH", map_path)
    with pytest.raises(SystemExit):
        mod.load_name_map("handle")


def test_load_name_map_tolerates_utf8_bom(tmp_path: Path, monkeypatch):
    """Regression test: load_name_map() must handle UTF-8 BOM (EF BB BF) gracefully."""
    map_path = tmp_path / "handle_map.json"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    # Write JSON with UTF-8 BOM prefix
    bom = b'\xef\xbb\xbf'
    json_bytes = json.dumps({"speaker one": "Player A", "SPEAKER-TWO": "Player B"}).encode("utf-8")
    map_path.write_bytes(bom + json_bytes)
    monkeypatch.setattr(mod, "HANDLE_MAP_PATH", map_path)

    loaded = mod.load_name_map("handle")
    assert loaded == {"speaker one": "Player A", "speaker two": "Player B"}



def test_load_name_map_ignores_reserved_comment_keys(tmp_path: Path, monkeypatch):
    map_path = tmp_path / "handle_map.json"
    write_map(
        map_path,
        {
            "__comment_1": "Use this file for discord-handle aliases.",
            "__comment_2": "Keys are aliases; values are preferred display names.",
            "speaker one": "Player A",
        },
    )
    monkeypatch.setattr(mod, "HANDLE_MAP_PATH", map_path)

    loaded = mod.load_name_map("handle")
    assert loaded == {"speaker one": "Player A"}


def test_load_name_map_non_string_comment_value_fails(tmp_path: Path, monkeypatch):
    map_path = tmp_path / "handle_map.json"
    write_map(
        map_path,
        {
            "__comment_1": 123,
            "speaker one": "Player A",
        },
    )
    monkeypatch.setattr(mod, "HANDLE_MAP_PATH", map_path)
    with pytest.raises(SystemExit):
        mod.load_name_map("handle")


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


def test_main_name_map_mode_none_preserves_default_speakers(tmp_path: Path):
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
            "--name-map-mode",
            "none",
            "--json",
            "--force",
            "--quiet",
        ]
    )

    run_dir = next(out_root.iterdir())
    payload = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))
    assert {t["speaker"] for t in payload["tracks"]} == {"speaker one", "speaker two"}
    assert {s["speaker"] for s in payload["segments"]} == {"speaker one", "speaker two"}
    assert {s["text"] for s in payload["segments"]} == {"hello", "world"}


def test_main_name_map_mode_handle_applies_mapping(tmp_path: Path, monkeypatch):
    input_dir = tmp_path / "craig_export"
    input_dir.mkdir()
    (input_dir / "speaker_one.mp3").write_bytes(b"a")
    (input_dir / "speaker_two.mp3").write_bytes(b"b")

    handle_map = tmp_path / "config" / "handle_map.json"
    write_map(handle_map, {"speaker one": "AlphaHandle", "speaker two": "BetaHandle"})
    monkeypatch.setattr(mod, "HANDLE_MAP_PATH", handle_map)

    out_root = tmp_path / "out"
    mod.main(
        [
            "--input",
            str(input_dir),
            "--output-root",
            str(out_root),
            "--name-map-mode",
            "handle",
            "--json",
            "--force",
            "--quiet",
        ]
    )

    run_dir = next(out_root.iterdir())
    payload = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))
    assert {t["speaker"] for t in payload["tracks"]} == {"AlphaHandle", "BetaHandle"}
    assert {s["speaker"] for s in payload["segments"]} == {"AlphaHandle", "BetaHandle"}
    assert {s["text"] for s in payload["segments"]} == {"hello", "world"}


def test_main_name_map_mode_real_applies_mapping(tmp_path: Path, monkeypatch):
    input_dir = tmp_path / "craig_export"
    input_dir.mkdir()
    (input_dir / "speaker_one.mp3").write_bytes(b"a")
    (input_dir / "speaker_two.mp3").write_bytes(b"b")

    real_map = tmp_path / "config" / "realname_map.json"
    write_map(real_map, {"speaker one": "Alice Carter", "speaker two": "Bob Rivera"})
    monkeypatch.setattr(mod, "REALNAME_MAP_PATH", real_map)

    out_root = tmp_path / "out"
    mod.main(
        [
            "--input",
            str(input_dir),
            "--output-root",
            str(out_root),
            "--name-map-mode",
            "real",
            "--json",
            "--force",
            "--quiet",
        ]
    )

    run_dir = next(out_root.iterdir())
    payload = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))
    assert {t["speaker"] for t in payload["tracks"]} == {"Alice Carter", "Bob Rivera"}
    assert {s["speaker"] for s in payload["segments"]} == {"Alice Carter", "Bob Rivera"}
    assert {s["text"] for s in payload["segments"]} == {"hello", "world"}


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
