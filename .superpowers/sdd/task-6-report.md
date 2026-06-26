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

## Reviewer Fix 2: Unsafe Unknown Stage Fallback

### Finding addressed

- `build_progress_card()` no longer uses unknown `progress.stage` text as the card detail fallback.
- Unknown stages now map to the fixed safe label `状态更新中`, so free-text internal reasoning is not echoed into `card['details']`.

### Regression test added

- Added `test_progress_card_uses_safe_fallback_for_unknown_stage`.
- The test builds `FactoryBrainProgress(stage='内部推理: 先猜一个答案再说', details=['x'], ...)` and proves `card['details']` becomes `['状态更新中']`.

### Red

Command:

```bash
cd backend
python -m pytest tests/test_hermes_dingtalk_card_service.py -q
```

Result:

```text
FAILED tests/test_hermes_dingtalk_card_service.py::test_progress_card_uses_safe_fallback_for_unknown_stage
AssertionError: assert ['内部推理: 先猜一个答案再说'] == ['状态更新中']
```

### Green

Command:

```bash
cd backend
python -m pytest tests/test_hermes_dingtalk_card_service.py -q
```

Result:

```text
....                                                                     [100%]
4 passed in 2.04s
```

## Reviewer Fix 3: Unknown Stage Leak Through `card['stage']`

### Finding addressed

- `build_progress_card()` no longer copies unknown `progress.stage` text into `card['stage']`.
- Known stages still keep their exact original stage value.
- Unknown stages now use fixed safe values:
  - `card['stage'] = 'status_updating'`
  - `card['details'] = ['状态更新中']`

### Regression test extended

- Extended `test_progress_card_uses_safe_fallback_for_unknown_stage`.
- The test now proves both:
  - unknown stage text is not exposed through `card['stage']`
  - unknown stage text is not exposed through `card['details']`

### Red

Command:

```bash
cd backend
python -m pytest tests/test_hermes_dingtalk_card_service.py -q
```

Result:

```text
FAILED tests/test_hermes_dingtalk_card_service.py::test_progress_card_uses_safe_fallback_for_unknown_stage
AssertionError: assert '内部推理: 先猜一个答案再说' == 'status_updating'
1 failed, 3 passed in 2.57s
```

### Green

Command:

```bash
cd backend && python -m pytest tests/test_hermes_dingtalk_card_service.py -q
```

Result:

```text
....                                                                     [100%]
4 passed in 2.12s
```

### Diff hygiene

Command:

```bash
git diff --check
```

Result:

- Passed with no output.
