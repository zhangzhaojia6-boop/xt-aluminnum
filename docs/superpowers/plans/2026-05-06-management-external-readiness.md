# Management External Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把正式外部联通闸门从运维脚本下沉到管理端实时态势页，让管理者直接看到 MES、Workflow、LLM、钉钉、应用连接是否阻塞上线。

**Architecture:** 后端新增鉴权的 dashboard readiness API，复用 `check_statistics_module_ready.inspect_statistics_module_ready()` 的现有判断，不回显密钥值。前端 `LiveDashboard.vue` 并行加载该 API，用紧凑闸门卡显示硬阻塞数量和前几个问题编码。

**Tech Stack:** FastAPI + pytest；Vue 3 + scoped CSS + Node test；不新增依赖。

---

## Tasks

- [x] 后端 TDD：新增 dashboard 外部联通闸门路由测试，验证 manager 可读取 hard issues、mobile 被拒绝。
- [x] 后端实现：在 `backend/app/routers/dashboard.py` 增加 `/dashboard/external-readiness`。
- [x] 前端 TDD：管理端实时态势测试覆盖 `fetchExternalReadiness`、上线闸门、硬阻塞字段。
- [x] 前端实现：`frontend/src/api/dashboard.js` 新增 API，`LiveDashboard.vue` 展示外部联通闸门卡。
- [ ] 验证、提交、部署并核对线上 readyz 与前端产物。

## Verification

```powershell
python -m pytest backend/tests/test_dashboard_routes.py::test_external_readiness_dashboard_route_exposes_hard_issues -q
npm --prefix frontend test -- managementCommandCenter.test.js
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```
