# Parse 7 Review Analysis Trends Runtime Plan

**Goal:** 让 `analysis_handoff` 直接带出轻量趋势上下文，先补昨天对比和 7 日均值。

## Task 1: 锁定 trend contract

**Files:**
- Modify: `backend/tests/test_dashboard_routes.py`
- Modify: `backend/tests/test_report_service_contract_lane.py`

- [ ] 为 factory/workshop `analysis_handoff` 增加 `trend`
- [ ] 锁定 `current_output / yesterday_output / output_delta_vs_yesterday / seven_day_average_output`

## Task 2: 实现 schema 与服务规则

**Files:**
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/report_service.py`

- [ ] 为 `AnalysisHandoffOut` 增加 typed `trend`
- [ ] handoff helper 从 `history_digest` 提取 deterministic 趋势上下文
- [ ] 不新增数据库查询

## Task 3: 验证与交接

**Files:**
- Modify: `.omx/notepad.md`

- [ ] 跑 focused tests
- [ ] 若容器可用，补后端全量
- [ ] 记录 parse6 收口与 parse7 起步基线
