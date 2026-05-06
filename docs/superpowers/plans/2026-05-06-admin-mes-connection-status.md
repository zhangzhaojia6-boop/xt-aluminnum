# Admin MES Connection Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让管理端运维页直接显示外部 MES 当前是已同步、未配置、迁移缺失还是供应商异常，避免只能通过 SSH 脚本判断。

**Architecture:** 复用 `mes_sync_service.latest_sync_status()`，在 `/api/v1/mes/sync-status` 增加安全的状态字段，不回显任何密钥。前端 `LiveDashboard.vue` 与现有态势数据并行拉取该接口，并在第一屏显示紧凑的外部 MES 状态条。

**Tech Stack:** FastAPI + Pydantic + pytest；Vue 3 + Element Plus + node:test；不新增依赖。

---

## Tasks

- [x] 扩展 `MesSyncStatusOut`，包含 `configured`、`migration_ready`、`source`、`action_required`、`last_run_status`。
- [x] 更新 `/api/v1/mes/sync-status` 路由测试，证明 manager 可见非敏感状态，错误文本仍只给 admin。
- [x] 增加 `fetchMesSyncStatus()` 前端 API。
- [x] 在 `LiveDashboard.vue` 第一屏增加外部 MES 状态条，显示状态、来源、动作和最近同步。
- [x] 更新前端契约测试，保证运维页暴露 MES 状态且不出现密钥值。
- [x] 运行后端聚焦测试、前端单测、构建和 diff 检查。

## Verification

```powershell
python -m pytest backend/tests/test_factory_command_routes.py::test_mes_sync_status_route backend/tests/test_factory_command_routes.py::test_mes_sync_status_rejects_non_manager -q
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -m frontend_contract -q
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

已验证：

- `python -m pytest backend/tests/test_factory_command_routes.py::test_mes_sync_status_route backend/tests/test_factory_command_routes.py::test_mes_sync_status_rejects_non_manager -q`：2 passed
- `python -m pytest backend/tests -m frontend_contract -q`：124 passed，662 deselected
- `python -m pytest backend/tests -q --durations=10`：662 passed，124 deselected，30 warnings
- `npm --prefix frontend test`：110 passed
- `npm --prefix frontend run build`：通过
- `git diff --check`：通过
