# 外部 MES 投影与 AI 工厂总览 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `鑫泰铝业 数据中枢` 内交付外部 `MES` 只读投影、车间/机列/卷级实时大屏、填报端流转确认，以及能交流、会主动汇报的常驻 AI 助手。

**Architecture:** 外部 `MES` 只作为读源，通过服务端 adapter 拉取 MVC/DataTables 接口并落到本地读模型，不回写、不把凭据下发前端。后端新增 `factory-command` 只读 API，把卷级流转、机列聚合、库存去向、经营估算和数据新鲜度整理成前端可直接渲染的结构。AI 只读取后端生成的窄上下文包，用证据引用、主动汇报和关注订阅支撑对话，不让模型直接扫库或执行写动作。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, APScheduler, pytest, httpx, Vue 3, Pinia, Element Plus, node:test, Vite

---

## Scope

这个 spec 横跨外部 `MES` 接入、读模型、大屏、AI、填报端。它们不是彼此独立的产品线，交付链路是同一条：先拿到可信生产事实，再按车间/机列/卷聚合，最后让 AI 围绕这些事实交流和主动汇报。所以这里保留为一个实施计划，但每个 task 都按可测试的垂直切片拆开，执行时逐段提交。

非目标：

- 不回写外部 `MES`。
- 不把产品命名为 `MES`，用户可见身份继续使用 `数据中枢`。
- 不新增外部消息发送，第一阶段只做站内主动汇报和草稿。
- 不引入新依赖，除非执行时先单独确认。
- 不承诺财务利润，只展示经营估算口径。

## File Map

Backend adapter and sync:

- Modify: `backend/app/config.py` for external `MES` MVC adapter env settings.
- Modify: `backend/app/adapters/mes_adapter.py` to extend read-only adapter contracts.
- Create: `backend/app/adapters/mvc_mes_adapter.py` for login/session/DataTables parsing.
- Modify: `backend/app/main.py` to construct the MVC adapter and register idempotent sync jobs.
- Modify: `backend/app/services/mes_sync_service.py` to sync follow cards, dispatch, crafts, devices, WIP, stock, machine lines, and flow events.
- Modify: `backend/app/models/mes.py` for projection fields and new read models.
- Create: `backend/alembic/versions/0022_factory_command_projection.py`.
- Test: `backend/tests/test_mvc_mes_adapter.py`, `backend/tests/test_mes_sync_service.py`, `backend/tests/test_mes_sync_lag.py`.

Backend factory command:

- Create: `backend/app/schemas/factory_command.py`.
- Create: `backend/app/services/factory_command_service.py`.
- Create: `backend/app/routers/factory_command.py`.
- Modify: `backend/app/main.py` to include `/api/v1/factory-command`.
- Test: `backend/tests/test_factory_command_service.py`, `backend/tests/test_factory_command_routes.py`.

Backend AI assistant:

- Create: `backend/app/models/assistant.py`.
- Create: `backend/alembic/versions/0023_ai_assistant_state.py`.
- Create: `backend/app/schemas/ai_assistant.py`.
- Create: `backend/app/services/ai_context_service.py`.
- Create: `backend/app/services/ai_rules_service.py`.
- Create: `backend/app/services/ai_briefing_service.py`.
- Modify: `backend/app/routers/ai.py` to persist conversations and expose assistant, briefing, and watchlist endpoints.
- Modify: `backend/app/services/assistant_service.py` only for shared LLM fallback helpers if needed.
- Test: `backend/tests/test_ai_context_service.py`, `backend/tests/test_ai_briefing_service.py`, `backend/tests/test_ai_assistant_routes.py`.

Backend fill terminal:

- Modify: `backend/app/schemas/work_orders.py`.
- Modify: `backend/app/services/work_order/entry.py`.
- Test: `backend/tests/test_work_order_routes.py`, `backend/tests/test_work_order_service.py`.

Frontend data layer:

- Create: `frontend/src/api/factory-command.js`.
- Create: `frontend/src/api/ai-assistant.js`.
- Create: `frontend/src/stores/factory-command.js`.
- Modify: `frontend/src/stores/ai-chat.js`.
- Modify: `frontend/src/stores/assistant.js`.
- Create: `frontend/src/utils/factoryCommandFormatters.js`.
- Create: `frontend/src/utils/aiAssistantContracts.js`.
- Test: `frontend/tests/factoryCommandFormatters.test.js`, `frontend/tests/aiAssistantContracts.test.js`.

Frontend routes and screens:

