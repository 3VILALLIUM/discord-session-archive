"""Tests for src/discord_session_archive.py.

These tests mock external dependencies (OpenAI, pydub/ffmpeg) so they run fast and offline.
Run with: pytest -q
"""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
import time
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
            def create(model, file, response_format, language=None):  # noqa: ARG004
                return SimpleNamespace(
                    language=language or "en",
                    segments=[
                        {
                            "start": 0.0,
                            "end": 1.0,
                            "text": "hello",
                            "avg_logprob": -0.2,
                            "no_speech_prob": 0.05,
                            "compression_ratio": 1.0,
                        },
                        {
                            "start": 1.0,
                            "end": 2.0,
                            "text": "world",
                            "avg_logprob": -0.2,
                            "no_speech_prob": 0.05,
                            "compression_ratio": 1.0,
                        },
                    ],
                )


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch, tmp_path: Path):
    map_path = tmp_path / "config" / "name_replace_map.json"
    write_json(map_path, {"speaker one": "Speaker One", "@speaker-one": "Speaker One"})
    monkeypatch.setattr(mod, "NAME_REPLACE_MAP_PATH", map_path)
    monkeypatch.setattr(mod, "check_ffmpeg", lambda: True)
    monkeypatch.setattr(mod, "load_api_key", lambda: "sk-test")
    monkeypatch.setattr(mod, "build_client", lambda api_key: FakeOpenAIClient())
    monkeypatch.setattr(mod, "AudioSegment", SimpleNamespace(from_file=lambda p: FakeAudioSegment(11_000)))


def test_normalize_name_map_key():
    assert mod.normalize_name_map_key("  Speaker-One__A  ") == "speaker one a"


def test_normalize_language_hint_accepts_codes_and_names():
    assert mod.normalize_language_hint("EN") == "en"
    assert mod.normalize_language_hint("english") == "en"
    assert mod.normalize_language_hint("Welsh") == "cy"
    assert mod.normalize_language_hint("auto") is None
    assert mod.normalize_language_hint("unknown-language") is None


def test_call_whisper_with_language_fallback_retries_without_hint(tmp_path: Path, monkeypatch):
    chunk_path = tmp_path / "chunk.flac"
    chunk_path.write_bytes(b"fake")
    chunk = mod.ChunkSpec(index=0, start_ms=0, end_ms=1000, file_path=chunk_path, offset_sec=0.0)
    seen_languages = []

    def fake_call_whisper(client, chunk_spec, api_semaphore, language):  # noqa: ARG001
        seen_languages.append(language)
        if language == "english":
            raise RuntimeError("invalid language parameter")
        return {
            "chunk_file": chunk_spec.file_path.name,
            "offset_sec": 0.0,
            "duration_sec": 1.0,
            "language": "en",
            "segments": [{"start": 0.0, "end": 1.0, "text": "hello"}],
        }

    monkeypatch.setattr(mod, "call_whisper", fake_call_whisper)
    logger = mod.setup_logger(quiet=True)
    result = mod.call_whisper_with_language_fallback(
        client=SimpleNamespace(),
        chunk=chunk,
        api_semaphore=threading.BoundedSemaphore(1),
        language="english",
        logger=logger,
    )

    assert seen_languages == ["english", None]
    assert result["segments"]


def test_transcribe_track_auto_language_uses_safe_iso_hint(tmp_path: Path, monkeypatch):
    audio_path = tmp_path / "3-3vilallium_0.aac"
    audio_path.write_bytes(b"audio")
    seen_languages = []

    def fake_call_whisper(client, chunk_spec, api_semaphore, language):  # noqa: ARG001
        seen_languages.append(language)
        return {
            "chunk_file": chunk_spec.file_path.name,
            "offset_sec": chunk_spec.offset_sec,
            "duration_sec": (chunk_spec.end_ms - chunk_spec.start_ms) / 1000.0,
            "language": "english",
            "segments": [{"start": chunk_spec.offset_sec, "end": chunk_spec.offset_sec + 0.5, "text": "hello"}],
        }

    monkeypatch.setattr(mod, "call_whisper", fake_call_whisper)
    logger = mod.setup_logger(quiet=True)

    track = mod.transcribe_track(
        client=SimpleNamespace(),
        audio_path=audio_path,
        name_map={},
        chunk_sec=2,
        overlap_sec=0,
        max_workers=2,
        language="auto",
        dry_run=False,
        api_semaphore=threading.BoundedSemaphore(4),
        logger=logger,
    )

    assert seen_languages[:2] == [None, None]
    assert all(value == "en" for value in seen_languages[2:])
    assert track["segments"]


