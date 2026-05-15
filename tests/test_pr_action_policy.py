"""Repository policy invariants for pull request close and merge actions."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_PATH = REPO_ROOT / "AGENTS.md"

REQUIRED_PR_REVIEW_GATE_LINES = (
    "- Closing and merging pull requests are separate, explicit user-authorized actions, never routine cleanup.",
    "- Do not close a pull request unless the user gives an explicit close instruction for that pull request.",
    "- Do not merge a pull request unless the user gives an explicit instruction containing the standalone word `MERGE` for that pull request.",
    '- Do not infer close or merge permission from phrases like "ship it", "looks good", "approved", "done", "superseded", "replace it", "clean up", or "go ahead".',
    "- Do not get clever about this rule. If the exact close or `MERGE` instruction is missing, stop and ask.",
    "- Before inspecting PR details, reviewing comments, changing labels or branches, closing, merging, or otherwise acting on a pull request, first verify GitHub Copilot code review has completed and has been checked.",
    "- The only permitted pre-review action is checking whether GitHub Copilot code review has completed.",
    "- Even with explicit close or `MERGE` instruction, do not close or merge pull requests until GitHub Copilot code review has completed and has been checked.",
    "- If Copilot review is pending, missing, incomplete, or unchecked, do not act on the pull request; wait for review completion and ask the user to proceed once it is complete and checked.",
    "- Before merging, read every pull request conversation, review thread, and comment after GitHub Copilot code review has completed.",
    "- Before merging, address every actionable comment with code, docs, tests, or a documented no-change rationale.",
    "- Before merging, reply to every actionable comment with what was done or why no change was made, then resolve the thread only after it has been addressed and replied to.",
    "- Do not merge while any pull request conversation is unread, unaddressed, unreplied, or unresolved.",
    "- GitHub may auto-close superseded PRs independently, but agents must not proactively close superseded PRs before Copilot review has completed and been checked.",
)

ALLOWED_PR_REVIEW_GATE_LINES = REQUIRED_PR_REVIEW_GATE_LINES + (
    "This section is enforced by:",
    "- `scripts/pr_action_policy_check.ps1`",
    "- `scripts/pr_action_policy_check.sh`",
    "- `.githooks/pre-commit`",
    "- `.githooks/pre-push`",
    "- `.github/workflows/guard-raw-transcripts.yml`",
    "- `tests/test_pr_action_policy.py`",
)


def _pr_review_gate_section() -> list[str]:
    lines = AGENTS_PATH.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("## PR Review Gate") + 1
    except ValueError as exc:
        raise AssertionError("AGENTS.md must include ## PR Review Gate") from exc

    end = next(
        (index for index, line in enumerate(lines[start:], start=start) if line.startswith("## ")),
        len(lines),
    )
    return lines[start:end]


def test_pr_review_gate_requires_explicit_close_and_merge_permission():
    section = _pr_review_gate_section()

    missing = [line for line in REQUIRED_PR_REVIEW_GATE_LINES if line not in section]
    assert missing == []


def test_pr_review_gate_does_not_allow_soft_close_or_merge_exceptions():
    section = _pr_review_gate_section()

    forbidden_lines = [
        line
        for line in section
        if "unless the user explicitly instructs otherwise" in line
        or "has had a chance" in line
        or "had a chance to appear" in line
        or ("Do not close or merge pull requests until" in line and "unless" in line)
    ]
    assert forbidden_lines == []


def test_pr_review_gate_does_not_allow_unchecked_extra_lines():
    section = _pr_review_gate_section()

    unexpected_lines = [line for line in section if line and line not in ALLOWED_PR_REVIEW_GATE_LINES]
    assert unexpected_lines == []
