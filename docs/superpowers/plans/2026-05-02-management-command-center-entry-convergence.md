# 管理端态势与填报收敛 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把管理端收敛成一屏可扫的工厂实时态势，并用 TDD 锁住后端状态口径、前端导航/矩阵逻辑、移动填报重量校验。

**Architecture:** 后端继续使用 `realtime_service.aggregate_live_payload` 输出聚合口径，新增缺报/关注单元统计和单元格状态语义。前端提取 `managementCommandCenter` 工具函数供页面和 Node 单测共用，`LiveDashboard` 改为工厂态势板，导航降级低频入口。移动按卷录入只补最小重量业务校验。

**Tech Stack:** FastAPI, pytest, Vue 3, Element Plus, npm node:test, Vite

---

### Task 1: 后端实时聚合状态口径

**Files:**
- Modify: `backend/app/services/realtime_service.py`
- Modify: `backend/app/schemas/realtime.py`
- Test: `backend/tests/test_realtime_service_contract.py`

- [ ] **Step 1: Write failing backend tests**

Create `backend/tests/test_realtime_service_contract.py` with lightweight workshop/machine/shift objects and call `aggregate_live_payload`.

Expected assertions:
- `overall_progress.missing_cell_count` counts applicable `not_started` cells.
- `overall_progress.attention_cell_count` counts not fully submitted cells and cells with attendance exceptions.
- each shift has `status_tone` and `status_text`.
- `not_applicable` cells remain muted and are not counted in totals.

- [ ] **Step 2: Run the new backend test and confirm RED**

Run: `python -m pytest backend/tests/test_realtime_service_contract.py -q`

Expected: FAIL because the new count and status fields do not exist.

- [ ] **Step 3: Implement minimal backend contract**

Update `aggregate_live_payload` to compute:
- `missing_cell_count`
- `attention_cell_count`
- `completion_rate`
- `status_tone`
- `status_text`

Update `LiveShiftCellOut` with `is_applicable`, `status_tone`, `status_text`.

- [ ] **Step 4: Run backend target tests and confirm GREEN**

Run: `python -m pytest backend/tests/test_realtime_service_contract.py backend/tests/test_realtime_routes.py -q`

- [ ] **Step 5: Commit backend TDD slice**

Commit message: `feat: 收敛实时聚合状态口径`

---

### Task 2: 前端管理态势工具函数与导航收敛

**Files:**
- Create: `frontend/src/utils/managementCommandCenter.js`
- Modify: `frontend/src/config/manage-navigation.js`
- Test: `frontend/tests/managementCommandCenter.test.js`

- [ ] **Step 1: Write failing frontend tests**

Create `frontend/tests/managementCommandCenter.test.js`.

Expected assertions:
- `buildCommandCenterSummary` returns submitted/total/missing/attention/output/yield/dataSourceLabel.
- `statusToneForCell` maps `all_submitted`, `in_progress`, `not_started`, `not_applicable`, attendance exception.
- `sortWorkshopsForCommandCenter` puts workshops with attention cells first.
- `manageNavGroups` for review-only users exposes high-frequency groups and hides AI/cost/settings/imports.

- [ ] **Step 2: Run frontend tests and confirm RED**

Run: `npm --prefix frontend test`

Expected: FAIL because the utility file and navigation contract are not yet implemented.

- [ ] **Step 3: Implement helper functions and navigation contract**

Add `frontend/src/utils/managementCommandCenter.js`.

Update `manage-navigation.js`:
- first-level groups: 总览、工厂状态、填报审核、日报交付、异常质量、主数据。
- AI/cost/settings/imports/governance stay admin-only or low-frequency admin group.
- keep route paths valid.

- [ ] **Step 4: Run frontend unit tests and confirm GREEN**

Run: `npm --prefix frontend test`

- [ ] **Step 5: Commit frontend helper/navigation slice**

Commit message: `feat: 收敛管理端导航和态势工具`

---

### Task 3: 管理端工厂实时态势页面

**Files:**
- Modify: `frontend/src/views/reports/LiveDashboard.vue`
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue`
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: Update LiveDashboard**

Use the helper functions from Task 2.

Change visible identity:
- title: `工厂实时态势`
- tags: `全厂`, `机列填报`, `实时状态`
- remove ops/probe wording from the first screen.

Top strip must show:
- 今日产出
- 提交进度
- 缺报单元
- 关注单元
- 数据源
- 更新时间

Matrix cells must show status text and color, not only symbols.

- [ ] **Step 2: Clean FactoryDirector dead hidden sections**

Remove `display:none` war-room/ribbon/legacy hero sections and unused imports/computed values created solely for those hidden blocks.

- [ ] **Step 3: Route old ops URL safely**

Keep `/manage/admin/settings` usable, but make primary factory status route point to the real-time attitude board.

- [ ] **Step 4: Run build**

Run: `npm --prefix frontend run build`

- [ ] **Step 5: Commit UI slice**

Commit message: `refactor: 打造管理端工厂实时态势`

---

### Task 4: 移动按卷录入重量校验

**Files:**
- Create or modify: `frontend/src/utils/coilEntryValidation.js`
- Modify: `frontend/src/views/mobile/CoilEntryWorkbench.vue`
- Test: `frontend/tests/coilEntryValidation.test.js`

- [ ] **Step 1: Write failing validation tests**

Expected assertions:
- missing tracking card returns required message.
- missing input/output weight returns required message.
- zero or negative weight returns invalid message.
- output weight greater than input weight returns invalid message.
- valid payload returns `null`.

- [ ] **Step 2: Run frontend tests and confirm RED**

Run: `npm --prefix frontend test`

- [ ] **Step 3: Implement validation and wire into submit**

Create `validateCoilEntryForm(form)` and call it in `submitCoil`.

- [ ] **Step 4: Run frontend tests and confirm GREEN**

Run: `npm --prefix frontend test`

- [ ] **Step 5: Commit mobile validation slice**

Commit message: `fix: 加强按卷录入重量校验`

---

### Task 5: Final verification

**Files:**
- No new files expected.

- [ ] **Step 1: Run backend full suite**

Run: `python -m pytest backend/tests -q`

- [ ] **Step 2: Run frontend unit tests**

Run: `npm --prefix frontend test`

- [ ] **Step 3: Run frontend build**

Run: `npm --prefix frontend run build`

- [ ] **Step 4: Start dev server and visually inspect**

Run: `npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173`

Inspect desktop and mobile widths for:
- no overlapping text
- top status strip visible
- matrix cells readable
- low-frequency nav not crowding first-level menu

- [ ] **Step 5: Commit any final polish**

Commit message: `style: 优化工厂态势视觉层级`
