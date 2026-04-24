# Parse 10 Review Analysis Section Matrix Runtime Plan

**Goal:** 为 `analysis_handoff` 增加一个稳定的 section 状态索引，让后续 AI 不需要自己扫描每个 section 才知道哪里健康、哪里告警、哪里阻塞。

## Task 1: 锁定 section_matrix contract

**Files:**
- Modify: `backend/tests/test_dashboard_routes.py`
- Modify: `backend/tests/test_report_service_contract_lane.py`

- [ ] 为 `analysis_handoff` 增加 `section_matrix`
- [ ] 锁定 factory / workshop route payload 的 typed 访问
- [ ] 锁定 build_factory_dashboard 的真实派生结果

## Task 2: 实现 schema 与服务规则

**Files:**
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/report_service.py`

- [ ] 为 `AnalysisHandoffOut` 增加 typed `section_matrix`
- [ ] 从 `reporting / delivery / energy / contracts / risk` 的既有 status 派生 matrix
- [ ] 不新增数据库查询

## Task 3: 验证与交接

**Files:**
- Modify: `.omx/notepad.md`

- [ ] 跑 focused tests
- [ ] 若容器可用，补后端全量
- [ ] 记录 parse8 / parse9 收口与 parse10 起步基线
