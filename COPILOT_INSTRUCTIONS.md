# COPILOT_INSTRUCTIONS.md

Custom review instructions for GitHub Copilot code review on `deepgram-neon-craigbot`-style workflows.

## 1) Purpose

Use these instructions to review PRs for correctness, privacy, and operational safety.
The project processes Discord audio with Craig + Deepgram + Neon. The review standard is:

- **privacy-first**
- **fail-closed policy enforcement**
- **idempotent processing**
- **minimal, proven solutions**

If there is tension between feature velocity and privacy/policy safety, prioritize safety.

---

## 2) Non-Negotiable Invariants

Treat each item as a merge blocker if violated.

1. **Deepgram MIP gate is mandatory**
   - Every Deepgram request must include and enforce `mip_opt_out=true`.
   - No alternate egress path may bypass the policy adapter.

2. **Privacy contract is mandatory**
   - Final output must not expose:
     - guild/server name
     - raw Discord handles
     - unreplaced spoken names
   - Export must fail-closed when privacy validation fails.

3. **Diarization must be explicit**
   - Default behavior for single-track inputs is `diarize=false`.
   - Diyarization requires explicit profile/flag opt-in.

4. **Idempotency must hold**
   - Equivalent processing keys cannot produce duplicate outputs.
   - Profile/version changes must intentionally produce distinct runs.

5. **State transitions must be legal**
   - Illegal job transitions are rejected.
   - Retryable and terminal failure paths are distinct and deterministic.

---

## 3) Review Priorities (in order)

1. **Policy/privacy safety**
2. **Correctness/data integrity**
3. **Reliability and failure behavior**
4. **Test completeness**
5. **Complexity/scope control**

When in doubt, comment on earlier priorities first.

---

## 4) Files and Areas That Deserve Extra Scrutiny

Focus extra attention on:

- request construction / API clients
- export generators and sanitizers
- schema files and migration scripts
- queue/job orchestration and retry logic
- tests that claim fail-closed behavior
- CI workflows and required-check logic

---

## 5) Required Review Checks

For each relevant PR, verify all applicable checks below.

## A) Policy Enforcement Checks

- Confirm `mip_opt_out=true` is present in effective outbound request parameters.
- Confirm callers cannot override policy to false.
- Confirm behavior is fail-closed when policy configuration is missing/invalid.
- Flag any direct SDK/API calls that avoid the policy adapter.

## B) Privacy Contract Checks

- Confirm sanitization runs before final export.
- Confirm privacy checks include guild name, Discord handles, spoken-name replacement/fallback.
- Confirm export is blocked on privacy check failure.
- Confirm no debug/log output introduces raw sensitive identifiers.

## C) Idempotency Checks

- Confirm dedupe key includes required dimensions (session/audio/profile/version).
- Confirm retries cannot create duplicates.
- Confirm unique constraints or equivalent protections are present where appropriate.

## D) State-Machine Checks

- Confirm legal transitions are explicit.
- Confirm illegal transitions fail loudly.
- Confirm retryable failures requeue with bounded attempts.
- Confirm terminal failures stop and surface diagnostics.

## E) CI/Test Checks

- Confirm required tests exist for changed behavior.
- Confirm both positive and negative cases are present.
- Confirm schema changes include fixture and regression-test updates.
- Confirm required checks remain merge-blocking.

---

## 6) Anti-Patterns to Flag

Always flag these as issues:

- policy-by-convention instead of enforced gate
- privacy check as warning-only
- hidden defaults that change diarization behavior
- broad refactor unrelated to task
- adding dependencies/frameworks without clear need
- reducing test strictness to pass CI
- adding skipped/xfail tests without rationale

---

## 7) Guidance on “Fancy vs Proven”

Prefer:

1. Existing repo scripts/workflows
2. Minimal extension of existing patterns
3. New abstraction only with strong justification

If a PR introduces a novel pattern, request explicit rationale and tradeoff analysis.

---

## 8) Severity and Commenting Standard

Every substantive review comment should include:

1. **Severity**: `critical`, `high`, `medium`, `low`
2. **What is wrong** (specific and localizable)
3. **Why it matters** (risk)
4. **What to change** (actionable fix)

Mark as **must-fix before merge** when severity is `critical` or `high`.

---

## 9) Recommended Comment Templates

### Critical policy/privacy issue

- **Severity:** critical
- **Issue:** [specific file/path + behavior]
- **Risk:** Could allow policy/privacy bypass in production.
- **Required fix:** Enforce fail-closed gate in [module], add negative regression test.

### High reliability issue

- **Severity:** high
- **Issue:** Retry/state logic can produce duplicate or stuck jobs.
- **Risk:** Data corruption / operational instability.
- **Required fix:** Add transition guard and idempotency protection, plus tests.

### Medium maintainability issue

- **Severity:** medium
- **Issue:** Introduces unnecessary abstraction without measurable benefit.
- **Risk:** Increased complexity and drift from proven behavior.
- **Suggested fix:** Reuse existing pattern/script and reduce moving parts.

---

## 10) Required Praise Behavior

When the PR does things well, acknowledge it explicitly, especially:

- minimal, focused diffs
- stronger fail-closed behavior
- clear negative tests
- schema/fixture/test alignment
- reduced privacy risk

This helps reinforce desired engineering behavior.

---

## 11) Merge-Blocking Checklist for Copilot

Request changes if any item below is true:

- Any Deepgram path can egress without `mip_opt_out=true`
- Any export path can bypass privacy validation
- Any prohibited identifier can reach final output
- Any required test category is missing for changed behavior
- Any idempotency/state transition regression risk is unaddressed
- Required CI checks are removed, weakened, or non-blocking

---

## 12) Scope Discipline

Review should not request broad unrelated refactors.
Recommend the smallest change that satisfies policy/privacy/correctness.

---

## 13) Final Review Outcome Guidance

Use one of these explicit outcomes:

- **Approve**: all invariants hold, risk acceptable, tests sufficient.
- **Comment**: non-blocking improvements.
- **Request changes**: any invariant/risk gap remains.

For request-changes outcomes, enumerate must-fix items as a checklist.
