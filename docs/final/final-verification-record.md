# Final Verification Record

- 기록 시각: 2026-09-14 KST
- 검증 기준: `a4748954fa39a44171d52030ff286c2dafeda2b0` + 아래 narrow finalization working-tree changes
- checkout: detached `HEAD`
- 환경: Linux 5.15.0-191-generic x86_64, Python 3.10.12, pytest 9.1.1
- 상태 기준: [Final Status & Freeze Criteria](./final-status-and-freeze-criteria.md)

이 문서는 freeze candidate revision에서 실제로 수행한 검증과 아직 수행하지 않은 항목을 분리한다. Historical 결과는 current PASS로 승격하지 않는다.

## 1. Regression

| Check ID | Check | Required for Freeze? | Actual | Status |
| --- | --- | --- | --- | --- |
| `CORE-REG-01` | `python3 scripts/check_prepare_regression.py --strict` | yes | 25 fixtures: pass=25, warn=0, fail=0 | `PASS` |
| `CORE-REG-02` | `python3 scripts/check_stage_dryrun_regression.py --strict` | yes | pass=19, warn=0, fail=0 | `PASS` |
| `CORE-REG-03` | Core pytest, external benchmark files excluded | yes | 837 passed | `PASS` |
| `EXT-BENCH-01` | External CRS/CSIC benchmark pytest family | yes | 173 passed, 25 skipped | `PASS` |

`CORE-REG-03` uses the tracked deterministic fixture `data/eval/prepare_candidate_selection_jobs12_fixture.json`. The fixture preserves Job 12 provenance and only contains the request IDs and filtered reasons required by the evaluation contract. `runs/jobs/12/` is absent in this checkout, so the passing result does not depend on gitignored runtime artifacts.

`EXT-BENCH-01` was run with:

- disposable venv: `/tmp/final-benchmark-venv.17aUPI/venv`
- dependencies installed only there: `PyYAML==6.0.2`, `pytest==9.1.1`
- repository package visibility: `PYTHONPATH` set to the verified checkout root
- `/opt/web_log_analysis/.venv` was not modified and still has no PyYAML
- no DB access, provider call, or runtime Job execution was part of this benchmark check

## 2. Live Selected Logs to Analysis Job E2E

| Check ID | Scope | Required for Promotion? | Actual | Status |
| --- | --- | --- | --- | --- |
| `E2E-LIVE-JOB-01` | Live Selected Logs → existing full_report Job → Viewer | Live → Analysis Job | Job 30 met the composed acceptance contract | `PASS / CLOSED` |

Job 30 evidence:

- selected child IDs and exact export IDs: `[1128]`
- control ID `1137`: excluded
- `dry_run=false`
- Stage1: real OpenAI success=1, error=0
- Stage2: real OpenAI success
- `stage2_report.json` and `viewer_payload.json`: generated
- `analysis_reports`: saved
- Job status: `SUCCEEDED`
- Job Detail HTTP: 200
- Viewer HTTP: 200
- artifacts: `runs/jobs/30/`

Job 29 remains the preserved negative runtime evidence:

- status: `FAILED`
- cause: export runtime configuration; `LOG_DB_HOST` missing
- no modification, retry, migration, GRANT, source DML, or provider recall was performed against Job 29

## 3. Demo Fixture Freeze

Current status: `NOT FROZEN / PREPARATION IN PROGRESS`.

- CASE-01, CASE-02, CASE-04, CASE-05, CASE-S01, and CASE-S02 referenced fixture/expected files exist and their identities were readable at the verification revision.
- CASE-03 has Job 30 traversal runtime evidence, but the dedicated reproducible demo fixture/input identity required by the casebook is not yet frozen.
- CASE-06 still requires a dedicated CMDi export fixture and Job/Viewer reproduction identity.
- The Job 12 evaluation contract is now hermetic through a tracked minimal fixture; the original Job 12 runtime artifact paths remain provenance only.
- Demo fixture freeze date remains 2026-09-26; no fixture meaning was changed by this verification.

## 4. Screenshot and Presentation Readiness

Current status: `PLAN READY / CAPTURE NOT STARTED`.

- Canonical plan exists: [Final Presentation & Screenshot Plan](./final-presentation-and-screenshot-plan.md).
- Demo narrative, required screen inventory, evidence-boundary wording, fallback requirements, and screenshot metadata contract are defined.
- Current repository inventory contains no PNG/JPEG/WebP screenshot and no PPT/PPTX deck under `docs/` or `runs/`.
- Capture must wait for freeze candidate approval, demo fixture identity freeze, and required runtime checks.
- Every captured screen must record Screen ID, revision, Job ID, Case ID, capture time, environment, source fixture/input, and notes.

## 5. Deployment / Demo Preflight

The following check is mandatory before every final deployment, demo startup, worker restart, or live reproduction:

```text
[ ] worker environment has LOG_DB_HOST
```

Preflight checklist:

```text
[ ] approved freeze revision/SHA is checked out
[ ] worktree and staged-change scope is recorded
[ ] worker environment has LOG_DB_HOST
[ ] APP_DB_USER and LOG_DB_USER are present
[ ] provider credential is present without exposing its value
[ ] DB, Web, and Worker processes use the intended environment
[ ] demo Job IDs and fixture/input identities are fixed
[ ] Job Detail and Viewer routes are reachable
[ ] screenshot/fallback assets match the same freeze revision
[ ] no secret or sensitive raw data is visible
[ ] Apache logs-only evidence-boundary wording is preserved
```

The Job 30 execution environment passed the `LOG_DB_HOST` presence check. This does not replace the mandatory preflight check for a later deployment/demo process environment.

## 6. Code Freeze Decision Snapshot

Current decision: `CODE FREEZE BLOCKED ONLY ON FREEZE CANDIDATE SHA APPROVAL`.

Code Freeze gate:

1. Hermetic Job 12 eval fixture: `PASS`.
2. Core tests all green: `PASS`.
3. External benchmark: `PASS`.
4. Freeze candidate SHA: `NOT SET` — approval pending; no tag was created.

Demo / Evidence Freeze gate, tracked separately from Code Freeze:

1. CASE-03 dedicated fixture identity: pending.
2. CASE-06 dedicated fixture identity: pending.
3. Screenshots/PPT: pending.
4. Evidence-boundary wording review: pending.

No application runtime code, runtime venv, migration, GRANT, source data, Job 29, Job 30, or provider-backed E2E execution was changed during this verification pass.
