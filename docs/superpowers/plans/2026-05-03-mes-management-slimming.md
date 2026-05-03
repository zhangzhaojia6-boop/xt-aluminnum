# MES 接入健康与管理端瘦身 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `鑫泰铝业 数据中枢` 的管理端先回答三件事：外部 `MES` 链接是否健康、数据是否新鲜、管理者是否只看到运行决策需要的入口；同时保留班次和审核的后端兜底能力。

**Architecture:** 后端把 `MES` 接入状态收敛为稳定 health/freshness contract，投影缺迁移或未配置时不让工厂总览 500；工厂指挥中心接口逐步从全量内存扫描改成数据库聚合和分页；前端主导航收窄为工厂运行、异常、AI 和必要配置，班次中心退出主路径，审核页改为异常与补录语义。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, Vue 3, Element Plus, node:test, Vite

---

## Scope

Source spec: `docs/superpowers/specs/2026-05-03-mes-management-slimming-design.md`

本轮只做“接得顺、看得清、少入口、少全量”的改进，不新增外部系统能力。

In scope:

- `MES_ADAPTER=null`、投影迁移缺失、同步失败、同步滞后都返回结构化状态。
- 工厂总览和车间机列不依赖默认全量卷级扫描。
- 卷级列表默认分页，首屏不拉整表。
- 普通管理者主导航不再出现班次中心、填报审核、导入历史、别名映射、系统设置、权限治理、重复成本入口。
- 管理员仍能进入主数据、用户、数据接入配置。
- `ReviewTaskCenter.vue` 从“待审/已审/批量审核”改为“异常与补录”。
- `/manage/shift`、`/review/*`、`/admin/*` 保留兼容路径，不让旧入口断链。

Out of scope:

- 不把产品命名为 `MES`。
- 不回写外部 `MES`。
- 不删除 `ShiftConfig`、review 状态字段、审计字段或兼容路由。
- 不新增第三方依赖。
- 不重写整套前端。
- 不新增说明型页面或营销型文案。

---

## Task 1: MES 接入健康 contract

**Files:**

- Modify: `backend/app/services/mes_sync_service.py`
- Modify: `backend/app/services/factory_command_service.py`
- Modify: `backend/app/core/health.py`
- Modify: `backend/app/schemas/factory_command.py`
- Test: `backend/tests/test_mes_sync_lag.py`
- Test: `backend/tests/test_health.py`
- Test: `backend/tests/test_factory_command_service.py`

- [ ] **Step 1: Write failing backend tests**

Add tests that pin these states:

- `MES_ADAPTER=null` returns `status='unconfigured'`, `configured=False`, `migration_ready=True`, `action_required='configure_mes'`; readiness remains HTTP 200.
- missing projection table or column returns `status='migration_missing'`, `migration_ready=False`, `action_required='run_migration'`; factory command freshness does not raise.
- latest sync run failed returns `status='failed'`, keeps `last_error`, and sets `action_required='check_vendor'` or `check_credentials` from the existing run metadata.
- `lag_seconds <= 300` maps to `fresh`; `300 < lag_seconds <= 900` maps to `stale`; `lag_seconds > 900` remains stale but carries high-risk tone data for the frontend.

Use monkeypatches for SQLAlchemy `ProgrammingError` and `OperationalError` so the test does not depend on the local database staying behind migration `0022`.

- [ ] **Step 2: Run the new backend tests and confirm RED**

Run:

```powershell
python -m pytest backend/tests/test_mes_sync_lag.py backend/tests/test_health.py backend/tests/test_factory_command_service.py -q
```

Expected: FAIL because the new `configured`, `migration_ready`, `action_required`, and migration-missing handling do not exist.

- [ ] **Step 3: Implement the minimal status builder**

In `mes_sync_service.py`:

- Add a small helper that normalizes sync facts into:
  - `configured`
  - `migration_ready`
  - `status`
  - `source`
  - `lag_seconds`
  - `last_synced_at`
  - `last_event_at`
  - `last_error`
  - `action_required`
- Catch only database shape failures around projection queries: missing table, missing column, `ProgrammingError`, `OperationalError`.
- Keep genuine unexpected exceptions visible to tests unless they are part of the projection-read path.

In `factory_command_service.py`:

