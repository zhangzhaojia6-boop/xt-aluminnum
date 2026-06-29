## Task 3: Evidence Priority Planner

status: DONE

changed files:
- `backend/app/services/hermes_root_owner_evidence_service.py`
- `backend/tests/test_hermes_root_owner_evidence_service.py`

commit:
- `5c13214f` feat: prioritize root owner evidence sources

tests run with outputs:
- `cd backend; python -m pytest tests/test_hermes_root_owner_evidence_service.py -q` (red step)
  - output:
    - `ModuleNotFoundError: No module named 'app.services.hermes_root_owner_evidence_service'`
- `cd backend; python -m pytest tests/test_hermes_root_owner_evidence_service.py -q` (green step)
  - output: `3 passed in 2.52s`

self-review:
- 钉钉群内容候选优先级高于 MES 只读库。
- 生产域 MES 只读候选优先级高于数据中枢投影。
- 缺少钉钉、MES、数据中枢投影时，会在 `missing_sources` 和 trace 里明确记录。
- 本次没有新增 routing、outbox、frontend 或 docs 逻辑；报告文件只按任务要求记录结果，未纳入提交。

concerns:
- 提交前发现暂存区已有外部文档归档 rename；本次 commit 使用 pathspec，只提交了两个任务文件，没有包含那些既有改动。

---

status: DONE

changed files:
- backend/app/services/hermes_factory_normalization_service.py
- backend/tests/test_hermes_factory_normalization_service.py
- .superpowers/sdd/task-3-report.md

commit:
- b17da27e Normalize factory-brain requests into routing-ready facts

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (red step)
  - output:
    - `ERROR collecting tests/test_hermes_factory_normalization_service.py`
    - `ModuleNotFoundError: No module named 'app.services.hermes_factory_normalization_service'`
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (green step)
  - output: `2 passed in 2.24s`
- `cd backend && python -m compileall app/services/hermes_factory_normalization_service.py tests/test_hermes_factory_normalization_service.py`
  - output: success
- `git diff --check`
  - output: success

self-review:
- 按 brief 先写测试，再运行红灯，确认失败原因就是缺少 normalization service。
- 实现严格按 Task 3 范围收口，只新增 normalization service 和对应测试，没有改动意图分类器、orchestrator 或其他旧行为。
- 归一化规则保持最小：统一车间别名、统一指标列表、固定数据源优先级、判断 artifact 与输出模式。

concerns:
- `docs/longterm-ai-skill-system-spec.md` 在当前 worktree 中不存在；本次改读了仓库里实际存在的相关 Hermes 设计文档，不影响 Task 3 落地。

## Fix Task 3 Review Finding

changed files:
- `backend/app/services/hermes_factory_normalization_service.py`
- `backend/tests/test_hermes_factory_normalization_service.py`
- `.superpowers/sdd/task-3-report.md`

commit:
- `2acdac72` Recognize bare workshop numbers in factory normalization

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (red step)
  - output:
    - `3 failed, 2 passed in 3.17s`
    - failures: bare `1650` / `1850` / `2050` natural-language cases normalized to `factory` instead of `workshop`
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (green step)
  - output: `5 passed in 2.17s`
- `cd backend && python -m compileall app/services/hermes_factory_normalization_service.py tests/test_hermes_factory_normalization_service.py`
  - output:
    - `Compiling 'app/services/hermes_factory_normalization_service.py'...`
    - `Compiling 'tests/test_hermes_factory_normalization_service.py'...`

## Fix Task 3 Final Review Finding

changed files:
- `backend/app/services/hermes_factory_normalization_service.py`
- `backend/tests/test_hermes_factory_normalization_service.py`
- `.superpowers/sdd/task-3-report.md`

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (red step)
  - output:
    - `3 failed, 5 passed in 3.62s`
    - failures: `entities={'workshop': '1650'/'1850'/'2050'}` still normalized to `factory` when text did not include the workshop number
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (green step)
  - output: `8 passed in 2.11s`
