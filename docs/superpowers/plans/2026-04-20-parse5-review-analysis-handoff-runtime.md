# Parse 5 Review Analysis Handoff Runtime Plan

**Goal:** 为审阅端补齐稳定的 `analysis_handoff` contract，先从 factory/workshop dashboard 的 deterministic AI 输入包开始，不接真实模型。

## Task 1: 锁定 handoff contract

**Files:**
- Modify: `backend/tests/test_dashboard_routes.py`

- [ ] 为 factory dashboard 增加 `analysis_handoff` 期望
- [ ] 为 workshop dashboard 增加 `analysis_handoff` 期望
- [ ] 锁定 `readiness / blocking_reasons / reporting / delivery / energy / contracts / risk`

## Task 2: 实现 schema 与服务构建

**Files:**
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/report_service.py`

- [ ] 新增 typed `AnalysisHandoffOut`
- [ ] 新增 factory/workshop handoff 构建 helper
- [ ] 确保 handoff 只消费已 typed 的 summary contract

## Task 3: 验证与交接

**Files:**
- Modify: `.omx/notepad.md`

- [ ] Run focused route tests
- [ ] 若 Docker 环境可用，优先回到容器侧验证后端全量
- [ ] 记录 parse4 收口与 parse5 起步基线
