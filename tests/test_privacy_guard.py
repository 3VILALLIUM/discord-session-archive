"""Regression tests for repository privacy guard secret detection."""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_RELATIVE_PATHS = {
    "powershell": Path("scripts/privacy_guard_check.ps1"),
    "bash": Path("scripts/privacy_guard_check.sh"),
}


def _classic_openai_key() -> str:
    return "sk-" + ("A" * 32)


def _project_openai_key() -> str:
    return "sk-" + "proj-" + ("B" * 32)


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _make_repo_with_guard(tmp_path: Path, script_relative_path: Path, fake_key: str) -> Path:
    repo = tmp_path / "repo"
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / script_relative_path, repo / script_relative_path)

    (repo / "tracked.txt").write_text(f"OPENAI_API_KEY={fake_key}\n", encoding="utf-8")

    _run_git(repo, "init")
    _run_git(repo, "add", script_relative_path.as_posix(), "tracked.txt")
    return repo


def _powershell_command(script_path: Path) -> list[str]:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        pytest.skip("PowerShell is not available")

    command = [executable, "-NoProfile"]
    if platform.system() == "Windows":
        command.extend(["-ExecutionPolicy", "Bypass"])
    command.extend(["-File", str(script_path)])
    return command


def _functional_bash() -> str:
    executable = shutil.which("bash")
    if executable is None:
        pytest.skip("bash is not available")

    probe = subprocess.run(
        [executable, "--version"],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        pytest.skip("bash is not functional in this environment")
    return executable


@pytest.mark.parametrize(
    ("case_name", "fake_key_factory"),
    [
        ("classic", _classic_openai_key),
        ("project", _project_openai_key),
    ],
)
def test_powershell_privacy_guard_blocks_openai_keys(tmp_path: Path, case_name: str, fake_key_factory):
    repo = _make_repo_with_guard(tmp_path, SCRIPT_RELATIVE_PATHS["powershell"], fake_key_factory())

    result = subprocess.run(
        _powershell_command(repo / SCRIPT_RELATIVE_PATHS["powershell"]),
        cwd=repo,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0, f"{case_name} OpenAI key was not blocked"
    assert "possible secret content" in output
    assert "tracked.txt" in output


@pytest.mark.parametrize(
    ("case_name", "fake_key_factory"),
    [
        ("classic", _classic_openai_key),
        ("project", _project_openai_key),
    ],
)
def test_bash_privacy_guard_blocks_openai_keys(tmp_path: Path, case_name: str, fake_key_factory):
    bash = _functional_bash()
    repo = _make_repo_with_guard(tmp_path, SCRIPT_RELATIVE_PATHS["bash"], fake_key_factory())

    result = subprocess.run(
        [bash, SCRIPT_RELATIVE_PATHS["bash"].as_posix()],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0, f"{case_name} OpenAI key was not blocked"
    assert "possible secret content" in output
    assert "tracked.txt" in output