- Modify: `frontend/src/router/index.js`.
- Modify: `frontend/src/config/manage-navigation.js`.
- Create: `frontend/src/views/factory-command/FactoryCommandShell.vue`.
- Create: `frontend/src/views/factory-command/FactoryOverview.vue`.
- Create: `frontend/src/views/factory-command/ProductionFlowScreen.vue`.
- Create: `frontend/src/views/factory-command/MachineLineScreen.vue`.
- Create: `frontend/src/views/factory-command/CoilTrace.vue`.
- Create: `frontend/src/views/factory-command/CostBenefitScreen.vue`.
- Create: `frontend/src/views/factory-command/DestinationScreen.vue`.
- Create: `frontend/src/views/factory-command/ExceptionMap.vue`.
- Modify: `frontend/src/views/reports/LiveDashboard.vue` only for route handoff or reuse of overview data.
- Test: `frontend/tests/factoryCommandNavigation.test.js`, `frontend/tests/factoryCommandScreens.test.js`.

Frontend AI assistant UI:

- Create: `frontend/src/components/ai/AiAssistantDrawer.vue`.
- Create: `frontend/src/components/ai/AiBriefingInbox.vue`.
- Create: `frontend/src/components/ai/AiEvidenceRefs.vue`.
- Create: `frontend/src/components/ai/AiWatchlistPanel.vue`.
- Modify: `frontend/src/layout/ManageShell.vue`.
- Modify: `frontend/src/views/ai/AiWorkstation.vue`.
- Modify: `frontend/src/components/review/ReviewAssistantDock.vue`.
- Test: `frontend/tests/aiAssistantUiContract.test.js`.

Frontend fill terminal:

- Create: `frontend/src/utils/coilFlowFields.js`.
- Modify: `frontend/src/views/mobile/CoilEntryWorkbench.vue`.
- Modify: `frontend/src/utils/coilEntryValidation.js`.
- Test: `frontend/tests/coilFlowFields.test.js`, `frontend/tests/coilEntryValidation.test.js`.

## Task 1: 外部 MES MVC 只读 Adapter

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/adapters/mes_adapter.py`
- Create: `backend/app/adapters/mvc_mes_adapter.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_mvc_mes_adapter.py`
- Test: `backend/tests/test_mes_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

Create `backend/tests/test_mvc_mes_adapter.py` with fake sender responses for:

- login flow: `/Login/CheckLogin`, `/Login/QueryLogin`
- menu: `/Right/GetUserRightList`
- DataTables list: `/Dispatch/QueryList`
- master data: `/Craft/GetList`, `/Device/GetList`
- stock: `/Stock/GetList`
- WIP summary: `/Dispatch/DoingReportTotal`

Expected assertions:

- credentials are read from settings, never from request payloads.
- `BatchNumber` becomes `tracking_card_no`, but `coil_key` prefers `MES:{Product.Id}`.
- `CurrentWorkShop`, `CurrentProcess`, `NextWorkShop`, `NextProcess`, `ProcessRoute`, `PrintProcessRoute`, `DelayHour`, `StatusName`, `MaterialCode` are preserved in metadata.
- adapter methods return empty lists on empty `data`, and raise on login failure.
- adapter does not implement writeback.

- [ ] **Step 2: Run adapter tests and confirm RED**

Run: `python -m pytest backend/tests/test_mvc_mes_adapter.py -q`

Expected: FAIL because `MvcMesAdapter` and the extended adapter contract do not exist.

- [ ] **Step 3: Extend adapter contract minimally**

Update `backend/app/adapters/mes_adapter.py` with read-only dataclasses:

- `MesCraft`
- `MesDevice`
- `MesStockItem`
- `MesWipTotal`
- `MesMachineLineSource`

Add abstract methods with `NullMesAdapter` empty implementations:

- `list_crafts()`
- `list_devices()`
- `list_follow_cards(...)`
- `list_dispatch(...)`
- `list_wip_totals()`
- `list_stock(...)`
- `list_machine_line_sources()`

保持 `push_completion()` 兼容旧代码，但本功能不调用它。

- [ ] **Step 4: Implement `MvcMesAdapter`**

Create `backend/app/adapters/mvc_mes_adapter.py`.

实现要点：

- 只使用现有 `httpx`。
- cookies 保存在 adapter 实例内。
- base URL 统一去掉结尾斜杠。
- 用户名和密码只从 env-backed settings 读取。
- DataTables 请求使用服务端 POST 参数。
- 原始行保存在 `metadata` 或 `source_payload`。
- 用小型私有 helper 处理 text、float、datetime 和嵌套 `Product.Id` 提取。

- [ ] **Step 5: Wire adapter construction**

Modify `backend/app/config.py`:

- add `MES_MVC_BASE_URL`
- add `MES_MVC_USERNAME`
- add `MES_MVC_PASSWORD`
- add `MES_MVC_TIMEOUT_SECONDS`

Modify `backend/app/main.py` so `MES_ADAPTER=mvc` creates `MvcMesAdapter`.

- [ ] **Step 6: Run adapter target tests**

Run: `python -m pytest backend/tests/test_mvc_mes_adapter.py backend/tests/test_rest_api_mes_adapter.py backend/tests/test_mes_adapter.py -q`

Expected: PASS.

- [ ] **Step 7: Commit adapter slice**

