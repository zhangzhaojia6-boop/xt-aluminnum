# Live Fill Management Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让管理端明确吃到今天测试中的现场卷级填报数据，同时保留正式汇总只统计已确认数据的边界，并补一组轻量动态图表提升管理端可读性。

**Architecture:** 后端继续把正式领导口径限定在 `auto_confirmed/confirmed`，但工厂指挥和管理端上报状态增加 `mobile_coil_agg` 待确认来源。前端不新增图表库，复用 `history_digest.daily_snapshots` 和现有设计体系，用 SVG 折线/面积和来源标签展示正式汇总与实时流入。

**Tech Stack:** FastAPI + SQLAlchemy + pytest；Vue 3 + Element Plus + scoped CSS；不新增依赖。

---

## Context

- 统一填报页机列主操走 `/mobile/coil-entry`，写入 `work_order_entries` 并聚合到 `shift_production_data.mobile_coil_agg`。
- 管理端厂级正式产量来自已确认口径，不应把 `pending` 直接算入正式日报。
- 本轮只把 `pending + mobile_coil_agg` 作为实时待确认流入展示，普通 `pending` 导入仍不进入工厂指挥汇总。

## Files

- Modify: `backend/app/services/factory_command_service.py`
- Modify: `backend/app/services/report/lane_builders.py`
- Modify: `backend/tests/test_factory_command_service.py`
- Modify: `backend/tests/test_workshop_reporting_status.py`
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue`
- Modify: `frontend/src/utils/reportStatus.js`
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`

## Tasks

- [x] Add tests proving `pending + mobile_coil_agg` is visible to factory command without including normal pending imports.
- [x] Add tests proving the factory dashboard reporting table surfaces same-day live coil aggregates as `卷级直录`.
- [x] Implement the backend live visibility path without changing formal confirmed report scope.
- [x] Add a lightweight SVG trend chart to the factory dashboard with output, storage, and shipment series.
- [x] Verify focused backend, frontend contract, frontend unit, frontend build, full backend tests, and live readyz.

## Verification

```bash
python -m pytest backend/tests/test_factory_command_service.py backend/tests/test_workshop_reporting_status.py -q
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -m frontend_contract -q
npm --prefix frontend test
npm --prefix frontend run build
python -m pytest backend/tests -q
git diff --check
Invoke-RestMethod -Uri http://8.140.218.13/readyz -TimeoutSec 10
```

`mes_sync=unconfigured` remains an external-configuration blocker until real external MES credentials and network access are supplied.
