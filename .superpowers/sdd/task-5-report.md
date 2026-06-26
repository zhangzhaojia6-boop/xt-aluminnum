# Task 5 Report: Evidence Merger And Missing-Data Behavior

## Scope

- Implemented `collect_factory_evidence()` and `describe_evidence_gap()` in `backend/app/services/hermes_factory_evidence_service.py`.
- Added focused tests in `backend/tests/test_hermes_factory_evidence_service.py`.
- Kept changes inside the allowed write scope only.

## Preconditions Verified

- `git branch --show-current` -> `daily-report-manual-alignment`
- `git rev-parse --short HEAD` -> `e020e3bd`

## TDD Evidence

### Red

Command:

```bash
cd backend
python -m pytest tests/test_hermes_factory_evidence_service.py -q
```

Result:

- Failed during collection with `ModuleNotFoundError: No module named 'app.services.hermes_factory_evidence_service'`
- This matches the expected red state from the brief because the service file did not exist yet.

### Green

Implemented deterministic placeholder evidence behavior:

- `daily_output` produces a traceable placeholder with:
  - source chosen from the planned tools (`dingtalk_specialist` when DingTalk context ingestion is planned, otherwise `datahub`)
  - `business_date`
  - `unit='ton'`
  - business definition
  - confidence
  - metadata for org units and live-query requirement
- `monthly_output` produces a historical-report placeholder
- Missing metrics are reported without hallucinating values
- RAG is not used as a numeric fact source

## Verification

### Focused test

Command:

```bash
cd backend
python -m pytest tests/test_hermes_factory_evidence_service.py -q
```

Result:

```text
..                                                                       [100%]
2 passed in 2.10s
```

### Syntax check

Command:

```bash
cd backend
python -m py_compile app/services/hermes_factory_evidence_service.py tests/test_hermes_factory_evidence_service.py
```

Result:

- Passed with no output.

### Final required command

Command:

```bash
cd backend && python -m pytest tests/test_hermes_factory_evidence_service.py -q
```

Result:

```text
..                                                                       [100%]
2 passed in 2.09s
```

### Diff hygiene

Command:

```bash
git diff --check
```

Result:

- Passed with no output.

## Files Changed

- `backend/app/services/hermes_factory_evidence_service.py`
- `backend/tests/test_hermes_factory_evidence_service.py`
- `.superpowers/sdd/task-5-report.md`

## Notes

- The repository currently has unrelated existing changes in `AGENTS.md` and untracked `docs/superpowers/*` files. They were left untouched.
- The instruction mentioned `docs/longterm-ai-skill-system-spec.md`, but that file does not exist in this worktree. This did not block Task 5 because the task brief provided exact implementation requirements.

## Reviewer Fix: Placeholder Evidence Still Counts As Missing

### Preconditions Re-verified

- `git branch --show-current` -> `daily-report-manual-alignment`
- `git rev-parse --short HEAD` -> `6c5ccf81`

### Red

Command:

```bash
cd backend
python -m pytest tests/test_hermes_factory_evidence_service.py -q
```

Result:

- `test_gap_message_still_names_placeholder_metrics_as_missing` failed.
- Failure matched the reviewer finding: `describe_evidence_gap()` returned `None` after `collect_factory_evidence()` produced placeholder references with `value=None` and `metadata["needs_live_query"]=True`.

### Fix

- Added regression coverage that first collects `daily_output` evidence, then feeds those references into `describe_evidence_gap()`.
- Added assertions that collected references keep `business_date` and a non-empty `business_definition`.
- Tightened completeness logic so a reference only counts as complete when:
  - `value is not None`
  - `metadata["needs_live_query"]` is not true

### Green

Command:

```bash
cd backend
python -m pytest tests/test_hermes_factory_evidence_service.py -q
```

Result:

```text
...                                                                      [100%]
3 passed in 2.11s
```

### Diff Hygiene

Command:

```bash
git diff --check
```

Result:

- Passed with no output.