Commit message: `feat: add read only mvc mes adapter`

## Task 2: MES 投影读模型与同步

**Files:**
- Modify: `backend/app/models/mes.py`
- Create: `backend/alembic/versions/0022_factory_command_projection.py`
- Modify: `backend/app/services/mes_sync_service.py`
- Modify: `backend/app/schemas/mes_sync.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_mes_sync_service.py`
- Test: `backend/tests/test_mes_sync_lag.py`

- [ ] **Step 1: Write failing sync tests**

Extend `backend/tests/test_mes_sync_service.py`.

预期断言：

- `_upsert_snapshot` 保存 `mes_product_id`、`material_code`、current/next workshop/process、route text、status name、delay hours、spec fields 和 `last_seen_from_mes_at`。
- `coil_key` 有 product id 时使用 `MES:{mes_product_id}`，否则使用 `fallback:{batch_no}:{material_code}`。
- 机列同步把设备名和 1#-11# 槽位映射到稳定 `line_code`。
- flow events 幂等，同一卷同一工序重复出现时不重复写入。
- 同步失败时 run log 记录为 `failed`，并且不删除已有投影行。

- [ ] **Step 2: Run sync tests and confirm RED**

Run: `python -m pytest backend/tests/test_mes_sync_service.py backend/tests/test_mes_sync_lag.py -q`

Expected: FAIL because the new fields and tables do not exist.

- [ ] **Step 3: Add migration and models**

Create `backend/alembic/versions/0022_factory_command_projection.py`.

Add columns to `mes_coil_snapshots`:

- `mes_product_id`
- `material_code`
- `customer_alias`
- `alloy_grade`
- `material_state`
- `spec_thickness`
- `spec_width`
- `spec_length`
- `spec_display`
- `feeding_weight`
- `material_weight`
- `gross_weight`
- `net_weight`
- `current_workshop`
- `current_process`
- `current_process_sort`
- `next_workshop`
- `next_process`
- `next_process_sort`
- `process_route_text`
- `print_process_route_text`
- `status_name`
- `card_status_name`
- `production_status`
- `delay_hours`
- `in_stock_date`
- `delivery_date`
- `allocation_date`
- `last_seen_from_mes_at`

Create tables:

- `mes_machine_line_snapshots`
- `coil_flow_events`

Mirror the same fields in `backend/app/models/mes.py`.

- [ ] **Step 4: Implement idempotent sync functions**

Update `backend/app/services/mes_sync_service.py`:

- 保持现有 `sync_coil_snapshots()` 行为稳定。
- add `sync_mes_crafts()`
- add `sync_mes_devices()`
- add `sync_mes_follow_cards()`
- add `sync_mes_dispatch()`
- add `sync_mes_wip_total()`
- add `sync_mes_stock()`
- add `sync_mes_machine_lines()`
- add flow-event generation from previous/current/next process changes.

All functions return `MesSyncStats` or a compatible dict with fetched/upserted/replayed/failed counts.

- [ ] **Step 5: Register scheduler jobs**

Modify `backend/app/main.py`:

- 保留当前 `mes_sync` job，兼容旧同步链路。
- when adapter is not `null`, schedule the broader projection sync at `settings.MES_SYNC_POLL_MINUTES`.
- set `max_instances=1`, `coalesce=True`, and never clear old rows on failure.

- [ ] **Step 6: Run migration and sync target tests**

Run: `python -m pytest backend/tests/test_mes_sync_service.py backend/tests/test_mes_sync_lag.py -q`

Expected: PASS.

- [ ] **Step 7: Commit projection slice**

Commit message: `feat: project mes coils and machine lines`

## Task 3: Factory Command Backend API

**Files:**
- Create: `backend/app/schemas/factory_command.py`
- Create: `backend/app/services/factory_command_service.py`
- Create: `backend/app/routers/factory_command.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_factory_command_service.py`
- Test: `backend/tests/test_factory_command_routes.py`

- [ ] **Step 1: Write failing service tests**

Create `backend/tests/test_factory_command_service.py` with in-memory rows or lightweight SQLAlchemy session fixtures.

Expected assertions:

- overview returns output, WIP, stock destination, abnormal count, cost estimate, and sync freshness.
- workshop rows group by `current_workshop`.
- machine-line rows group by `line_code` and expose active coil count, active tons, finished tons, stalled count, cost estimate, and margin estimate.
- coil flow returns previous/current/next process and destination.
- stale status is `fresh` under 120s, `stale` above 300s, and `offline_or_blocked` above 900s.
- cost fields are labelled as estimate and do not use finance-profit wording.

- [ ] **Step 2: Write failing route tests**

Create `backend/tests/test_factory_command_routes.py`.

Cover:

