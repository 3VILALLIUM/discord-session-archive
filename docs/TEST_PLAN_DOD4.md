# DoD #4 Test Plan: Acceptance Tests Defined and Enforced

## Scope
This DoD covers the required acceptance test suite for policy enforcement, privacy gating, idempotency, state transitions, and schema contract regression.

Out of scope for this DoD: feature expansion, analytics quality tuning, and infrastructure scaling.

## Locked Constraints
- Craig single-track mixed audio is the default input mode.
- Diarization is off by default and opt-in only by explicit profile/flag.
- No Deepgram request can be sent without `mip_opt_out=true`.
- Final exports must be sanitized and blocked on privacy violations.
- Idempotency must prevent duplicate outputs for equivalent processing keys.

## Required Test Categories

### 1) Policy Enforcement
- `test_policy_blocks_missing_mip_opt_out`
- `test_policy_blocks_false_mip_opt_out`
- `test_policy_allows_true_mip_opt_out`
- `test_policy_rejects_direct_deepgram_client_bypass`

Acceptance:
- Request construction fails before network egress when `mip_opt_out` is missing or false.
- No bypass call paths exist outside the policy adapter.

### 2) Privacy Transformation + Export Gate
- `test_export_blocked_on_guild_name_presence`
- `test_export_blocked_on_discord_handle_presence`
- `test_export_blocked_on_unreplaced_spoken_name`
- `test_export_allows_fallback_participant_name`
- `test_export_requires_all_privacy_flags_true`

Acceptance:
- Export hard-fails on each privacy violation fixture.
- Export succeeds only when all required privacy checks pass.

### 3) Idempotency
- `test_idempotency_dedupes_same_key`
- `test_idempotency_allows_new_run_when_profile_changes`
- `test_idempotency_allows_new_run_when_normalizer_version_changes`

Acceptance:
- Re-running an identical key does not create duplicate output artifacts.
- Key-dimension changes generate distinct runs.

### 4) State Machine
- `test_state_machine_allows_legal_transitions`
- `test_state_machine_rejects_illegal_transition`
- `test_state_machine_retryable_failure_requeues`
- `test_state_machine_terminal_failure_stops`

Acceptance:
- Illegal transitions are rejected with explicit errors.
- Retryable and terminal failures follow separate, deterministic paths.

### 5) Schema Contract Regression
- Existing: `tests/test_schema_contracts.py`
- Additions:
  - `test_schema_rejects_profile_without_privacy_contract`
  - `test_schema_rejects_job_with_policy_override_false`
  - `test_schema_rejects_output_with_privacy_flag_false`

Acceptance:
- Valid fixtures pass; invalid fixtures fail; CI blocks regressions.

## Fixture Plan
- `tests/fixtures/schemas/profiles/` for profile validity and policy constraints.
- `tests/fixtures/schemas/jobs/` for job payload gating.
- `tests/fixtures/schemas/outputs/` for export contract and privacy flags.
- `tests/fixtures/privacy/` for text-level leakage scenarios.
- `tests/fixtures/state_machine/` for transition path assertions.

## Execution Order
1. Add policy enforcement tests.
2. Add privacy gate tests.
3. Add idempotency tests.
4. Add state machine tests.
5. Extend schema regression tests and fixtures.
6. Mark CI jobs as required checks.

## CI Required Checks
- `pytest tests/test_schema_contracts.py`
- `pytest tests/test_policy_enforcement.py`
- `pytest tests/test_privacy_gate.py`
- `pytest tests/test_idempotency.py`
- `pytest tests/test_state_machine.py`

## DoD #4 Acceptance Criteria
DoD #4 is complete only when all conditions below are true:
1. All required test files exist and execute in CI.
2. Each test category has positive and negative cases.
3. Policy tests prove fail-closed behavior for `mip_opt_out`.
4. Privacy tests prove export blocking on leakage.
5. Idempotency tests prove no duplicate artifacts on equivalent keys.
6. State tests prove legal-only transitions and correct failure handling.
7. Schema regression tests cover required policy/privacy constraints.

## Automatic Fail Conditions
- Any acceptance test category is missing.
- Any CI required check is optional or absent.
- Any policy/privacy test can be bypassed by configuration.
- Any known invalid fixture passes.

## DoD #4 Final Gate
### GO
- All required test suites green.
- Required fixtures present.
- CI checks are mandatory and enforced.

### NO-GO
- Any required suite missing or failing.
- Any bypass path for policy/privacy accepted.
- Any regression in schema contract validation.