- Make `build_freshness` consume the normalized status.
- Keep old keys used by AI tests, especially `lag_seconds`, `last_run_status`, and `status`.
- Do not make `unconfigured` a fatal state.

In `health.py`:

- If `MES_ADAPTER` is `null`, report `checks.mes_sync='unconfigured'` and keep overall readiness true.
- If the adapter is enabled and status is `migration_missing` or `failed`, include details and set readiness according to existing hard-gate behavior.

- [ ] **Step 4: Run target backend tests and confirm GREEN**

Run:

```powershell
python -m pytest backend/tests/test_mes_sync_lag.py backend/tests/test_health.py backend/tests/test_factory_command_service.py backend/tests/test_factory_command_routes.py -q
```

- [ ] **Step 5: Commit the backend health slice**

Commit message: `feat: 收敛 MES 接入健康状态`

---

## Task 2: 工厂指挥中心查询减负

**Files:**

- Modify: `backend/app/services/factory_command_service.py`
- Modify: `backend/app/routers/factory_command.py`
- Modify: `backend/app/schemas/factory_command.py`
- Test: `backend/tests/test_factory_command_service.py`
- Test: `backend/tests/test_factory_command_routes.py`
- Test: `backend/tests/test_ai_context_service.py`
- Test: `backend/tests/test_ai_briefing_service.py`

- [ ] **Step 1: Write failing tests for bounded reads**

Add tests for:

- `list_coils(db)` defaults to a bounded page and never returns all rows when more than the default limit exists.
- `list_coils(db, limit=20, offset=40, workshop='冷轧')` passes filter and paging through the service.
- route `/api/v1/factory-command/coils` accepts `limit`, `offset`, `workshop`, `destination`, and `query`.
- small-sample outputs from `build_overview`, `list_workshops`, and `list_machine_lines` stay compatible with existing tests.

Keep the current fake DB tests for behavior, and add a focused SQLite-backed service test only where SQL aggregation needs to be proven.

- [ ] **Step 2: Run query tests and confirm RED**

Run:

```powershell
python -m pytest backend/tests/test_factory_command_service.py backend/tests/test_factory_command_routes.py -q
```

Expected: FAIL because `list_coils` has no public paging contract and route params are not wired through.

- [ ] **Step 3: Implement paging and scoped query helpers**

Implement in small steps:

- Add `limit=100`, `offset=0`, `workshop=None`, `destination=None`, `query=None` to `list_coils`.
- Clamp `limit` to a safe maximum such as `500`.
- Push filters into the SQL query for real SQLAlchemy sessions.
- Preserve the fake DB path used by existing tests so unit tests remain fast.
- For `build_overview`, `list_workshops`, and `list_machine_lines`, introduce query helpers that aggregate in SQL for real sessions and fall back to the existing in-memory behavior only for fake DB tests.

Do not change response field names unless a test proves the old contract cannot support paging.

- [ ] **Step 4: Verify AI context still receives narrow data**

Run:

```powershell
python -m pytest backend/tests/test_ai_context_service.py backend/tests/test_ai_briefing_service.py -q
```

Expected: GREEN. If failures show that AI depends on all coils, update AI context assembly to request only a small exception-first page.

- [ ] **Step 5: Commit the query slice**

Commit message: `perf: 降低工厂指挥中心默认查询量`

---

## Task 3: 管理端导航瘦身

**Files:**

- Modify: `frontend/src/config/manage-navigation.js`
- Modify: `frontend/src/router/index.js`
- Test: `frontend/tests/factoryCommandNavigation.test.js`
- Test: `backend/tests/test_mobile_entry_copy_consistency.py`
- Test: `backend/tests/test_reference_command_center_spec.py`

- [ ] **Step 1: Write failing navigation tests**

Add or update tests so ordinary review users see:

- `工厂总览`
- `生产流转`
- `车间机列`
- `卷级追踪`
- `库存去向`
- `异常地图`
- `AI 助手`

Assert ordinary review users do not see:

- `班次中心`
- `填报审核`
- `导入历史`
- `别名映射`
- `系统设置`
- `权限治理`
- `成本核算与效益中心`

Assert admin users still see:

- `主数据与模板中心`
- `用户管理`
- `数据接入`

- [ ] **Step 2: Run navigation tests and confirm RED**