- `cd backend && python -m compileall app/services/hermes_factory_normalization_service.py tests/test_hermes_factory_normalization_service.py`
  - output:
    - `Compiling 'tests/test_hermes_factory_normalization_service.py'...`
- `git diff --check -- backend/app/services/hermes_factory_normalization_service.py backend/tests/test_hermes_factory_normalization_service.py .superpowers/sdd/task-3-report.md`
  - output: success

self-review:
- 只补了一个缺口：当上游意图分类器把车间直接归一成裸数字字符串时，归一化层现在会把它当作车间，不再错误回退到全厂。
- 原有别名匹配、文本裸数字匹配、指标归一化和输出模式逻辑都保持不变。

## Fix Task 3 Final Review Finding Round 2

changed files:
- `backend/app/services/hermes_factory_normalization_service.py`
- `backend/tests/test_hermes_factory_normalization_service.py`
- `.superpowers/sdd/task-3-report.md`

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (red step)
  - output:
    - `1 failed, 11 passed in 2.55s`
    - failure: `今天产量2050吨发我` was still normalized to `workshop` instead of `factory`
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (green step)
  - output: `12 passed in 2.21s`

self-review:
- 这次只收紧了“文本里裸数字车间号”的识别条件，不动实体兜底、别名映射、指标归一化和输出模式。
- 现在只有两种文本会按裸数字识别车间：句首车间号上下文，或数字后面明确跟 `车间`、`冷轧`、`机组`。
- `今天产量2050吨发我` 这种吨数表达会留在全厂范围，不会再误命中 `2050` 车间。

## Fix Task 3 Reviewer Finding: Full Workshop Entity Aliases

changed files:
- `backend/app/services/hermes_factory_normalization_service.py`
- `backend/tests/test_hermes_factory_normalization_service.py`
- `.superpowers/sdd/task-3-report.md`

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (red step)
  - output:
    - `3 failed, 12 passed in 2.67s`
    - failures: `entities={'workshop': '1650冷轧车间'/'1850冷轧车间'/'2050冷轧车间'}` still normalized to `factory` when text did not include the workshop
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (green step)
  - output: `15 passed in 2.12s`
- `cd backend && python -m compileall app/services/hermes_factory_normalization_service.py tests/test_hermes_factory_normalization_service.py`
  - output:
    - `Compiling 'tests/test_hermes_factory_normalization_service.py'...`
- `git diff --check -- backend/app/services/hermes_factory_normalization_service.py backend/tests/test_hermes_factory_normalization_service.py .superpowers/sdd/task-3-report.md`
  - output: success

self-review:
- 这次只补了 3 个完整车间实体别名：`1650冷轧车间`、`1850冷轧车间`、`2050冷轧车间`。
- 没有放宽数字识别规则，所以 `今天产量2050吨发我` 仍然会保持全厂范围，不会被错判成 `2050` 车间。

## Fix Task 3 Reviewer Finding: Bare Numeric Entity Needs Workshop Context

changed files:
- `backend/app/services/hermes_factory_normalization_service.py`
- `backend/tests/test_hermes_factory_normalization_service.py`
- `.superpowers/sdd/task-3-report.md`

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (red step)
  - output:
    - `1 failed, 15 passed in 2.42s`
    - failure: `entities={'workshop': '2050'}` plus `今天产量2050吨发我` still normalized to `workshop` instead of `factory`
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (green step)
  - output: `16 passed in 2.01s`
- `cd backend && python -m compileall app/services/hermes_factory_normalization_service.py tests/test_hermes_factory_normalization_service.py`
  - output:
    - `Compiling 'tests/test_hermes_factory_normalization_service.py'...`
- `git diff --check -- backend/app/services/hermes_factory_normalization_service.py backend/tests/test_hermes_factory_normalization_service.py .superpowers/sdd/task-3-report.md`
  - output: success