- `GET /api/v1/factory-command/overview`
- `GET /api/v1/factory-command/workshops`
- `GET /api/v1/factory-command/machine-lines`
- `GET /api/v1/factory-command/coils`
- `GET /api/v1/factory-command/coils/{coil_key}/flow`
- `GET /api/v1/factory-command/cost-benefit`
- `GET /api/v1/factory-command/destinations`
- `GET /api/v1/mes/sync-status`

- [ ] **Step 3: Run factory command tests and confirm RED**

Run: `python -m pytest backend/tests/test_factory_command_service.py backend/tests/test_factory_command_routes.py -q`

Expected: FAIL because schemas, service, and router do not exist.

- [ ] **Step 4: Implement schemas**

Create `backend/app/schemas/factory_command.py` with response models:

- `FactoryCommandFreshnessOut`
- `FactoryOverviewOut`
- `FactoryWorkshopOut`
- `FactoryMachineLineOut`
- `FactoryCoilListItemOut`
- `FactoryCoilFlowOut`
- `FactoryCostBenefitOut`
- `FactoryDestinationOut`

字段保持显式声明。不要新增名为 `description`、`explanation`、`helperText`、`tooltip`、`note` 或 `rationale` 的 schema 字段。

- [ ] **Step 5: Implement service aggregation**

Create `backend/app/services/factory_command_service.py`.

实现要点：

- Query local projection tables only.
- 使用 `latest_sync_status()` 计算数据新鲜度。
- 只有当前用户 scope 允许时，才返回 `source_payload` 里的原始来源行。
- Compute stalled coils from `delay_hours` and missing next process.
- 优先复用现有 management/cost services。缺口径时输出 `missing_data`，不要编造经营估算数字。

- [ ] **Step 6: Implement router and mount it**

Create `backend/app/routers/factory_command.py` and include it in `backend/app/main.py` with prefix `/api/v1/factory-command`.

使用 manager/reviewer 权限，不开放 public access。

- [ ] **Step 7: Run backend target tests**

Run: `python -m pytest backend/tests/test_factory_command_service.py backend/tests/test_factory_command_routes.py backend/tests/test_mes_sync_lag.py -q`

Expected: PASS.

- [ ] **Step 8: Commit backend API slice**

Commit message: `feat: add factory command read api`

## Task 4: AI 上下文包、对话持久化与证据结构

**Files:**
- Create: `backend/app/models/assistant.py`
- Create: `backend/alembic/versions/0023_ai_assistant_state.py`
- Create: `backend/app/schemas/ai_assistant.py`
- Create: `backend/app/services/ai_context_service.py`
- Modify: `backend/app/routers/ai.py`
- Test: `backend/tests/test_ai_context_service.py`
- Test: `backend/tests/test_ai_assistant_routes.py`

- [ ] **Step 1: Write failing AI context tests**

Create `backend/tests/test_ai_context_service.py`.

Expected assertions:

- context pack includes scope, freshness, top abnormal coils, machine-line metrics, route refs, rules fired, and known missing data.
- context pack excludes credentials, raw password fields, and out-of-scope rows.
- stale `MES` data adds a `missing_data` entry and forces answer confidence below `high`.
- generated answer shape includes `answer`, `confidence`, `evidence_refs`, `missing_data`, `recommended_next_actions`, and `can_create_watch`.

- [ ] **Step 2: Write failing route tests**

Create `backend/tests/test_ai_assistant_routes.py`.

Cover:

- `GET /api/v1/ai/assistant/conversations`
- `POST /api/v1/ai/assistant/conversations`
- `GET /api/v1/ai/assistant/conversations/{id}/messages`
- `POST /api/v1/ai/assistant/conversations/{id}/messages`
- `POST /api/v1/ai/assistant/ask`
- existing `/api/v1/ai/conversations` still works for current frontend compatibility.

- [ ] **Step 3: Run AI tests and confirm RED**

Run: `python -m pytest backend/tests/test_ai_context_service.py backend/tests/test_ai_assistant_routes.py -q`

Expected: FAIL because persistent models and context service do not exist.

- [ ] **Step 4: Add AI state migration and models**

Create `backend/alembic/versions/0023_ai_assistant_state.py` and `backend/app/models/assistant.py`.

Tables:

- `ai_conversations`
- `ai_messages`
- `ai_context_packs`

字段跟随 spec。`payload`、`evidence_refs`、`missing_data` 和 `recommended_next_actions` 使用项目现有 JSON type helper。

- [ ] **Step 5: Implement context pack builder**

Create `backend/app/services/ai_context_service.py`.

实现要点：

- 按 intent 和 scope 生成窄上下文。
- 能通过 `factory_command_service` 取数时，不直接做宽表扫描。
- Save context packs with a source hash and expiry.
- Return deterministic fallback answers when LLM is disabled.
- When LLM is enabled, call existing `generate_llm_summary()` with strict JSON instructions and parse defensively.

- [ ] **Step 6: Persist conversations and messages**

Modify `backend/app/routers/ai.py`.

