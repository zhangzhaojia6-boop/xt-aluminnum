# Machine-Line User Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让管理员在用户管理页按机列绑定状态和具体机列快速定位账号，补齐机列级用户配置的现场排查效率。

**Architecture:** 继续以 `equipment.bound_user_id` 作为机列账号绑定真源。后端 `GET /api/v1/users/` 增加服务端筛选参数，保证分页和总数准确；前端 `UserManagement.vue` 只增加筛选控件并透传查询条件。

**Tech Stack:** FastAPI + SQLAlchemy + pytest；Vue 3 + Element Plus + node:test；不新增依赖。

---

## Task 1: Backend Machine Binding Filters

**Files:**
- Modify: `backend/app/routers/users.py`
- Test: `backend/tests/test_users_routes.py`

- [x] **Step 1: Write failing route tests**

Add assertions for:
- `machine_binding=bound` only returns accounts with an `Equipment.bound_user_id`.
- `machine_binding=unbound` only returns accounts without an equipment binding.
- `bound_machine_id=<id>` returns the account bound to that exact machine.

Run: `python -m pytest backend/tests/test_users_routes.py -q`
Expected: tests fail because the endpoint ignores the new query params.

- [x] **Step 2: Implement the endpoint filters**

Add optional query params to `list_users`:
- `machine_binding: str | None`
- `bound_machine_id: int | None`

Apply filters before `count()` using `Equipment.bound_user_id` subqueries. Keep existing response shape unchanged.

- [x] **Step 3: Verify backend**

Run: `python -m pytest backend/tests/test_users_routes.py -q`
Expected: all tests pass.

## Task 2: Frontend User Management Filters

**Files:**
- Modify: `frontend/src/views/master/UserManagement.vue`
- Test: `frontend/tests/userDingtalkSync.test.js`

- [x] **Step 1: Write failing frontend contract test**

Assert the user management source contains:
- `绑定状态`
- `machineBinding`
- `boundMachineId`
- `machine_binding`
- `handleMachineBindingFilterChange`

Run: `npm --prefix frontend test -- userDingtalkSync.test.js`
Expected: tests fail until the controls exist.

- [x] **Step 2: Add production UI filters**

Add compact Element Plus selects in the existing filter bar:
- 绑定状态: 全部 / 已绑定 / 未绑定
- 绑定机列: from loaded equipment, filterable and disabled when binding status is 未绑定

When workshop filter changes, clear an incompatible selected machine. When binding status changes to 未绑定, clear the machine filter.

- [x] **Step 3: Pass filters to API**

Extend the `fetchUsersPage` call with:
- `machine_binding: filters.machineBinding || undefined`
- `bound_machine_id: filters.boundMachineId || undefined`

## Task 3: Validation And Delivery

**Files:**
- Verify: backend and frontend tests
- Update docs only if build asset names or validation evidence change during deployment

- [x] **Step 1: Focused tests**

Run:
```powershell
python -m pytest backend/tests/test_users_routes.py -q
npm --prefix frontend test -- userDingtalkSync.test.js
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

If verification passes, commit with `feat: 支持机列用户配置筛选`, push `main`, deploy to the server, then probe `/readyz` and `/api/v1/users/` with the new filters.
