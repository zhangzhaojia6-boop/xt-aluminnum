# Unbound Account Filter Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让管理端“未绑定填报归属”面板的“绑定账号”入口直达用户管理页的未绑定账号筛选结果。

**Architecture:** 不新增后端接口，复用现有 `/api/v1/users/?machine_binding=unbound` 能力。`LiveDashboard.vue` 只负责带查询参数跳转，`UserManagement.vue` 只负责从路由查询参数初始化现有筛选状态。

**Tech Stack:** Vue 3 + Vue Router + node:test；不新增依赖。

---

## Task 1: Contract Tests

**Files:**
- Modify: `frontend/tests/managementCommandCenter.test.js`
- Modify: `frontend/tests/userDingtalkSync.test.js`

- [x] **Step 1: Add source contract assertions**

Assert:
- `LiveDashboard.vue` links to `/manage/admin/users` with `machine_binding: 'unbound'`.
- `UserManagement.vue` imports `useRoute`, reads `route.query.machine_binding`, and calls `applyRouteFilters()` before initial `load()`.

Run:
```powershell
npm --prefix frontend test -- managementCommandCenter.test.js userDingtalkSync.test.js
```

Result: FAIL before implementation; PASS after adding `unboundAccountRoute` and `applyRouteFilters()`.

## Task 2: Link And Route Query Handling

**Files:**
- Modify: `frontend/src/views/reports/LiveDashboard.vue`
- Modify: `frontend/src/views/master/UserManagement.vue`

- [x] **Step 1: Add filtered link target**

In `LiveDashboard.vue`, replace the static users link with a computed route target:
- path: `/manage/admin/users`
- query: `machine_binding=unbound`
- preserve `desktop=1` when the current route has it, so compact/mobile visual checks stay on management surface.

- [x] **Step 2: Apply query filters on users page**

In `UserManagement.vue`, add `useRoute()` and an `applyRouteFilters()` helper. Accept `machine_binding=bound|unbound`; if `bound_machine_id` is present and numeric, set `boundMachineId` and force `machineBinding='bound'`. When `machine_binding=unbound`, clear `boundMachineId`.

## Task 3: Verification And Delivery

**Files:**
- Verify: frontend focused tests, frontend full tests, frontend build, route marker in production asset

- [x] **Step 1: Focused checks**

Run:
```powershell
npm --prefix frontend test -- managementCommandCenter.test.js userDingtalkSync.test.js
```

- [x] **Step 2: Broader checks**

Run:
```powershell
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

- [x] **Step 3: Commit, push, deploy, probe**

Commit with `feat: 串联未绑定账号筛选入口`, deploy through `scripts/deploy_systemd_host.sh --pull http://8.140.218.13`, then verify production assets contain `machine_binding` and `applyRouteFilters`.

Result:
- `main@3847564` 已部署到 ECS。
- 线上 `LiveDashboard-CiAkZ4yu.js` / `UserManagement-97qO9yGl.js` 已包含 `machine_binding`，`UserManagement-97qO9yGl.js` 已包含 `bound_machine_id`。
- 生产 Playwright 验证桌面 `1440x900` 与手机 `390x844` 均从“绑定账号”跳到 `/manage/admin/users?machine_binding=unbound&desktop=1`，用户接口实际请求 `/api/v1/users/?machine_binding=unbound&skip=0&limit=10`，返回 `total=198`，无横向溢出。