保留 `frontend/src/stores/ai-chat.js` 仍在使用的兼容 endpoints，再补 spec 里的 `/assistant/...` endpoints。

- [ ] **Step 7: Run AI target tests**

Run: `python -m pytest backend/tests/test_ai_context_service.py backend/tests/test_ai_assistant_routes.py backend/tests/test_assistant_routes.py -q`

Expected: PASS.

- [ ] **Step 8: Commit AI context slice**

Commit message: `feat: add evidence based ai assistant context`

## Task 5: 主动汇报与关注订阅

**Files:**
- Modify: `backend/app/models/assistant.py`
- Modify: `backend/alembic/versions/0023_ai_assistant_state.py`
- Create: `backend/app/services/ai_rules_service.py`
- Create: `backend/app/services/ai_briefing_service.py`
- Modify: `backend/app/schemas/ai_assistant.py`
- Modify: `backend/app/routers/ai.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_ai_briefing_service.py`
- Test: `backend/tests/test_ai_assistant_routes.py`

- [ ] **Step 1: Write failing briefing tests**

Create `backend/tests/test_ai_briefing_service.py`.

Expected assertions:

- opening briefing includes WIP, priority machine lines, inherited risk, and sync state.
- hourly inspection emits only changed or abnormal facts when configured to hide normal items.
- exception briefing triggers on route missing, delay hours, stale sync, weight anomaly, and destination anomaly.
- watchlist item for workshop/machine/coil/process/metric filters briefings to that scope.
- quiet hours 只抑制投递，不删除事件记录。

- [ ] **Step 2: Extend route tests for briefing and watchlist**

Add cases for:

- `GET /api/v1/ai/briefings`
- `POST /api/v1/ai/briefings/{id}/read`
- `POST /api/v1/ai/briefings/{id}/follow-up`
- `POST /api/v1/ai/briefings/generate-now`
- `GET /api/v1/ai/watchlist`
- `POST /api/v1/ai/watchlist`
- `PATCH /api/v1/ai/watchlist/{id}`
- `DELETE /api/v1/ai/watchlist/{id}`

- [ ] **Step 3: Run briefing tests and confirm RED**

Run: `python -m pytest backend/tests/test_ai_briefing_service.py backend/tests/test_ai_assistant_routes.py -q`

Expected: FAIL because rules, briefings, and watchlist are not implemented.

- [ ] **Step 4: Add rules engine**

Create `backend/app/services/ai_rules_service.py`.

Rules:

- `sync_stale`
- `route_missing`
- `delay_hours_high`
- `weight_anomaly`
- `destination_unknown`
- `cost_estimate_missing`
- `machine_line_cost_spike`

Return rule events with `severity`, `evidence_refs`, and `recommended_next_actions`.

- [ ] **Step 5: Add briefing service**

Create `backend/app/services/ai_briefing_service.py`.

Support:

- `opening_shift`
- `hourly_inspection`
- `exception_flash`
- `watchlist_update`
- `handover`
- `manager_briefing`

Store all generated events in `ai_briefing_events`.

- [ ] **Step 6: Wire routes and scheduler**

Modify `backend/app/routers/ai.py` for briefing/watchlist endpoints.

Modify `backend/app/main.py`:

- after `MES` sync, run rules.
- schedule hourly briefing generation.
- do not send external messages.

- [ ] **Step 7: Run backend AI briefing tests**

Run: `python -m pytest backend/tests/test_ai_briefing_service.py backend/tests/test_ai_assistant_routes.py -q`

Expected: PASS.

- [ ] **Step 8: Commit proactive AI slice**

Commit message: `feat: add proactive ai briefings and watchlist`

## Task 6: Factory Command Frontend Data Layer

**Files:**
- Create: `frontend/src/api/factory-command.js`
- Create: `frontend/src/api/ai-assistant.js`
- Create: `frontend/src/stores/factory-command.js`
- Modify: `frontend/src/stores/ai-chat.js`
- Modify: `frontend/src/stores/assistant.js`
- Create: `frontend/src/utils/factoryCommandFormatters.js`
- Create: `frontend/src/utils/aiAssistantContracts.js`
- Test: `frontend/tests/factoryCommandFormatters.test.js`
- Test: `frontend/tests/aiAssistantContracts.test.js`

- [ ] **Step 1: Write failing frontend contract tests**

Create `frontend/tests/factoryCommandFormatters.test.js`.

Expected assertions:

- freshness label maps `fresh`, `stale`, and `offline_or_blocked`.
- source label maps `mes_projection`, `local_entry`, and `mixed`.
- machine-line formatter preserves active tons, finished tons, stalled count, estimated cost, estimated gross margin, and missing cost data.
- destination formatter groups in-progress, finished stock, allocation, delivery, and unknown.

Create `frontend/tests/aiAssistantContracts.test.js`.

Expected assertions:

- answer normalization always returns `answer`, `confidence`, `evidenceRefs`, `missingData`, `recommendedNextActions`, and `canCreateWatch`.
- briefing normalization preserves severity, read status, follow-up status, evidence count, and expiry.
- watchlist normalization preserves type, scope key, trigger rules, quiet hours, frequency, channels, and active flag.

- [ ] **Step 2: Run frontend tests and confirm RED**

Run: `npm --prefix frontend test`

Expected: FAIL because the new files do not exist.

- [ ] **Step 3: Implement API modules**

Create `frontend/src/api/factory-command.js` for:

- `fetchFactoryCommandOverview`
- `fetchFactoryCommandWorkshops`
- `fetchFactoryCommandMachineLines`
- `fetchFactoryCommandCoils`
- `fetchFactoryCommandCoilFlow`
- `fetchFactoryCommandCostBenefit`
- `fetchFactoryCommandDestinations`
- `askFactoryCommandAi`

Create `frontend/src/api/ai-assistant.js` for assistant conversation, briefing, and watchlist endpoints.

- [ ] **Step 4: Implement stores and formatters**

Create `frontend/src/stores/factory-command.js`.

Modify:

- `frontend/src/stores/ai-chat.js` to prefer `/api/v1/ai/assistant/...` while keeping old endpoints as fallback.
- `frontend/src/stores/assistant.js` to load briefings and watchlist.

- [ ] **Step 5: Run frontend tests**

Run: `npm --prefix frontend test`

Expected: PASS.

- [ ] **Step 6: Commit frontend data slice**

Commit message: `feat: add factory command frontend data layer`

