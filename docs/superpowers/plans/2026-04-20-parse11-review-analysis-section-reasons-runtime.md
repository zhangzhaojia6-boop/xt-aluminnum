# Parse 11 Review Analysis Section Reasons Runtime Plan

**Goal:** 为 `analysis_handoff` 增加按 section 归类的 deterministic reason keys，让后续 AI 快速知道每个 section 为什么处于当前状态。

## Task 1: 锁定 section_reasons contract

**Files:**
- Modify: `backend/tests/test_dashboard_routes.py`
- Modify: `backend/tests/test_report_service_contract_lane.py`

- [ ] 为 `analysis_handoff` 增加 `section_reasons`
- [ ] 锁定 factory / workshop route payload 的 typed 访问
- [ ] 锁定 build_factory_dashboard 的真实 reason keys

## Task 2: 实现 schema 与服务规则

**Files:**
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/report_service.py`

- [ ] 为 `AnalysisHandoffOut` 增加 typed `section_reasons`
- [ ] 从既有 section status 与 attention / blocking / gap keys 派生 reasons
- [ ] 不新增数据库查询

## Task 3: 验证与交接

**Files:**
- Modify: `.omx/notepad.md`

- [ ] 跑 focused tests
- [ ] 若容器可用，补后端全量
- [ ] 记录 parse10 收口与 parse11 起步基线
