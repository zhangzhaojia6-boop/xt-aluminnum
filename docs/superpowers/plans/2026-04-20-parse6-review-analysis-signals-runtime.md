# Parse 6 Review Analysis Signals Runtime Plan

**Goal:** 让 `analysis_handoff` 从“可读输入包”升级成“可直接消费的信号包”，先补 deterministic 的 `priority` 与 `attention_flags`。

## Task 1: 锁定信号层 contract

**Files:**
- Modify: `backend/tests/test_dashboard_routes.py`
- Modify: `backend/tests/test_report_service_contract_lane.py`

- [ ] 为 factory/workshop `analysis_handoff` 增加 `priority`
- [ ] 为 factory/workshop `analysis_handoff` 增加 `attention_flags`
- [ ] 锁定 blocking / warning / healthy 三种典型信号

## Task 2: 实现 schema 与服务规则

**Files:**
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/report_service.py`

- [ ] 为 `AnalysisHandoffOut` 增加 `priority / attention_flags`
- [ ] 在 handoff helper 中集中生成 deterministic 信号
- [ ] 确保只消费已有 typed summary contract

## Task 3: 验证与交接

**Files:**
- Modify: `.omx/notepad.md`

- [ ] 跑 focused tests
- [ ] 若容器可用，补后端全量
- [ ] 记录 parse5 收口与 parse6 起步基线