def test_load_name_map_replace_valid(tmp_path: Path, monkeypatch):
    map_path = tmp_path / "name_replace_map.json"
    write_json(map_path, {"speaker one": "Player A", "SPEAKER-TWO": "Player B"})
    monkeypatch.setattr(mod, "NAME_REPLACE_MAP_PATH", map_path)

    loaded = mod.load_name_map("replace")
    assert loaded == {"speaker one": "Player A", "speaker two": "Player B"}


def test_load_name_map_none_returns_empty():
    assert mod.load_name_map("none") == {}


def test_load_name_map_missing_file_fails(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(mod, "NAME_REPLACE_MAP_PATH", tmp_path / "missing.json")
    with pytest.raises(SystemExit):
        mod.load_name_map("replace")


def test_parse_craig_info_and_run_id_from_info(tmp_path: Path):
    info = tmp_path / "info.txt"
    info.write_text(
        "\n".join(
            [
                "Guild: Dungeon of The Mad Mage",
                "Start time: 2026-02-13T02:13:52.421Z",
                "Requester: @speaker-one",
                "Channel: voice-main",
                "Tracks: speaker_one, speaker_two",
                "Notes: test run",
            ]
        ),
        encoding="utf-8",
    )
    parsed = mod.parse_craig_info(info)
    run_id = mod.build_run_id(None, parsed)

    assert parsed.guild == "Dungeon of The Mad Mage"
    assert parsed.start_time_utc is not None
    assert run_id.startswith("Dungeon_of_The_Mad_Mage_2026-02-13T02-13-52.421Z")
    assert ":" not in run_id


def test_build_run_id_strips_guild_numeric_id_suffix(tmp_path: Path):
    info = tmp_path / "info.txt"
    info.write_text(
        "\n".join(
            [
                "Guild: Dungeon of The Mad Mage 1039186847059943424",
                "Start time: 2026-02-13T02:13:52.421Z",
            ]
        ),
        encoding="utf-8",
    )
    parsed = mod.parse_craig_info(info)
    run_id = mod.build_run_id(None, parsed)
    assert run_id.startswith("Dungeon_of_The_Mad_Mage_2026-02-13T02-13-52.421Z")
    assert "1039186847059943424" not in run_id


def test_build_run_id_label_precedence_over_info(tmp_path: Path):
    info = tmp_path / "info.txt"
    info.write_text(
        "\n".join(
            [
                "Guild: Dungeon of The Mad Mage",
                "Start time: 2026-02-13T02:13:52.421Z",
            ]
        ),
        encoding="utf-8",
    )
    parsed = mod.parse_craig_info(info)
    run_id = mod.build_run_id("my-label", parsed)
    assert run_id.startswith("my-label_")


def test_build_run_id_falls_back_when_info_missing_fields():
    run_id = mod.build_run_id(None, mod.CraigInfoMetadata())
    assert run_id
    assert "_" in run_id


def test_main_writes_transcript_and_named_log_file(tmp_path: Path):
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
            "--label",
            "demo",
            "--force",
            "--quiet",
        ]
    )

    run_dirs = list(out_root.glob("demo_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    files = sorted(path.name for path in run_dir.iterdir() if path.is_file())
    assert files == [f"{run_dir.name}_log.md", f"{run_dir.name}_transcript.md"]
    assert not (run_dir / "run.log").exists()


def test_main_defaults_to_file_picker_when_input_omitted(tmp_path: Path, monkeypatch):
    input_dir = tmp_path / "craig_export"
    input_dir.mkdir()
    (input_dir / "speaker_one.mp3").write_bytes(b"a")
    monkeypatch.setattr(mod, "pick_folder_via_gui", lambda initial_dir: input_dir)

    out_root = tmp_path / "out"
    mod.main(
        [
            "--output-root",
            str(out_root),
            "--label",
            "picker",
            "--force",
            "--quiet",
        ]
    )

    run_dirs = list(out_root.glob("picker_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / f"{run_dir.name}_transcript.md").exists()
    assert (run_dir / f"{run_dir.name}_log.md").exists()


def test_main_applies_unified_map_to_speaker_and_metadata(tmp_path: Path, monkeypatch):
    input_dir = tmp_path / "craig_export"
    input_dir.mkdir()
    (input_dir / "speaker_one.mp3").write_bytes(b"a")
    (input_dir / "info.txt").write_text(
        "\n".join(
            [
                "Guild: Demo Guild",
                "Start time: 2026-02-13T02:13:52.421Z",
                "Requester: @speaker-one",
                "Channel: dev-room",
                "Tracks: speaker_one",
                "Notes: @speaker-one joined late",
            ]
        ),
        encoding="utf-8",
    )
    map_path = tmp_path / "config" / "name_replace_map.json"
    write_json(map_path, {"speaker one": "Alpha", "@speaker-one": "Alpha"})
    monkeypatch.setattr(mod, "NAME_REPLACE_MAP_PATH", map_path)

    out_root = tmp_path / "out"
    mod.main(
        [
            "--input",
            str(input_dir),
            "--output-root",
            str(out_root),
            "--force",
            "--quiet",
        ]
    )

    run_dir = next(out_root.iterdir())
    transcript = (run_dir / f"{run_dir.name}_transcript.md").read_text(encoding="utf-8")
    assert 'requester: "Alpha"' in transcript
    assert "tracks:" in transcript
    assert '  - "Alpha"' in transcript
    assert "craig_notes:" in transcript
    assert '  - "Alpha joined late"' in transcript
    assert "[0.00s Alpha] hello" in transcript


def test_parse_craig_info_captures_note_section_lines(tmp_path: Path):
    info = tmp_path / "info.txt"
    info.write_text(
        "\n".join(
            [
                "Guild: Test Guild",
                "Notes:",
                "00:12 Session start recap",
                "01:03:22 Boss reveal",
                "Note 3: Post-fight debrief",
            ]
        ),
        encoding="utf-8",
    )
    parsed = mod.parse_craig_info(info)
    assert "00:12 Session start recap" in parsed.notes
    assert "01:03:22 Boss reveal" in parsed.notes
    assert "Post-fight debrief" in parsed.notes


def test_removed_output_flags_fail_with_clear_error(tmp_path: Path, capsys):
    input_dir = tmp_path / "craig_export"
    input_dir.mkdir()
    (input_dir / "speaker_one.mp3").write_bytes(b"a")
    with pytest.raises(SystemExit):
        mod.main(["--input", str(input_dir), "--clean"])
    err = capsys.readouterr().err
    assert "Removed flags detected" in err


def test_removed_name_map_modes_fail_with_clear_error(tmp_path: Path, capsys):
    input_dir = tmp_path / "craig_export"
    input_dir.mkdir()
    (input_dir / "speaker_one.mp3").write_bytes(b"a")
    with pytest.raises(SystemExit):
        mod.main(["--input", str(input_dir), "--name-map-mode", "handle"])
    err = capsys.readouterr().err
    assert "Removed name-map mode detected" in err


def test_quality_filter_balanced_vs_off():
    noisy = {
        "start": 0.0,
        "end": 1.0,
        "speaker": "Alpha",
        "text": "test test test test test test test test",
        "avg_logprob": -2.0,
        "no_speech_prob": 0.95,
        "compression_ratio": 3.5,
    }
    clean = {
        "start": 2.0,
        "end": 3.0,
        "speaker": "Alpha",
        "text": "all right let's start",
        "avg_logprob": -0.2,
        "no_speech_prob": 0.05,
        "compression_ratio": 1.0,
    }
    assert len(mod.apply_quality_filter([noisy, clean], mode="off")) == 2
    assert len(mod.apply_quality_filter([noisy, clean], mode="balanced")) == 1


def test_quality_filter_keeps_single_one_word_when_not_repeated():
    single = {
        "start": 0.0,
        "end": 0.5,
        "speaker": "Alpha",
        "text": "you",
        "avg_logprob": -0.2,
        "no_speech_prob": 0.05,
        "compression_ratio": 1.0,
    }
    full = {
        "start": 1.0,
        "end": 2.0,
        "speaker": "Beta",
        "text": "ready to go",
        "avg_logprob": -0.2,
        "no_speech_prob": 0.05,
        "compression_ratio": 1.0,
    }
    filtered = mod.apply_quality_filter([single, full], mode="balanced")
    assert any(seg["text"] == "you" for seg in filtered)
    assert any(seg["text"] == "ready to go" for seg in filtered)


def test_quality_filter_suppresses_repeated_one_word_burst_across_speakers():
    burst = [
        {
            "start": 10.00,
            "end": 10.30,
            "speaker": "A",
            "text": "you",
            "avg_logprob": -0.2,
            "no_speech_prob": 0.05,
            "compression_ratio": 1.0,
        },
        {
            "start": 10.10,
            "end": 10.35,
            "speaker": "B",
            "text": "you",
            "avg_logprob": -0.2,
            "no_speech_prob": 0.05,
            "compression_ratio": 1.0,
        },
        {
            "start": 10.20,
            "end": 10.40,
            "speaker": "C",
            "text": "you",
            "avg_logprob": -0.2,
            "no_speech_prob": 0.05,
            "compression_ratio": 1.0,
        },
    ]
    real = {
        "start": 11.0,
        "end": 12.0,
        "speaker": "DM",
        "text": "let's begin",
        "avg_logprob": -0.2,
        "no_speech_prob": 0.05,
        "compression_ratio": 1.0,
    }
    filtered = mod.apply_quality_filter([*burst, real], mode="balanced")
    assert all(seg["text"] != "you" for seg in filtered)
    assert any(seg["text"] == "let's begin" for seg in filtered)


def test_quality_filter_suppresses_repeated_one_word_echo_same_speaker():
    segments = [
        {
            "start": 20.0,
            "end": 20.2,
            "speaker": "Alpha",
            "text": "you",
            "avg_logprob": -0.2,
            "no_speech_prob": 0.05,
            "compression_ratio": 1.0,
        },
        {
            "start": 20.8,
            "end": 21.0,
            "speaker": "Alpha",
            "text": "you",
            "avg_logprob": -0.2,
            "no_speech_prob": 0.05,
            "compression_ratio": 1.0,
        },
        {
            "start": 22.0,
            "end": 22.5,
            "speaker": "Beta",
            "text": "yes",
            "avg_logprob": -0.2,
            "no_speech_prob": 0.05,
            "compression_ratio": 1.0,
        },
    ]
    filtered = mod.apply_quality_filter(segments, mode="balanced")
    # First one-word utterance can remain, repeated echo should be suppressed.
    assert len([seg for seg in filtered if seg["text"] == "you"]) == 1
    assert any(seg["text"] == "yes" for seg in filtered)


def test_quality_filter_strict_is_at_least_as_aggressive_as_balanced():
    noisy = {
        "start": 0.0,
        "end": 1.0,
        "speaker": "Alpha",
        "text": "hello hello hello hello hello hello hello hello",
        "avg_logprob": -1.2,
        "no_speech_prob": 0.7,
        "compression_ratio": 2.5,
    }
    clean = {
        "start": 2.0,
        "end": 3.0,
        "speaker": "Alpha",
        "text": "ready to start",
        "avg_logprob": -0.2,
        "no_speech_prob": 0.05,
        "compression_ratio": 1.0,
    }
    balanced = mod.apply_quality_filter([noisy, clean], mode="balanced")
    strict = mod.apply_quality_filter([noisy, clean], mode="strict")
    assert len(strict) <= len(balanced)


def test_global_api_worker_cap_is_enforced(tmp_path: Path, monkeypatch):
    class TrackingClient:
        class audio:
            class transcriptions:
                current = 0
                peak = 0
                lock = threading.Lock()

                @staticmethod
                def create(model, file, response_format, language=None):  # noqa: ARG004
                    with TrackingClient.audio.transcriptions.lock:
                        TrackingClient.audio.transcriptions.current += 1
                        TrackingClient.audio.transcriptions.peak = max(
                            TrackingClient.audio.transcriptions.peak,
                            TrackingClient.audio.transcriptions.current,
                        )
                    time.sleep(0.02)
                    with TrackingClient.audio.transcriptions.lock:
                        TrackingClient.audio.transcriptions.current -= 1
                    return SimpleNamespace(
                        language=language or "en",
                        segments=[{"start": 0.0, "end": 1.0, "text": "hello"}],
                    )

    monkeypatch.setattr(mod, "build_client", lambda api_key: TrackingClient())
    monkeypatch.setattr(mod, "AudioSegment", SimpleNamespace(from_file=lambda p: FakeAudioSegment(6_000)))

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
            "--chunk-sec",
            "2",
            "--overlap-sec",
            "0",
            "--track-workers",
            "4",
            "--max-workers",
            "4",
            "--api-workers",
            "1",
            "--force",
            "--quiet",
        ]
    )

    assert TrackingClient.audio.transcriptions.peak <= 1