## Task 7: 工厂总览与生产大屏分支

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/config/manage-navigation.js`
- Create: `frontend/src/views/factory-command/FactoryCommandShell.vue`
- Create: `frontend/src/views/factory-command/FactoryOverview.vue`
- Create: `frontend/src/views/factory-command/ProductionFlowScreen.vue`
- Create: `frontend/src/views/factory-command/MachineLineScreen.vue`
- Create: `frontend/src/views/factory-command/CoilTrace.vue`
- Create: `frontend/src/views/factory-command/CostBenefitScreen.vue`
- Create: `frontend/src/views/factory-command/DestinationScreen.vue`
- Create: `frontend/src/views/factory-command/ExceptionMap.vue`
- Test: `frontend/tests/factoryCommandNavigation.test.js`
- Test: `frontend/tests/factoryCommandScreens.test.js`

- [ ] **Step 1: Write failing navigation and source tests**

Create `frontend/tests/factoryCommandNavigation.test.js`.

Expected assertions:

- routes exist for `/manage/overview`, `/manage/factory/flow`, `/manage/factory/machine-lines`, `/manage/factory/coils`, `/manage/factory/cost`, `/manage/factory/destinations`, `/manage/factory/exceptions`, `/manage/ai-assistant`.
- manager navigation exposes 工厂总览 and production branches.
- 数据接入 remains admin-only.
- AI 助手 is available as a secondary workbench and not the only way to see factory state.

Create `frontend/tests/factoryCommandScreens.test.js` using source checks for key labels and store calls.

- [ ] **Step 2: Run frontend tests and confirm RED**

Run: `npm --prefix frontend test`

Expected: FAIL because routes and views are missing.

- [ ] **Step 3: Build route shell**

Create `FactoryCommandShell.vue` with tabs or segmented navigation for:

- 工厂总览
- 生产流转
- 车间机列
- 卷级追踪
- 经营效益
- 库存去向
- 异常地图

界面保持克制、紧凑、可扫读。不要加营销文案或 onboarding copy。

- [ ] **Step 4: Build overview and flow screens**

Create `FactoryOverview.vue` and `ProductionFlowScreen.vue`.

Required visible data:

- data source and sync timestamp.
- all-factory WIP, today output, input, packaging, stock, risk count, estimated margin.
- coil flow from previous process to current process to next process to stock/allocation/delivery.
- stale/offline state shown in every first-screen header.

- [ ] **Step 5: Build machine-line and coil trace screens**

Create `MachineLineScreen.vue` and `CoilTrace.vue`.

Required visible data:

- workshop rows.
- machine-line rows.
- active tons, finished tons, stalled coils, cost estimate, margin estimate.
- search by batch/card/material.
- previous/current/next process and destination.

- [ ] **Step 6: Build cost, destination, and exception screens**

Create:

- `CostBenefitScreen.vue`
- `DestinationScreen.vue`
- `ExceptionMap.vue`

使用“估算”“经营口径”，不要使用财务利润口径的文案。

- [ ] **Step 7: Wire navigation**

Modify `frontend/src/router/index.js` and `frontend/src/config/manage-navigation.js`.

Suggested routes:

- `/manage/overview`
- `/manage/factory/flow`
- `/manage/factory/machine-lines`
- `/manage/factory/coils`
- `/manage/factory/cost`
- `/manage/factory/destinations`
- `/manage/factory/exceptions`
- `/manage/ai-assistant`

- [ ] **Step 8: Run tests and build**

Run: `npm --prefix frontend test`

Run: `npm --prefix frontend run build`

Expected: PASS.

- [ ] **Step 9: Commit big-screen slice**

Commit message: `feat: add factory command screens`

## Task 8: 常驻 AI 助手、主动汇报收件箱和关注列表

**Files:**
- Create: `frontend/src/components/ai/AiAssistantDrawer.vue`
- Create: `frontend/src/components/ai/AiBriefingInbox.vue`
- Create: `frontend/src/components/ai/AiEvidenceRefs.vue`
- Create: `frontend/src/components/ai/AiWatchlistPanel.vue`
- Modify: `frontend/src/layout/ManageShell.vue`
- Modify: `frontend/src/views/ai/AiWorkstation.vue`
- Modify: `frontend/src/components/review/ReviewAssistantDock.vue`
- Test: `frontend/tests/aiAssistantUiContract.test.js`

- [ ] **Step 1: Write failing UI contract tests**

Create `frontend/tests/aiAssistantUiContract.test.js`.

Expected assertions:

- `ManageShell.vue` imports or renders the assistant drawer.
- `AiAssistantDrawer.vue` includes context, conversation, evidence, briefings, and watchlist areas.
- `AiBriefingInbox.vue` supports unread, read, followed, and ignored states.
- `AiWatchlistPanel.vue` supports workshop, machine, coil, process, alloy/spec, and metric watch types.
- factory command screens include “问 AI” entry points with scoped context keys.

- [ ] **Step 2: Run UI tests and confirm RED**

Run: `npm --prefix frontend test`

Expected: FAIL because the drawer and inbox components do not exist.

- [ ] **Step 3: Implement assistant drawer**

Create `AiAssistantDrawer.vue`.

Behavior:

- stays available in management shell.
- opens from top-level button, screen “问 AI” actions, and briefing cards.
- sends current route/scope to the backend as context.
- shows evidence refs and missing data next to answers.
- freshness 为 stale 或 offline 时显示数据滞后提示。

- [ ] **Step 4: Implement briefing inbox and watchlist**

Create:

- `AiBriefingInbox.vue`
- `AiEvidenceRefs.vue`
- `AiWatchlistPanel.vue`

使用 Task 6 的 AI assistant store。

- [ ] **Step 5: Upgrade AI workstation**

Modify `frontend/src/views/ai/AiWorkstation.vue`:

- show conversation history.
- add tabs for 主动汇报 and 关注列表.
- 保留现有 streaming 体验。
- remove static “预测 / 分析 / 执行” phrasing if it no longer matches live capabilities.

- [ ] **Step 6: Connect screen-level Ask AI actions**

Modify factory command screens from Task 7 so:

- coil rows can ask about that coil.
- machine-line rows can ask about that line.
- cost cards can ask about estimate inputs and missing data.
- exception cards can ask for evidence and next actions.

- [ ] **Step 7: Run tests and build**

Run: `npm --prefix frontend test`

Run: `npm --prefix frontend run build`

Expected: PASS.

- [ ] **Step 8: Commit AI UI slice**

Commit message: `feat: add proactive ai assistant surface`

## Task 9: 填报端流转确认

**Files:**
- Modify: `backend/app/schemas/work_orders.py`
- Modify: `backend/app/services/work_order/entry.py`
- Create: `frontend/src/utils/coilFlowFields.js`
- Modify: `frontend/src/views/mobile/CoilEntryWorkbench.vue`
- Modify: `frontend/src/utils/coilEntryValidation.js`
- Test: `backend/tests/test_work_order_service.py`
- Test: `backend/tests/test_work_order_routes.py`
- Test: `frontend/tests/coilFlowFields.test.js`
- Test: `frontend/tests/coilEntryValidation.test.js`

- [ ] **Step 1: Write failing backend tests**

Extend `backend/tests/test_work_order_service.py`.

Expected assertions:

- create/update accepts `extra_payload.flow`.
- `flow.previous_workshop`, `flow.previous_process`, `flow.current_workshop`, `flow.current_process`, `flow.next_workshop`, `flow.next_process`, `flow_source`, and `flow_confirmed_at` are stored.
- unknown flow fields are rejected by template payload normalization.
- manual flow is marked `manual_pending_match`.
- submitted entries include flow payload in serialized output.

- [ ] **Step 2: Write failing frontend tests**

Create `frontend/tests/coilFlowFields.test.js`.

Expected assertions:

- `buildFlowPayload` maps external `MES` flow data into `extra_payload.flow`.
- missing next process requires manual next workshop/process.
- external route data locks previous/current/next fields by default.
- manual route source is `manual_pending_match`.

- [ ] **Step 3: Run flow tests and confirm RED**

Run: `python -m pytest backend/tests/test_work_order_service.py backend/tests/test_work_order_routes.py -q`

Run: `npm --prefix frontend test`

Expected: FAIL because flow payload support and UI utilities are missing.

- [ ] **Step 4: Implement backend payload support**

Modify `backend/app/schemas/work_orders.py` only if typed schema constraints are needed. Prefer storing the first version under `extra_payload.flow`.

Modify `backend/app/services/work_order/entry.py`:

- allow `flow` inside `extra_payload` for coil entry templates.
- preserve it during create, update, submit, and serialization.
- do not write flow data to external `MES`.

- [ ] **Step 5: Implement frontend flow utility and UI**

Create `frontend/src/utils/coilFlowFields.js`.

Modify `CoilEntryWorkbench.vue`:

- 有 card/coil 线索时加载流转建议。
- 在录入弹窗里展示 previous/current/next process。
- 当外部 `MES` 没有下工序时，前工序只填写 next workshop/process。
- include `extra_payload.flow` in submit payload.

- [ ] **Step 6: Run backend and frontend target tests**

Run: `python -m pytest backend/tests/test_work_order_service.py backend/tests/test_work_order_routes.py -q`

Run: `npm --prefix frontend test`

Expected: PASS.

- [ ] **Step 7: Commit fill terminal slice**

Commit message: `feat: add coil flow confirmation`

## Task 10: End-to-End Verification

**Files:**
- No new files expected unless a small doc update is needed.

- [ ] **Step 1: Run backend MES and AI target suites**

Run: `python -m pytest backend/tests/test_mvc_mes_adapter.py backend/tests/test_mes_sync_service.py backend/tests/test_factory_command_service.py backend/tests/test_factory_command_routes.py backend/tests/test_ai_context_service.py backend/tests/test_ai_briefing_service.py backend/tests/test_ai_assistant_routes.py -q`

Expected: PASS.

- [ ] **Step 2: Run backend full suite**

Run: `python -m pytest backend/tests -q`

Expected: PASS.

- [ ] **Step 3: Run frontend unit tests**

Run: `npm --prefix frontend test`

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run: `npm --prefix frontend run build`

Expected: PASS.

- [ ] **Step 5: Start frontend dev server**

Run: `npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173`

检查期间保持这个 terminal session 打开。

- [ ] **Step 6: Browser verification**

Open `http://127.0.0.1:5173`.

