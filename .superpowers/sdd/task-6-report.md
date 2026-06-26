# Task 6 Report: DingTalk Interactive Card Progress Builder

## Scope

- Added deterministic progress-stage sequencing in `backend/app/services/hermes_dingtalk_card_service.py`.
- Added focused card-builder tests in `backend/tests/test_hermes_dingtalk_card_service.py`.
- Kept changes inside the allowed write scope only.

## Preconditions Verified

- `git branch --show-current` -> `daily-report-manual-alignment`
- `git rev-parse --short HEAD` -> `cc095559`

## TDD Evidence

### Red

Command:

```bash
cd backend
python -m pytest tests/test_hermes_dingtalk_card_service.py -q
```

Result:

- Failed during collection with `ModuleNotFoundError: No module named 'app.services.hermes_dingtalk_card_service'`.
- This matched the expected red state from the brief because the service file did not exist yet.

### Green

Implemented the exact deterministic behavior from the brief:

- fixed 7-stage progress sequence
- each stage keeps the same `trace_id`
- card payload reuses one `cardBizId` derived from the trace id
- card exposes only auditable stage labels and fixed feedback actions

## Verification

### Focused test

Command:

```bash
cd backend
python -m pytest tests/test_hermes_dingtalk_card_service.py -q
```

Result:

```text
..                                                                       [100%]
2 passed in 2.19s
```

### Syntax check

Command:

```bash
cd backend
python -m py_compile app/services/hermes_dingtalk_card_service.py tests/test_hermes_dingtalk_card_service.py
```

Result:

- Passed with no output.

### Final required command

Command:

```bash
cd backend && python -m pytest tests/test_hermes_dingtalk_card_service.py -q
```

Result:

- Ran successfully under `cmd` because this workspace PowerShell does not support `&&`.

```text
..                                                                       [100%]
2 passed in 2.10s
```

### Diff hygiene

Command:

```bash
git diff --check
```

Result:

- Passed with no output.

## Files Changed

- `backend/app/services/hermes_dingtalk_card_service.py`
- `backend/tests/test_hermes_dingtalk_card_service.py`
- `.superpowers/sdd/task-6-report.md`

## Notes

- The repository currently has unrelated existing changes in `AGENTS.md` and untracked `docs/superpowers/*` files. They were left untouched.
- The instruction mentioned `docs/longterm-ai-skill-system-spec.md`, but that file does not exist in this worktree. This did not block Task 6 because the brief provided exact implementation requirements.

## Reviewer Fix Evidence

### Finding addressed

- `build_progress_card()` no longer exposes caller-provided `progress.details` in DingTalk cards.
- Card details now come only from fixed stage labels in `_STAGES`; unknown stages fall back to the stage name itself.

### Regression test added

- Added `test_progress_card_uses_auditable_stage_detail_labels`.
- The test builds `FactoryBrainProgress(stage='querying', details=['内部推理: 先猜一个答案再说'], ...)` and proves the internal text is filtered out while `正在查询数据源` remains.

### Red

Command:

```bash
cd backend
python -m pytest tests/test_hermes_dingtalk_card_service.py -q
```

Result:

```text
FAILED tests/test_hermes_dingtalk_card_service.py::test_progress_card_uses_auditable_stage_detail_labels
AssertionError: assert '内部推理: 先猜一个答案再说' not in ['内部推理: 先猜一个答案再说']
```

### Green

Command:

```bash
cd backend
python -m pytest tests/test_hermes_dingtalk_card_service.py -q
```

Result:

```text
...                                                                      [100%]
3 passed in 2.06s
```
