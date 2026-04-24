# Parse 14 Review Analysis Action Matrix Runtime Plan

**Goal:** 为 `analysis_handoff` 增加稳定的下一步动作键，让后续 AI 更容易按 section 进入正确的检查路径。

## Task 1: 锁定 action_matrix contract

**Files:**
- Modify: `backend/tests/test_dashboard_routes.py`
- Modify: `backend/tests/test_report_service_contract_lane.py`

- [ ] 为 `analysis_handoff` 增加 `action_matrix`
- [ ] 锁定 factory / workshop route payload 的 typed 访问
- [ ] 锁定 build_factory_dashboard 的真实动作键

## Task 2: 实现 schema 与服务规则

**Files:**
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/report_service.py`

- [ ] 为 `AnalysisHandoffOut` 增加 typed `action_matrix`
- [ ] 从既有 section status / reasons / gaps 派生 deterministic 动作键
- [ ] 不新增数据库查询

## Task 3: 验证与交接

**Files:**
- Modify: `.omx/notepad.md`

- [ ] 跑 focused tests
- [ ] 若容器可用，补后端全量
- [ ] 记录 parse13 收口与 parse14 起步基线