Run:

```powershell
npm --prefix frontend test -- frontend/tests/factoryCommandNavigation.test.js
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -q
```

Expected: FAIL because the current nav still exposes retired labels and old copy tests still expect `审阅中心` wording.

- [ ] **Step 3: Update navigation config**

In `manage-navigation.js`:

- Remove `班次中心` from ordinary nav.
- Replace `填报审核` group with an exception-oriented route only if it is still needed in the main nav; prefer grouping under `异常质量`.
- Keep a single cost/benefit entry. If it is still estimation-only, keep `经营效益` and remove `成本核算与效益中心`.
- Collapse `导入历史`、`别名映射`、`字段映射` under one admin `数据接入` entry.
- Collapse `系统设置` and `权限治理` under admin configuration routes, not ordinary nav.

In `router/index.js`:

- Keep old paths as redirects or aliases.
- Ensure `/manage/shift` resolves without a blank page, preferably to `/manage/master`.

- [ ] **Step 4: Update source-copy tests**

Update static tests that intentionally check frontend copy so they match the new contract:

- `ReviewTaskCenter.vue` should be checked for `异常与补录`, not `待审` and `已审`.
- Forbidden labels should be asserted absent from ordinary navigation.
- Keep tests that protect route compatibility.

- [ ] **Step 5: Commit the navigation slice**

Commit message: `refactor: 精简管理端主导航`

---

## Task 4: 工厂总览数据新鲜度展示

**Files:**

- Modify: `frontend/src/views/factory-command/FactoryOverview.vue`
- Modify: `frontend/src/api/factory-command.js`
- Modify: `frontend/src/stores/factory-command.js`
- Modify: `frontend/src/utils/factoryCommandFormatters.js`
- Test: `frontend/tests/factoryCommandFormatters.test.js`
- Test: `frontend/tests/factoryCommandScreens.test.js`

- [ ] **Step 1: Write failing frontend status tests**

Cover formatter behavior for:

- `fresh` -> `实时`
- `stale` with lag -> `滞后 X 分钟`
- `unconfigured` -> `未配置`
- `migration_missing` -> `投影未就绪`
- `failed` -> `同步失败`

Cover UI contract:

- Factory overview renders the status chip from backend freshness.
- It keeps showing local or last-known production data when status is `unconfigured`, `stale`, or `failed`.
- It does not render stack traces, raw SQL errors, or long explanatory text.

- [ ] **Step 2: Run frontend tests and confirm RED**

Run:

```powershell
npm --prefix frontend test -- frontend/tests/factoryCommandFormatters.test.js frontend/tests/factoryCommandScreens.test.js
```

Expected: FAIL because the new freshness states and labels are not fully mapped.

- [ ] **Step 3: Implement compact status rendering**

Update frontend data mapping:

- Normalize unknown backend statuses to `未就绪`.
- Display one compact state chip near the overview metrics.
- Use existing color/token patterns from the factory command views.
- Do not add helper paragraphs or onboarding copy.
- Do not expose `last_error` to ordinary users.

- [ ] **Step 4: Verify build**

Run:

```powershell
npm --prefix frontend run build
```

- [ ] **Step 5: Commit the freshness UI slice**

Commit message: `feat: 展示 MES 数据新鲜度`

---

## Task 5: 班次与审核降级

**Files:**

- Modify: `frontend/src/views/review/ReviewTaskCenter.vue`
- Modify: `frontend/src/views/shift/ShiftCenter.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/mocks/centerMockData.js`
- Test: `frontend/tests/reviewTaskCenter.test.js`
- Test: `frontend/tests/factoryCommandNavigation.test.js`
- Test: `backend/tests/test_frontend_refactor_blueprint.py`
- Test: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: Write failing tests for removed workflow language**

Assert `ReviewTaskCenter.vue` does not contain:

- `待审`
- `已审`
- `批量通过`
- `批量驳回`
- `审阅中心`

Assert it does contain:

- `异常与补录`
- `缺报`
- `退回`
- `差异`
- `同步滞后`

Assert `ShiftCenter.vue` no longer exposes production shift import actions in the management main path.

- [ ] **Step 2: Run copy tests and confirm RED**

Run:

