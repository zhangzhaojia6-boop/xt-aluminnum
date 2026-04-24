# Parse 8 Review Analysis Freshness Runtime Plan

**Goal:** 为 `analysis_handoff` 补齐 deterministic 的 freshness / confidence 上下文，帮助后续 AI 判断数据是否足够新、足够稳。

## Task 1: 锁定 freshness contract

**Files:**
- Modify: `backend/tests/test_dashboard_routes.py`
- Modify: `backend/tests/test_report_service_contract_lane.py`

- [ ] 为 `analysis_handoff` 增加 `freshness`
- [ ] 锁定 `freshness_status / sync_status / sync_lag_seconds / history_points / published_report_at`

## Task 2: 实现 schema 与服务规则

**Files:**
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/report_service.py`

- [ ] 为 `AnalysisHandoffOut` 增加 typed `freshness`
- [ ] 从现有 `sync_status / history_digest / latest_report_published_at` 构建 freshness
- [ ] 不新增数据库查询

## Task 3: 验证与交接

**Files:**
- Modify: `.omx/notepad.md`

- [ ] 跑 focused tests
- [ ] 若容器可用，补后端全量
- [ ] 记录 parse7 收口与 parse8 起步基线