self-review:
- 这次只收紧了“裸数字 workshop 实体”的兜底条件：文本也必须出现同一个车间号的车间语境，才会认成车间。
- `2050冷轧车间` 这类完整实体别名仍然无条件接受；`1650今天产量发我` 这类句首车间语境也保持可识别。
- `今天产量2050吨发我` 这种吨数表达现在会回到全厂范围，不再误把吨数当车间。

## Fix Task 3 Reviewer Finding: Bare Numeric Entity Fallback

changed files:
- `backend/app/services/hermes_factory_normalization_service.py`
- `backend/tests/test_hermes_factory_normalization_service.py`
- `.superpowers/sdd/task-3-report.md`

tests run with outputs:
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (red step)
  - output:
    - `3 failed, 16 passed in 2.48s`
    - failures: `entities={'workshop': '1650'/'1850'/'2050'}` plus `今天产量发我` still normalized to `factory`
- `cd backend && python -m pytest tests/test_hermes_factory_normalization_service.py -q` (green step)
  - output: `21 passed in 2.18s`

self-review:
- 裸数字 workshop 实体现在默认信任，保留上游实体识别结果。
- 如果原文把同一个数字明确写成吨数，例如 `2050吨`、`2050t`、`2050T`，归一化会拒绝该裸数字实体并保持全厂范围。
- 文本自身没有实体时仍保持严格规则，`今天产量2050吨发我` 不会被文本匹配误识别为 `2050` 车间。

## Fix Task 3 Review Findings: Evidence Priority Candidates

changed files:
- `backend/app/services/hermes_root_owner_evidence_service.py`
- `backend/tests/test_hermes_root_owner_evidence_service.py`
- `.superpowers/sdd/task-3-report.md`

tests run with outputs:
- `cd backend; python -m pytest tests/test_hermes_root_owner_evidence_service.py -q` (red step)
  - output:
    - `3 failed, 3 passed in 2.99s`
    - failures:
      - DingTalk metadata-only candidate still became primary over MES.
      - Hub reader exception was raised instead of being traced with a redacted reason.
      - Inventory domain did not call MES/WMS reader for inventory metric keys.
- `cd backend; python -m pytest tests/test_hermes_root_owner_evidence_service.py -q` (green step)
  - output: `6 passed in 2.51s`

self-review:
- DingTalk evidence only participates in primary selection when its value contains a current requested metric fact; metadata-only DingTalk items stay visible as supporting trace evidence.
- Trace now records per-source status details for DingTalk, MES/WMS and data hub projection, including missing/failed status, reasons, redacted errors and MES query keys.
- Inventory domain now plans MES/WMS reads for `finished_inbound_daily`, `wip_total` and `remaining_contract_weight`, and MES keeps higher priority than hub projection.

## Fix Task 3 Review Findings: Default DingTalk Facts And Hub Ready

changed files:
- `backend/app/services/hermes_root_owner_evidence_service.py`
- `backend/tests/test_hermes_root_owner_evidence_service.py`
- `.superpowers/sdd/task-3-report.md`

tests run with outputs:
- `cd backend; python -m pytest tests/test_hermes_root_owner_evidence_service.py -q`
  - output: `9 passed in 2.47s`
- `cd backend; python -m compileall app/services/hermes_root_owner_evidence_service.py tests/test_hermes_root_owner_evidence_service.py`
  - output: success

self-review:
- 默认 DingTalk reader 现在只从 `facts` / `parsed_facts` / `metrics` / `payload` / `metric_key + value` / 直接指标键里提取当前指标事实；文件名、摘要、raw text 这类元数据仍只作为 supporting evidence。
- `trace["source_status"]["dingtalk_group_content"]` 现在保留 DingTalk text/file 的 `status`、`error` 和计数；错误内容走 `redact_secret_text()` 脱敏。
- hub payload 的 `status="ready"` 进入候选排序前归一为 `ok`，trace 里仍保留原始 `ready` 和候选状态。

