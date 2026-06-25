# Task 1 Report - Hermes Fact Source Map

## What I implemented

I added the first machine-readable Hermes fact source map for `鑫泰铝业 数据中枢`.

- Created `backend/app/hermes/fact_source_map.json` with 12 fact entries covering production, inventory, energy, quality, cost, period, operations, and DingTalk evidence.
- Added `backend/app/services/hermes_fact_source_map_service.py` with:
  - `load_fact_source_map()`
  - `find_fact_source()`
  - `source_summary_for_metric()`
  - basic item validation for required fields, list fields, and delete protection values
- Added `backend/tests/test_hermes_fact_source_map_service.py` to verify:
  - core metrics load correctly
  - raw evidence and audit paths are protected
  - no sensitive keys appear in the loaded map

## RED command/output summary

Command:

```powershell
python -m pytest backend/tests/test_hermes_fact_source_map_service.py -q
```

Expected failure happened during collection:

- `ModuleNotFoundError: No module named 'app.services.hermes_fact_source_map_service'`

Why it failed as expected:

- The test file imported the new service module before it existed, so pytest stopped immediately during import collection.

## GREEN command/output summary

Command:

```powershell
python -m pytest backend/tests/test_hermes_fact_source_map_service.py -q
```

Result:

- `3 passed in 2.17s`

## Files changed

- `backend/app/hermes/fact_source_map.json`
- `backend/app/services/hermes_fact_source_map_service.py`
- `backend/tests/test_hermes_fact_source_map_service.py`

## Self-review findings

- The change is tightly scoped to the three owned files.
- The JSON content matches the task brief and includes the required 12 metrics.
- The service only does the minimum validation needed for this first source map.
- The public helper `source_summary_for_metric()` reads naturally for Hermes-facing summaries and includes the expected source/service/risk text.

## Concerns

None.

## Commit

- `9d184ee5` - `feat: add Hermes fact source map`

## Review follow-up

本次按评审意见补了 3 个点：

- 第一批事实来源地图现在明确补上了 3 个缺失类别的机器可读指标键：`workshop_output_daily`、`daily_input_weight`、`anomaly_explanation_daily`。
- 所有使用 `dingtalk_specialist` 作为优先来源的条目，都补了 `dingtalk_evidence_conditions`，并要求 4 个门禁键：`authorized_group`、`specialist_sender`、`content_type`、`time_range`。
- `load_fact_source_map()` 现在会检查重复 `metric_key`，重复时直接报错；测试里也加了一个临时 JSON 重复键回归。

这次没有新增任何密钥、连接串、token，也没有加入 MES/WMS 写路径。

测试结果：

```text
python -m pytest backend/tests/test_hermes_fact_source_map_service.py -q
5 passed in 2.17s
```
