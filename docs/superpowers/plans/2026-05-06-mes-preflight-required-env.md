# MES Preflight Required Env Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让管理端外部 MES 状态不只显示 `未配置`，还明确展示当前缺少的运行配置字段，便于现场把正式凭据补齐后稳定联通。

**Architecture:** 复用现有 `mes_sync_service.latest_sync_status()` 和 `/api/v1/mes/sync-status`，只增加安全的 `required_env` 字段，不回显任何密钥值。前端 `LiveDashboard.vue` 在外部 MES 状态条中渲染缺失字段列表，保持当前页面信息架构和设计系统。

**Tech Stack:** FastAPI + Pydantic + pytest；Vue 3 + scoped CSS + Node test；不新增依赖。

---

## Tasks

- [x] 后端 TDD：增加 `/api/v1/mes/sync-status` 在未配置时返回 `required_env` 的路由测试。
- [x] 后端实现：在同步状态 payload、schema、router 中透出安全字段 `required_env`。
- [x] 前端 TDD：增加管理端实时态势测试，覆盖 `required_env` / 缺少配置展示。
- [x] 前端实现：在外部 MES 状态条展示缺失配置字段。
- [ ] 验证并提交部署：跑聚焦测试、前端测试、构建、diff check，提交、推送、部署并验证线上产物。

## Verification

```powershell
python -m pytest backend/tests/test_factory_command_routes.py::test_mes_sync_status_route -q
npm --prefix frontend test -- managementCommandCenter.test.js
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```
