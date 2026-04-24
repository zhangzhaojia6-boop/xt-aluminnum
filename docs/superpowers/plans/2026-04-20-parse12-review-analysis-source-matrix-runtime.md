# Parse 12 Review Analysis Source Matrix Runtime Plan

**Goal:** 为 `analysis_handoff` 增加顶层来源索引，让后续 AI 可以不下钻 section 内容就先知道各块数据主要来自谁。

## Task 1: 锁定 source_matrix contract

**Files:**
- Modify: `backend/tests/test_dashboard_routes.py`
- Modify: `backend/tests/test_report_service_contract_lane.py`

- [ ] 为 `analysis_handoff` 增加 `source_matrix`
- [ ] 锁定 factory / workshop route payload 的 typed 访问
- [ ] 锁定 build_factory_dashboard 的真实来源集合

## Task 2: 实现 schema 与服务规则

**Files:**
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/report_service.py`

- [ ] 为 `AnalysisHandoffOut` 增加 typed `source_matrix`
- [ ] 从既有 section `source_labels` 派生 matrix
- [ ] 不新增数据库查询

## Task 3: 验证与交接

**Files:**
- Modify: `.omx/notepad.md`

- [ ] 跑 focused tests
- [ ] 若容器可用，补后端全量
- [ ] 记录 parse11 收口与 parse12 起步基线
