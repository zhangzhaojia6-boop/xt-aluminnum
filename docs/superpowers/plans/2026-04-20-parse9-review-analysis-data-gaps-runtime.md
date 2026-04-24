# Parse 9 Review Analysis Data Gaps Runtime Plan

**Goal:** 让 `analysis_handoff` 明确告诉后续 AI 当前缺什么，而不是让消费端自己从状态字段里反推。

## Task 1: 锁定 data_gaps contract

**Files:**
- Modify: `backend/tests/test_dashboard_routes.py`
- Modify: `backend/tests/test_report_service_contract_lane.py`

- [ ] 为 `analysis_handoff` 增加 `data_gaps`
- [ ] 锁定完整 / 部分缺失 / 明显缺失 三类场景

## Task 2: 实现 schema 与服务规则

**Files:**
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/report_service.py`

- [ ] 为 `AnalysisHandoffOut` 增加 `data_gaps`
- [ ] 从 freshness / contracts / energy 等现有 section 派生 gap keys
- [ ] 不新增数据库查询

## Task 3: 验证与交接

**Files:**
- Modify: `.omx/notepad.md`

- [ ] 跑 focused tests
- [ ] 若容器可用，补后端全量
- [ ] 记录 parse8 收口与 parse9 起步基线
