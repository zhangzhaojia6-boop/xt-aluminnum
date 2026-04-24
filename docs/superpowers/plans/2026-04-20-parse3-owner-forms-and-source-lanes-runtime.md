# Parse 3 Owner Forms And Source Lanes Runtime Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` or follow this plan step-by-step with verification after each slice.

**Goal:** 在 parse2 已稳定的主操“一岗一表”基线上，把 `inventory_keeper / utility_manager / contracts` 从共享 owner-only 补录页推进成真正的一岗一表，并为审阅端补稳定的来源泳道。

**Architecture:** 先不扩业务边界，优先拆 owner-only 的前端语义和字段分组，让同一个 `DynamicEntryForm.vue` 根据岗位桶渲染不同的标题、步骤和字段组；再补专项岗位 E2E，确保三类角色是真实可用；最后再进入审阅端来源泳道接口与卡片。

**Tech Stack:** Vue 3, Element Plus, Pinia, FastAPI, pytest, Playwright, Docker Compose

---

## File Map

- Create: `docs/superpowers/plans/2026-04-20-parse3-owner-forms-and-source-lanes-runtime.md` — 当前计划
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue` — owner-only 岗位专属标题、步骤、字段分组
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py` — 静态文案与结构断言
- Modify: `frontend/e2e/owner-only-inventory-dashboard.spec.js` — inventory 一岗一表断言
- Modify: `frontend/e2e/owner-only-utility-workshop.spec.js` — utility 一岗一表断言
- Modify: `frontend/e2e/owner-only-contract-dashboard.spec.js` — contracts 一岗一表断言
- Modify: `.omx/notepad.md` — 记录 parse3 首刀落点

## Task 1: Owner-Only 专属工作台语义

**Files:**
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: 先补失败断言，锁定三类专项岗位不再共用同一套补录文案**

验证点：

- `inventory_keeper` 应强调 `今日入库 / 今日发货 / 结存与备料`
- `utility_manager` 应强调 `用电 / 天然气 / 用水`
- `contracts` 应强调 `当日合同 / 月累计与余合同 / 投料与坯料`
- owner-only 页头、步骤标题、字段分组不再只是通用 `补录 / 本班原始值 / 补录字段`

- [ ] **Step 2: 用最小实现引入岗位配置**

建议实现：

- 在 `DynamicEntryForm.vue` 内新增 `OWNER_MODE_CONFIG`
- 用 `role_bucket` 决定：
  - 页头标题
  - 页头说明
  - 核心步骤标题
  - 补充步骤标题
  - 字段分组标题
- 继续复用同一组件，不单独拆新页面

- [ ] **Step 3: 为 owner-only 字段增加岗位分组函数**

建议实现：

- `inventory_keeper`：
  - `今日入库`
  - `今日发货`
  - `结存与备料`
- `utility_manager`：
  - `用电`
  - `天然气`
  - `用水`
- `contracts`：
  - `当日合同`
  - `月累计与余合同`
  - `投料与坯料`

## Task 2: 专项岗位 E2E 对齐

**Files:**
- Modify: `frontend/e2e/owner-only-inventory-dashboard.spec.js`
- Modify: `frontend/e2e/owner-only-utility-workshop.spec.js`
- Modify: `frontend/e2e/owner-only-contract-dashboard.spec.js`

- [ ] **Step 1: 对齐专项岗位真实文案与字段组**

验证点：

- inventory 登录后能看到 `今日入库 / 今日发货 / 结存与备料`
- utility 登录后能看到 `用电 / 天然气 / 用水`
- contracts 登录后能看到 `当日合同 / 月累计与余合同 / 投料与坯料`

- [ ] **Step 2: 跑专项岗位 E2E**

Run:

```powershell
cd frontend && npx playwright test e2e/owner-only-inventory-dashboard.spec.js e2e/owner-only-utility-workshop.spec.js e2e/owner-only-contract-dashboard.spec.js
```

## Task 3: 首刀回归与交接

**Files:**
- Modify: `.omx/notepad.md`

- [ ] **Step 1: 跑 parse3 首刀回归**

Run:

```powershell
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q
docker compose run --rm backend sh -lc "pytest -q"
cd frontend && npm run build
cd frontend && npx playwright test e2e/owner-only-inventory-dashboard.spec.js e2e/owner-only-utility-workshop.spec.js e2e/owner-only-contract-dashboard.spec.js
```

- [ ] **Step 2: 记录 parse3 首刀结果到 `.omx/notepad.md`**

记录内容：

- 哪三类岗位已完成一岗一表语义分离
- 最新测试结果
- 下一步进入审阅端来源泳道
