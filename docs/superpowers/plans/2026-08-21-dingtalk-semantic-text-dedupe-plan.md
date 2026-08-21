# DingTalk Semantic Text Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore deterministic candidate extraction when DingTalk stores the same real message twice with different whitespace.

**Architecture:** Keep the strict business parser unchanged. Deduplicate text fragments at the existing collection boundary with a Unicode- and whitespace-normalized comparison key while retaining the first original fragment for traceability.

**Tech Stack:** Python 3, pytest, existing `hermes_daily_fact_update_service` and DailyFactBundle.

---

## File Map

- Modify `backend/app/services/hermes_daily_fact_update_service.py`: add the comparison-only semantic text key and use it in the existing collector.
- Modify `backend/tests/test_hermes_daily_fact_update_service.py`: reproduce the production duplicate and protect the different-values rejection rule.
- Modify this plan only to record review and execution evidence.

### Task 1: Reproduce The Production Failure

- [x] Add a test with `recognized_text` and payload `message_text` containing the same plan-contract values but different whitespace.
- [x] Assert the result contains exactly these 9 fields:

```python
{
    "daily_input_weight",
    "cold_roll_input_daily",
    "remaining_contract_weight",
    "cold_2050_input_daily",
    "cold_1850_input_daily",
    "outsourced_input_daily",
    "medium_plate_input_daily",
    "daily_contract_weight",
    "daily_hot_roll_contract_weight",
}
```

- [x] Run:

```powershell
python -m pytest tests/test_hermes_daily_fact_update_service.py -q
```

Expected: the new test fails because candidate extraction returns `[]`.

### Task 2: Protect The Ambiguity Guard

- [x] Add a test containing two plan-contract messages with different numeric values.
- [x] Assert extraction returns `[]`.
- [x] Run the same test file and confirm the new ambiguity test passes before implementation.

### Task 3: Implement The Minimum Fix

- [x] Import `unicodedata` in `hermes_daily_fact_update_service.py`.
- [x] Add a private helper equivalent to:

```python
def _semantic_text_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", "", normalized)
```

- [x] Change `_append_text_part()` so `seen` stores `_semantic_text_key(text)` while `parts` still stores the original `text`.
- [x] Do not change `parse_plan_contract_message()`, confirmation statuses, or fact adoption.
- [x] Run:

```powershell
python -m pytest tests/test_hermes_daily_fact_update_service.py -q
```

Expected: all tests pass.

### Task 4: Regression Verification

- [x] Run the focused integration set:

```powershell
python -m pytest tests/test_hermes_daily_fact_update_service.py tests/test_daily_fact_bundle_service.py tests/test_dingtalk_stream_gateway_service.py -q
```

- [x] Run backend tests if the focused set is green:

```powershell
python -m pytest -q
```

- [x] Review the diff and confirm only the service, its focused test, and approved docs changed.

### Task 5: Merge, Deploy, And Prove On Production

- [x] Commit and push the feature branch.
- [x] Merge to `main`, push `main`, and deploy the exact merged SHA.
- [x] Verify local, origin, and `/srv/aluminum-bypass` SHA parity and clean worktrees.
- [x] Verify `aluminum-bypass` and `hermes-gateway` are active and `/readyz` reports database and MES sync healthy.
- [x] Read-only replay production evidence `712` and `725` through `extract_daily_fact_update_candidates()`.
- [x] Confirm both yield 9 fields, both database rows remain `machine_only`, and the replay does not change the maximum outbox ID.

## Pre-Deploy Evidence

- RED: the production-shaped duplicate regression failed with `[]` instead of 9 fields.
- Focused unit test: `23 passed`.
- Focused integration set: `130 passed`.
- Full backend suite: `3050 passed, 3 skipped, 27 deselected`.
- SPEC review: approved after extracting `_semantic_text_key()` as designed.
- Code-quality review: approved; Unicode full-width characters, NBSP, first `raw_text`, `trace_id`, and different-value ambiguity are covered.
- `git diff --check`: passed.

## Production Evidence

- CI run `32432941712`: frontend build and backend tests succeeded for merged SHA `a19975a5ee5119f47873f413c5b08d60fd0ddf54`.
- Production deploy run `32433860082`: succeeded for the same exact Data Hub SHA; Hermes stayed on `4d4452067cb43ebcd437eba78b0c67d9f1c64652`.
- Production services: `aluminum-bypass=active`, `hermes-gateway=active`.
- `/readyz`: `ready`; database, pipeline, and MES sync are `ok`; MES latest run is `success`.
- Evidence `712`: 9 candidate fields, `confirmation_status=machine_only`.
- Evidence `725`: 9 candidate fields, `confirmation_status=machine_only`.
- Read-only replay outbox maximum ID: `838 -> 838`; no reminder or external message was created.
- Recent production service error scan after deploy: no matching traceback, exception, error, or failure lines.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | CLEAR | Scope reduction: fix one proven parser-boundary defect; no UI or new workflow. |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | SKIPPED | Narrow root-cause fix will receive post-implementation adversarial review. |
| Eng Review | `/plan-eng-review` | Architecture & tests | 1 | CLEAR | Keep strict parser unchanged; dedupe only equivalent fragments; retain ambiguity regression. |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | NOT NEEDED | No user-interface change. |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | NOT NEEDED | No developer-facing workflow change. |

- **UNRESOLVED:** 0
- **VERDICT:** CEO + ENG CLEARED - ready to implement.
