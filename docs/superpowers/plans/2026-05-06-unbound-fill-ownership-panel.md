# Unbound Fill Ownership Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在管理端实时态势首屏明确展示“已进系统但未归属真实机列”的卷级直录数据，让管理者能快速判断填报数据没有吃到机列口径的原因。

**Architecture:** 不新增后端接口，复用 `/api/v1/aggregation/live` 返回的 `workshops[].machines[]`。前端 `managementCommandCenter.js` 增加纯函数汇总未绑定填报，`LiveDashboard.vue` 渲染一个紧凑运行面板；管理员可从面板进入用户管理配置账号。

**Tech Stack:** Vue 3 + Element Plus + node:test；不新增依赖。

---

## Task 1: Unbound Fill Summary Function

**Files:**
- Modify: `frontend/src/utils/managementCommandCenter.js`
- Test: `frontend/tests/managementCommandCenter.test.js`

- [x] **Step 1: Write failing tests**

Add a test for `buildUnboundFillSummary()` using current production-like rows:
- 2050 冷轧车间未绑定白班 9100 吨
- 2050 冷轧车间未绑定夜班 74110 吨
- 精整车间未绑定夜班 37250 吨
- 已绑定机列不计入

Expected summary:
- `rowCount=3`
- `workshopCount=2`
- `shiftCount=2`
- `output=120460`
- top row sorted by output desc

Run: `npm --prefix frontend test -- managementCommandCenter.test.js`
Expected: FAIL because the helper is not exported.

- [x] **Step 2: Implement helper**

Add `buildUnboundFillSummary(workshops = [], limit = 3)`. Treat a machine as unbound when:
- `machine.machine_binding_status === 'unbound'`
- or `machine.machineBindingStatus === 'unbound'`
- or `Number(machine.machine_id) < 0`

Keep the helper pure and reuse existing `numberValue()`.

## Task 2: Live Dashboard Panel

**Files:**
- Modify: `frontend/src/views/reports/LiveDashboard.vue`
- Test: `frontend/tests/managementCommandCenter.test.js`

- [x] **Step 1: Write failing source contract assertions**

Assert `LiveDashboard.vue` contains:
- `未绑定填报归属`
- `unboundFillSummary`
- `live-unbound-fill`
- `绑定账号`

- [x] **Step 2: Render the panel**

Place the panel between the MES connection strip and the existing “卷级直录分布” section. Show:
- total unbound output
- workshop count, shift count, row count
- top 3 workshop/shift rows
- admin-only link to `/manage/admin/users`

Use the existing restrained dashboard style, fixed compact spacing, and amber risk tone.

## Task 3: Verification And Delivery

**Files:**
- Verify: frontend tests, frontend build, frontend contract marker, deploy docs if deployed

- [x] **Step 1: Focused test**

Run:
```powershell
npm --prefix frontend test -- managementCommandCenter.test.js
```

- [x] **Step 2: Broader checks**

Run:
```powershell
npm --prefix frontend test
python -m pytest backend/tests -m frontend_contract -q
npm --prefix frontend run build
git diff --check
```

- [x] **Step 3: Commit, push, deploy, probe**

If verification passes, commit with `feat: 展示未绑定填报归属`, push `main`, deploy through `scripts/deploy_systemd_host.sh --pull http://8.140.218.13`, then verify the production `LiveDashboard` asset contains the new markers.
