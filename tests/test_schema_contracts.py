"""Schema contract validation tests for profile, job payload, and final output artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "schemas"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(schema_name: str) -> Draft202012Validator:
    schema = _load_json(SCHEMAS_DIR / schema_name)
    return Draft202012Validator(schema)


@pytest.mark.parametrize(
    ("schema_name", "fixture_name"),
    [
        ("asr_profile.schema.json", "profiles/valid_profile_registry.json"),
        ("transcribe_job.schema.json", "jobs/valid_transcribe_job.json"),
        ("final_output_contract.schema.json", "outputs/valid_final_output_contract.json"),
    ],
)
def test_valid_schema_fixtures_pass(schema_name: str, fixture_name: str):
    payload = _load_json(FIXTURES_DIR / fixture_name)
    errors = sorted(_validator(schema_name).iter_errors(payload), key=lambda error: error.path)
    assert errors == []


@pytest.mark.parametrize(
    ("schema_name", "fixture_name"),
    [
        ("asr_profile.schema.json", "profiles/invalid_profile_registry_mip_false.json"),
        ("transcribe_job.schema.json", "jobs/invalid_transcribe_job_policy_false.json"),
        ("final_output_contract.schema.json", "outputs/invalid_final_output_contract_privacy_false.json"),
    ],
)
def test_invalid_schema_fixtures_fail(schema_name: str, fixture_name: str):
    payload = _load_json(FIXTURES_DIR / fixture_name)
    errors = sorted(_validator(schema_name).iter_errors(payload), key=lambda error: error.path)
    assert errors != []
