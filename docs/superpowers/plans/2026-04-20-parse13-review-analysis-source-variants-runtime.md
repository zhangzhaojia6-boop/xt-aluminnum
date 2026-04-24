# Parse 13 Review Analysis Source Variants Runtime Plan

**Goal:** 为 `analysis_handoff` 增加 machine-friendly 的来源分类，让后续 AI 更容易按来源类别做规则判断与路由。

## Task 1: 锁定 source_variants contract

**Files:**
- Modify: `backend/tests/test_dashboard_routes.py`
- Modify: `backend/tests/test_report_service_contract_lane.py`

- [ ] 为 `analysis_handoff` 增加 `source_variants`
- [ ] 锁定 factory / workshop route payload 的 typed 访问
- [ ] 锁定 build_factory_dashboard 的真实来源变体集合

## Task 2: 实现 schema 与服务规则

**Files:**
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/report_service.py`

- [ ] 为 `AnalysisHandoffOut` 增加 typed `source_variants`
- [ ] 从既有 section 来源语义派生 machine-friendly 变体
- [ ] 不新增数据库查询

## Task 3: 验证与交接

**Files:**
- Modify: `.omx/notepad.md`

- [ ] 跑 focused tests
- [ ] 若容器可用，补后端全量
- [ ] 记录 parse12 收口与 parse13 起步基线
