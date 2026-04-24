# Parse 4 Review Summary Contracts Runtime Plan

**Goal:** 把审阅端剩余的关键摘要 contract 收紧，先从 `delivery-status` 与 `factory_dashboard.delivery_status` 开始，再逐步推进 `energy_summary / management_estimate / contract_lane` 等高频摘要块。

## Task 1: 交付摘要 contract

**Files:**
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/routers/dashboard.py`
- Modify: `backend/tests/test_delivery_status.py`
- Modify: `backend/tests/test_dashboard_routes.py`

- [ ] 为 `delivery-status` 增加 typed response model
- [ ] 把 `FactoryDashboardResponse.delivery_status` 收成 typed 字段
- [ ] 用 route tests 锁定 `delivery_ready / reports_generated / reports_reviewed_count / missing_steps`

## Task 2: 审阅摘要块继续 typed 化

**Files:**
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/tests/test_dashboard_routes.py`

- [ ] 逐步补 `energy_summary`
- [ ] 逐步补 `management_estimate`
- [ ] 逐步补 `contract_lane / contract_progress`

## Task 3: 验证与交接

**Files:**
- Modify: `.omx/notepad.md`

- [ ] Run `docker compose run --rm backend sh -lc "pytest tests/test_delivery_status.py tests/test_dashboard_routes.py -q"`
- [ ] Run `docker compose run --rm backend sh -lc "pytest -q"`
- [ ] Run `docker compose up -d --build backend nginx`
- [ ] Verify `curl -k https://localhost/readyz`
- [ ] 记录 parse4 起步与最新基线