Inspect desktop and mobile widths:

- `/manage/overview`
- `/manage/factory/flow`
- `/manage/factory/machine-lines`
- `/manage/factory/coils`
- `/manage/factory/cost`
- `/manage/factory/destinations`
- `/manage/factory/exceptions`
- `/manage/ai-assistant`
- `/entry/coil/:businessDate/:shiftId`

Required checks:

- first screen is actual factory state, not a landing page.
- no text overlap on mobile or desktop.
- every factory screen shows data source, last sync time, and lag state.
- AI drawer can answer from current screen context.
- briefing inbox shows generated briefings and read/follow-up state.
- watchlist can create and disable a scoped subscription.
- flow confirmation payload appears in submitted coil entry.

- [ ] **Step 7: Validate no secret leakage**

Run: `git diff -- . ":(exclude)backend/.env" ":(exclude).env"`

Expected:

- no credentials in code, tests, snapshots, or docs.
- external `MES` credentials exist only in local env.

- [ ] **Step 8: Final commit**

Commit message: `feat: deliver factory command center with ai assistant`

## Acceptance Criteria

- 管理者能在 10 秒内看到全厂、车间、机列、卷流转、库存去向和异常。
- 每张大屏都有数据源、最后同步时间、滞后秒数和 freshness 状态。
- 机列级展示当前做了多少、完成多少、停滞多少、成本估算和毛差估算，文案始终标明经营估算。
- 卷级追踪能回答前工序、当前工序、下工序、计划去向和最终去向。
- 填报端能保存 `extra_payload.flow`，外部 `MES` 可用时自动带出路线，不可用时允许手填下道去向。
- AI 助手常驻管理端，支持围绕页面、卷、机列、车间多轮对话。
- 主动汇报支持开班简报、小时巡检、异常快报、关注对象汇报、交接摘要和管理层简报。
- 用户能订阅车间、机列、卷/批号、工艺、合金/规格或指标。
- AI 回答和主动汇报都能点回证据，数据滞后、成本缺失、证据不足时明确标出。
- AI 不自动提交、删除、回写外部 `MES`、修改权限或发送外部消息。

## Rollback

- 设置 `MES_ADAPTER=null` 可停止外部 `MES` 拉取，前端显示本地数据或 stale 状态。
- 停用 AI 主动汇报调度时，保留对话和历史 briefings，不删除已生成记录。
- 新增路由可以从导航隐藏，旧 `/manage/overview`、`/manage/factory`、`/manage/ai` 保持可访问。
- 数据库迁移的 downgrade 删除新增投影/AI 表和新增列，执行前必须备份生产库。
