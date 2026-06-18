# MES 日报与看板口径对齐实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `xtmijd.com/manage/today` 和文字日报优先按外部 MES SQL Server 真实口径取数，修复 `园区精整` 归属、入库口径、月累计缺数三类硬问题。

**Architecture:** 保持现有链路不变：外部 SQL Server -> 本地 `mes_*` 投影表 -> 后端 API -> 前端展示。禁止前端或页面请求时直连外部 SQL。先修映射和入库口径，再补全按日期窗口同步，最后用 2026-06-17 对账验收。

**Tech Stack:** Python, FastAPI, SQLAlchemy, APScheduler, SQL Server read-only adapter, pytest.

## Global Constraints

- 不提交、不打印、不写入任何数据库密码、webhook、token 或连接串。
- 产品名使用 `鑫泰铝业 数据中枢`；MES 只作为外部数据源名称。
- 前端不直连外部 SQL Server，页面只读取后端 API。
- 保持 `/api/v1/dashboard/daily-production` 现有字段兼容，只允许增加可选来源字段。

---

### Task 1: 统一 MES 车间映射

**Files:**
- Create: `backend/app/services/report/mes_workshop_mapping.py`
- Modify: `backend/app/core/active_workshops.py`
- Modify: `backend/app/services/report/daily_overview_builder.py`
- Modify: `backend/app/services/report/template_daily_fact_sources.py`
- Test: `backend/tests/test_daily_overview_chain.py`
- Test: `backend/tests/test_template_daily_fact_sources.py`

**Interfaces:**
- Produces: `resolve_mes_process_workshop_bucket(workshop_name: Any, process_name: Any = None, device_name: Any = None) -> str | None`

- [x] 修正 `园区精整` 到 `园区剪切`。
- [x] 看板和日报都使用共享映射。
- [x] 测试 `园区精整/包装` 只进入 `园区剪切`，不进入 `精整`。

### Task 2: 修正入库与发货口径

**Files:**
- Modify: `backend/app/adapters/mes_adapter.py`
- Modify: `backend/app/adapters/sqlserver_mes_adapter.py`
- Modify: `backend/app/services/mes_sync_service.py`
- Modify: `backend/app/services/report/daily_overview_builder.py`
- Modify: `backend/app/services/report/template_daily_fact_sources.py`
- Test: `backend/tests/test_sqlserver_mes_adapter.py`
- Test: `backend/tests/test_mes_sync_service.py`
- Test: `backend/tests/test_daily_overview_mes_packaging.py`

**Interfaces:**
- Produces: `list_finished_inbound_records_between(start_at: datetime, end_at: datetime, limit: int = 1000, offset: int = 0) -> list[MesSourceRecord]`
- Produces: `list_delivery_records_between(start_at: datetime, end_at: datetime, limit: int = 1000, offset: int = 0) -> list[MesSourceRecord]`

- [x] `stock_records` 日期优先级改为 `InStockDate/StrInStockDate/CreateDate/UrgentOperateDate/AllocationDate/OperateDate`。
- [x] 成品入库优先使用 `WMS_InStock.TotalNetWeight + InStockDate`。
- [x] 发货优先使用 `MES_DeliveryDetail.NetWeight + OperateDate`。

### Task 3: 新增月初至目标日窗口回填

**Files:**
- Modify: `backend/app/adapters/mes_adapter.py`
- Modify: `backend/app/adapters/sqlserver_mes_adapter.py`
- Modify: `backend/app/services/mes_sync_service.py`
- Modify: `backend/app/tasks/mes_sync.py`
- Modify: `backend/app/core/scheduler.py`
- Test: `backend/tests/test_sqlserver_mes_adapter.py`
- Test: `backend/tests/test_mes_sync_service.py`
- Test: `backend/tests/test_scheduler.py`

**Interfaces:**
- Produces: `sync_mes_month_to_date_projection(db: Session, target_date: date | None = None, now: datetime | None = None) -> list[MesSyncStats]`
- Produces: task wrapper `sync_mes_month_to_date_projection(target_date: date | None = None) -> dict[str, object]`

- [x] SQL Server adapter 支持按日期窗口分页读取过程、入库、材料数据。
- [x] 每天 07:25 回填当月到昨日业务日。
- [x] 每天 08:50 再回填一次，修正晚录入。

### Task 4: 验证与生产只读 QA

**Commands:**
- `python -m pytest backend/tests/test_daily_overview_chain.py backend/tests/test_template_daily_fact_sources.py -q`
- `python -m pytest backend/tests/test_daily_overview_mes_packaging.py -q`
- `python -m pytest backend/tests/test_sqlserver_mes_adapter.py backend/tests/test_mes_sync_service.py -q`
- `python -m pytest backend/tests/test_daily_report_task.py backend/tests/test_report_generation.py backend/tests/test_reporter_agent.py -q`

- [x] 生产只读验证 2026-06-17：入库 `303.03`，发货 `222.306`。
- [x] 回填后月累计不再停在本地 `TOP 50` 残缺投影。