## Fix Task 3 Second Round Review Findings

changed files:
- `backend/app/services/hermes_root_owner_evidence_service.py`
- `backend/tests/test_hermes_root_owner_evidence_service.py`
- `.superpowers/sdd/task-3-report.md`

tests run with outputs:
- `cd backend; python -m pytest tests/test_hermes_root_owner_evidence_service.py -q` (red step)
  - output: `3 failed, 8 passed in 4.39s`
  - failures:
    - 未校验的默认 DingTalk `facts` 仍会压过 MES。
    - MES 真实 `records[query_key] = list[dict]` 形状仍把原始 records 放进 primary.value。
    - Hub 真实 `facts.values` 形状仍把原始 payload 放进 primary.value。
- `cd backend; python -m pytest tests/test_hermes_root_owner_evidence_service.py -q`
  - output: `11 passed in 5.83s`
- `cd backend; python -m compileall app/services/hermes_root_owner_evidence_service.py tests/test_hermes_root_owner_evidence_service.py`
  - output: success
- `git diff --check -- backend/app/services/hermes_root_owner_evidence_service.py backend/tests/test_hermes_root_owner_evidence_service.py`
  - output: success

self-review:
- 默认 DingTalk reader 只有在当前指标事实同时满足授权群、责任人/发送人、内容类型、业务时间窗口校验时，才会生成可参与 primary 排序的候选。
- 未校验的 DingTalk `facts`、raw text、文件摘要和其他原始 item 仍保留在 `supporting_evidence`，不再被递归指标检测误提权。
- MES 候选现在先按 `message_plan.metric_keys` 抽成 `{metric_key: value}`；真实 `records[query_key]` 列表会按最小字段集合聚合，抽不到当前指标会记录 `no_current_metric_fact` 并不建 primary。
- Hub 候选现在只从 `facts.values` 或 payload 直接指标键抽当前指标；`status="ready"` 仍可进入候选，但 primary.value 是指标小字典，不是日报大对象。

concerns:
- 本轮只覆盖当前 Task 3 evidence planner；没有跑后端全量测试，也没有做真实 MES / DingTalk / Hub 生产联调。

## Fix Task 3 Third Round Review Findings

changed files:
- `backend/app/services/hermes_root_owner_evidence_service.py`
- `backend/tests/test_hermes_root_owner_evidence_service.py`
- `.superpowers/sdd/task-3-report.md`

tests run with outputs:
- `cd backend; python -m pytest tests/test_hermes_root_owner_evidence_service.py -q`
  - first output after code change: `1 failed, 12 passed in 3.68s`
  - failure reason: old test still used `authorized_group: required` as a verified marker; updated it to `verified`.
  - final output: `13 passed in 2.45s`
- `cd backend; python -m compileall app/services/hermes_root_owner_evidence_service.py tests/test_hermes_root_owner_evidence_service.py`
  - output: success
- `git diff --check -- backend/app/services/hermes_root_owner_evidence_service.py backend/tests/test_hermes_root_owner_evidence_service.py`
  - output: success

self-review:
- `_validation_truthy()` no longer treats `required` or `business_day_window` as validation success. These now stay as rule descriptions unless another explicit pass marker exists.
- Default DingTalk facts with `evidence_conditions` such as `authorized_group: required`, `time_range: business_day_window`, and `content_type: [text, file, image]` remain supporting evidence and no longer beat MES.
- Same-priority DingTalk candidates now sort chat/text before file, then image, without changing DingTalk vs MES vs Hub priority numbers.
- Commit will include only the service and test files; this report remains in the worktree by request.

concerns:
- 本轮只跑了 Task 3 指定测试、compileall 和目标 diff check；没有跑后端全量测试，也没有做真实 DingTalk/MES 联调。