```powershell
npm --prefix frontend test -- frontend/tests/reviewTaskCenter.test.js frontend/tests/factoryCommandNavigation.test.js
python -m pytest backend/tests/test_frontend_refactor_blueprint.py backend/tests/test_mobile_entry_copy_consistency.py -q
```

Expected: FAIL because old review and shift wording is still present.

- [ ] **Step 3: Update review surface to exception handling**

In `ReviewTaskCenter.vue`:

- Rename the module to `异常与补录`.
- Replace “待审/已审” buckets with operational states such as missing, returned, diff, stale, override-required.
- Remove bulk approval buttons.
- Keep individual admin override only if the existing backend action requires a reason.
- Keep export only if it exports exception records, not approval queues.

In `centerMockData.js`:

- Rename mock keys and visible labels to exception handling vocabulary.
- Remove mock rows that only exist to demonstrate batch approval.

- [ ] **Step 4: Downgrade shift center**

In `ShiftCenter.vue` and router:

- Keep shift configuration available through master data.
- Remove or hide production shift import operations from the management main path.
- Redirect `/manage/shift` to `/manage/master` or render a compact configuration-only view.
- Keep backend `ShiftConfig` untouched.

- [ ] **Step 5: Commit the downgrade slice**

Commit message: `refactor: 降级班次和人工审核入口`

---

## Task 6: End-to-end verification and cleanup

**Files:**

- Review changed backend/frontend files from Tasks 1-5.
- Update only tests or docs directly affected by the new contract.

- [ ] **Step 1: Run targeted backend suite**

Run:

```powershell
python -m pytest backend/tests/test_mes_api_contract.py backend/tests/test_rest_api_mes_adapter.py backend/tests/test_mvc_mes_adapter.py backend/tests/test_mes_sync_service.py backend/tests/test_mes_sync_lag.py backend/tests/test_health.py backend/tests/test_factory_command_service.py backend/tests/test_factory_command_routes.py backend/tests/test_ai_context_service.py backend/tests/test_ai_briefing_service.py -q
```

- [ ] **Step 2: Run frontend unit and build checks**

Run:

```powershell
npm --prefix frontend test
npm --prefix frontend run build
```

- [ ] **Step 3: Run route smoke checks**

Run:

```powershell
npm --prefix frontend run e2e -- e2e/admin-surface.spec.js e2e/review-runtime.spec.js
```

If those specs do not exist in this checkout, list the available `frontend/e2e/*.spec.js` files and run the closest management/review route smoke specs.

- [ ] **Step 4: Run the project test suite**

Run:

```powershell
python -m pytest -q
```

If the full suite exposes pre-existing fixture or environment failures, record the exact failing test names and still fix any failure caused by this implementation.

- [ ] **Step 5: Manual browser verification**

Start the dev server:

```powershell
npm --prefix frontend run dev -- --host 127.0.0.1
```

Verify in browser:

- `/manage/overview` shows factory overview and one compact data status.
- ordinary review role nav does not show retired entries.
- admin role can still reach master data, users, and data access.
- `/manage/shift` does not produce a blank page.
- `异常与补录` has no batch approval workflow.

- [ ] **Step 6: Final commit**

Commit message: `chore: 验证 MES 健康与管理端瘦身`

---

## Rollback Plan

- Backend health fields are additive. If a caller breaks, keep new fields and restore old aliases in `build_freshness`.
- Query optimization affects reads only. Revert `factory_command_service.py` if aggregation differs from the old in-memory result.
- Navigation changes can be reverted in `frontend/src/config/manage-navigation.js` while keeping route redirects.
- Review and shift copy changes do not alter persisted data.

---

## Success Criteria

- `check_mes_sync_lag.py --json` no longer crashes solely because projection columns are missing; it returns a structured state or the tests cover the same service path.
- `MES_ADAPTER=null` is visible as unconfigured and does not mark the whole app down.
- Factory overview and machine-line endpoints do not default to full coil-list reads.
- Ordinary management nav no longer exposes `班次中心`、`填报审核`、`导入历史`、`别名映射`、`系统设置`、`权限治理`、`成本核算与效益中心`.
- `ReviewTaskCenter.vue` no longer presents an artificial manual approval queue.
- Targeted backend tests, frontend unit tests, frontend build, and the project backend suite have been run and recorded.
