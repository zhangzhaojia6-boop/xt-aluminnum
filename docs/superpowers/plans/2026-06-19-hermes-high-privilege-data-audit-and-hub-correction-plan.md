# Hermes High Privilege Data Audit And Hub Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Hermes 先拿到准确的原始数据，再用可审计、可回滚的方式修正 `鑫泰铝业 数据中枢`。第一阶段不做统一事实包，先完成 MES 只读、数据中枢可写、`D:\输出skill` 只读三边核验，并把 2026-06-16、2026-06-17、2026-06-18 三天关键字段对齐率提升到 85% 以上。

**Architecture:** 新增一个 Hermes 数据审计通道：Hermes 从 MES 只读取原始数据，从数据中枢读取当前数据，从 `D:\输出skill` 读取历史成品，然后生成差异、修正建议、数据中枢修正动作和重跑结果。MES 永远只读；数据中枢允许 Hermes 写，但所有写操作必须记录改前、改后、证据、原因和回滚信息。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, existing `SqlServerMesAdapter`, existing mapping reconciliation service, existing output-skill parsing utilities, SQLite test database, SQL Server production read adapter.

---

## 0. 先说清楚范围

这份 plan 只做第一阶段。

要做：

- Hermes 可以发起三边数据核验。
- Hermes 可以只读查询 MES 关键数据。
- Hermes 可以读取数据中枢当前数据。
- Hermes 可以读取 `D:\输出skill` 的历史成品。
- Hermes 可以写入数据中枢的修正记录、映射规则、别名规则、对齐结果。
- Hermes 的每次数据中枢写操作都有审计记录。
- 先用 2026-06-16、2026-06-17、2026-06-18 三天做历史回放。

不做：

- 不让 Hermes 写 MES。
- 不把数据库账号密码写入代码、日志、审计表或 plan。
- 不修改 `D:\输出skill` 原始文件。
- 不重写整个数据中枢。
- 不做前端大改版。
- 不把每日动态数字塞进 RAG 当事实。
- 不绕过 `agent_outbox` 做真实外发。

小白版理解：这次不是做一个漂亮页面，而是先给 Hermes 一套“查账、对账、修自己系统账”的后台能力。

## 0A. CEO Review 优化结论

本轮按 `plan-ceo-review` 视角复核后，结论是：原 plan 方向对，但还不够“能上线”。主要缺口不是功能不够，而是缺少失败路径、上线门禁、可观测性和回滚动作。

优化后的执行模式：

```text
HOLD SCOPE 为主
SELECTIVE EXPANSION 只补必要平台能力
```

意思是：不扩大成新平台，不做前端工作台，不提前做统一事实包；但把审计、错误、告警、回滚、幂等这些上线必需项补进第一阶段。

### 三种实施方案比较

| 方案 | 内容 | 工作量 | 风险 | 完整度 | 结论 |
|---|---|---:|---|---:|---|
| A. 最小方案 | 只加一个 API，调用现有对齐服务和 MES 查询 | S | 容易上线，但失败不可见、修正不可控 | 5/10 | 不选 |
| B. 当前优化方案 | 新增 Hermes 审计 run/action，复用现有 MES adapter 和对齐服务，补错误、监控、回滚 | M | 可控，能支撑历史三天验收 | 8.5/10 | 采用 |
| C. 理想平台方案 | 建完整数据质量平台、血缘图、审批流、前端工作台、全量规则中心 | XL | 价值高，但会拖慢当前救火目标 | 10/10 | 后续阶段 |

推荐采用 B。

原因很简单：当前问题是 Hermes 拿到的数据不准，现场需要先把数据链路查准。B 足够解决第一阶段目标，又不会把系统改成一个大工程。

### 12 个月理想态

```text
当前状态
  数据中枢已有 MES 投影、人工填报、日报、对齐服务，但口径分散
      ↓
本计划
  Hermes 有一条受控高权限审计通道，能查三边、解释差异、修正数据中枢低风险规则
      ↓
12 个月理想态
  数据中枢每天自动给出可信数据状态：哪些字段可信、哪些字段缺口、谁负责补、修正前后影响多少
```

小白版理解：最终不是让 Hermes “更会猜”，而是让系统每天自动告诉我们“这份日报哪些数是有证据的，哪些数还不可信”。

### 本次必须补进 plan 的 P1 风险

| 风险 | 为什么严重 | 本 plan 的修法 |
|---|---|---|
| 查 MES 失败但 run 仍显示完成 | Hermes 会拿缺数据做错误判断 | 每个来源有独立状态，任何来源失败必须进入 `source_errors` |
| 数据中枢修正重复执行 | 别名、规则、重算可能重复写入 | correction action 增加 `idempotency_key` 和唯一约束 |
| action 写了一半失败 | 审计表说成功，但真实规则没改完 | 每个 action 单事务执行，失败写 `failed` 和错误分类 |
| 原始 payload 过大或含敏感字段 | 审计表爆表，或泄露客户、人员、密钥 | 只存摘要、hash、来源引用和脱敏样本 |
| 85% 匹配率被误读成事实准确 | 指标变成自我安慰 | 必须同时输出剩余未匹配字段和原因分类 |
| 云端参考目录缺失 | output skill 对齐直接失效 | 参考目录缺失返回可解释 `output_skill_source_missing`，不能 500 |

## 1. 当前代码结构映射

实施前先确认这些现有入口，不要重复造轮子。

### 已存在并要复用

- `backend/app/adapters/sqlserver_mes_adapter.py`
  - 已有 `SqlServerMesAdapter`。
  - 已有生产记录、库存、投料、入库、成品率等 MES 只读查询方法。
  - 这次只在外面包一层 Hermes 专用读服务，不改成写服务。

- `backend/app/routers/hermes.py`
  - 目前主要是 Hermes 相关入口。
  - 这次不把所有新接口塞进去，新增独立 router，避免文件变大。

- `backend/app/services/hermes_governance_service.py`
  - 已有 Hermes 治理类服务。
  - 这次可以复用里面的安全思路，但不要把数据审计逻辑混进去。

- `backend/app/services/mapping_reconciliation_service.py`
  - 已有输出 skill 对齐解析和 dry-run 能力。
  - 这次要把它接入 Hermes 三边核验，不重写解析器。

- `backend/app/routers/mapping_reconciliation.py`
  - 已有对齐接口。
  - Hermes 可调用服务层，不应该绕 API 再调自己。

- `backend/app/models/reconciliation.py`
  - 已有 `DataReconciliationItem`、`MappingReconciliationRun`。
  - 这次新增 Hermes 自己的审计表，不把高权限审计塞进原表。

- `backend/app/main.py`
  - 注册 FastAPI router 的地方。

- `backend/tests/test_mapping_reconciliation_route.py`
  - 可参考 TestClient、SQLite 临时表、权限 override 的测试写法。

- `backend/tests/test_hermes_governance_service.py`
  - 可参考 Hermes 服务测试风格。

### 新增文件

- `backend/app/models/hermes_data_audit.py`
  - 新增 Hermes 数据审计 run 表和 correction action 表。

- `backend/alembic/versions/0049_hermes_data_audit.py`
  - 新增数据库迁移。

- `backend/app/schemas/hermes_data_audit.py`
  - 新增 API 入参、出参 schema。

- `backend/app/services/hermes_mes_read_service.py`
  - Hermes 专用 MES 只读服务。

- `backend/app/services/hermes_data_audit_service.py`
  - 三边核验、输出 skill 只读读取、差异分类、修正建议、修正动作执行。
  - 不单独新增 `backend/app/services/hermes_output_skill_service.py`；先复用现有 `parse_output_skill_reference_file()`，把输出 skill 读取做成私有 helper。

- `backend/app/routers/hermes_data_audit.py`
  - 新增 API：创建核验 run、查看 run、应用修正、重跑核验。

- `backend/tests/test_hermes_mes_read_service.py`
  - MES 只读服务测试。

- `backend/tests/test_hermes_data_audit_service.py`
  - 三边核验、输出 skill 读取 helper 和修正动作测试。

- `backend/tests/test_hermes_data_audit_router.py`
  - API 路由测试。

### 只做小改的文件

- `backend/app/models/__init__.py`
  - 导入新模型，保证 Alembic 和测试能看到。

- `backend/app/main.py`
  - 注册 `hermes_data_audit` router。

## 2. 数据模型设计

### 核验 run 表

表名：`hermes_data_audit_runs`

用途：记录 Hermes 某一天、某一批字段的三边核验结果。

建议字段：

```python
class HermesDataAuditRun(Base):
    __tablename__ = "hermes_data_audit_runs"

    id = Column(Integer, primary_key=True)
    run_key = Column(String(128), nullable=False, unique=True, index=True)
    business_date = Column(Date, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending", index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    source_status = Column(JSON, nullable=False, default=dict)
    source_errors = Column(JSON, nullable=False, default=dict)
    request_payload = Column(JSON, nullable=False, default=dict)
    mes_payload = Column(JSON, nullable=False, default=dict)
    hub_payload = Column(JSON, nullable=False, default=dict)
    output_skill_payload = Column(JSON, nullable=False, default=dict)
    diff_payload = Column(JSON, nullable=False, default=dict)
    correction_summary = Column(JSON, nullable=False, default=dict)
    match_rate = Column(Numeric(8, 4), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
```

补充要求：

- `run_key` 用 `business_date + fields hash + reference files hash + dry_run` 生成，避免同一个 dry-run 被重复创建成多条相同记录。
- `source_status` 分别记录 `mes`、`hub`、`output_skill` 三个来源的状态，例如 `ok`、`empty`、`missing`、`failed`。
- `source_errors` 只存错误类型和脱敏后的错误摘要，不存连接串、账号、密码。
- `mes_payload`、`hub_payload`、`output_skill_payload` 不存全量原始大表，只存字段级摘要、行数、hash、来源引用。
- `match_rate` 是展示指标，不是事实证明；完成标准仍以差异分类和字段证据为准。

### 修正 action 表

表名：`hermes_data_correction_actions`

用途：记录 Hermes 对数据中枢做过什么改动。

建议字段：

```python
class HermesDataCorrectionAction(Base):
    __tablename__ = "hermes_data_correction_actions"

    id = Column(Integer, primary_key=True)
    audit_run_id = Column(Integer, ForeignKey("hermes_data_audit_runs.id"), nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    action_type = Column(String(64), nullable=False, index=True)
    risk_level = Column(String(16), nullable=False, default="low", index=True)
    target_table = Column(String(128), nullable=False)
    target_key = Column(String(256), nullable=False)
    before_payload = Column(JSON, nullable=False, default=dict)
    after_payload = Column(JSON, nullable=False, default=dict)
    evidence_payload = Column(JSON, nullable=False, default=dict)
    rollback_payload = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="pending", index=True)
    rollback_status = Column(String(32), nullable=False, default="not_requested", index=True)
    error_message = Column(Text, nullable=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    applied_at = Column(DateTime(timezone=True), nullable=True)
```

补充要求：

- `idempotency_key` 用 `action_type + target_table + target_key + after_payload hash` 生成。重复请求不能重复改数据。
- `risk_level=low` 才允许第一阶段自动执行。`medium/high` 只能生成建议，不能自动 apply。
- `before_payload` 必须在同一事务里读取并写入，不能先写 action 再另查。
- `rollback_payload` 必须说明是“自动回滚”“人工回滚”还是“不可回滚”。
- 不允许把 MES 原始行、输出 skill 原始全文、数据库连接信息写进 action。

### 状态约定

`HermesDataAuditRun.status`：

- `pending`：刚创建。
- `running`：正在查三边数据。
- `completed`：核验完成。
- `failed`：核验失败。
- `correcting`：正在修数据中枢。
- `corrected`：已完成至少一项修正。

`HermesDataCorrectionAction.status`：

- `pending`：已生成建议，未执行。
- `applied`：已执行。
- `failed`：执行失败。
- `rolled_back`：已回滚。

小白版理解：run 是一次查账，action 是一次改账。每次改账都要知道“改了什么、为什么改、能不能撤回”。

## 3. API 设计

新增 router 前缀：

```text
/api/v1/hermes/data-audit
```

### 创建核验 run

```text
POST /api/v1/hermes/data-audit/runs
```

请求：

```json
{
  "business_date": "2026-06-18",
  "fields": [
    "total_output",
    "workshop_output",
    "wip_total",
    "inbound_total",
    "total_electricity_kwh",
    "total_gas_m3",
    "yield_rate",
    "contract_amount",
    "ton_cost"
  ],
  "reference_files": [],
  "dry_run": true
}
```

返回：

```json
{
  "id": 1,
  "business_date": "2026-06-18",
  "status": "completed",
  "match_rate": 0.86,
  "diff_count": 3,
  "correction_action_count": 2
}
```

### 查看核验 run

```text
GET /api/v1/hermes/data-audit/runs/{run_id}
```

返回应包含：

- MES 原始值摘要。
- 数据中枢当前值摘要。
- 输出 skill 成品值摘要。
- 差异分类。
- 推荐修正动作。
- 已执行修正动作。

### 应用修正

```text
POST /api/v1/hermes/data-audit/runs/{run_id}/corrections
```

请求：

```json
{
  "action_ids": [10, 11],
  "dry_run": false
}
```

第一阶段只允许低风险数据中枢修正：

- 字段映射 upsert。
- 车间、设备、工序、班次别名 upsert。
- 保存对齐 dry-run 结果。
- 触发数据中枢自己的重算任务。

不在第一阶段自动做：

- 删除业务数据。
- 批量覆盖日报正文。
- 绕过 outbox 直接外发。

### 重跑核验

```text
POST /api/v1/hermes/data-audit/runs/{run_id}/rerun
```

用途：修完数据中枢后再跑一次，看对齐率是否真的提升。

## 4. 任务清单

### Task 0: 实施前锁定边界和复用点

**目标：** 开工前先防止做成第二套对齐系统。

**必须确认：**

- [ ] 输出 skill 读取逻辑只作为 `HermesDataAuditService` 私有 helper，包装 `parse_output_skill_reference_file()`，不重写 Excel/TXT/JSON 解析主逻辑。
- [ ] `HermesMesReadService` 只包装 `SqlServerMesAdapter`，不暴露任意 SQL。
- [ ] `HermesDataAuditService` 只编排三边核验，不直接塞进 `mapping_reconciliation_service.py`。
- [ ] 所有真实修正默认受 `HERMES_DATA_AUDIT_APPLY_ENABLED=false` 控制。
- [ ] 云端第一轮只能 dry-run，不能自动 apply。
- [ ] 敏感信息脱敏复用现有 `redact_secret_text()` 或同等级工具。

**测试先行：**

- [ ] 在 service 测试中验证 `HERMES_DATA_AUDIT_APPLY_ENABLED=false` 时，非 dry-run apply 返回明确拒绝。
- [ ] 验证错误文本里出现 `password=`、`token=`、`secret=` 时会被脱敏。
- [ ] 验证参考目录不存在时返回 `output_skill_source_missing`，不是 500。

测试示例：

```python
def test_apply_is_blocked_when_feature_flag_disabled(db_session, monkeypatch):
    monkeypatch.setenv("HERMES_DATA_AUDIT_APPLY_ENABLED", "false")
    service = build_service(db_session)
    run = make_run_with_pending_action(db_session, action_type="mapping_alias_upsert")

    result = service.apply_corrections(
        run_id=run.id,
        action_ids=[run.actions[0].id],
        dry_run=False,
        actor_user_id=1,
    )

    assert result["applied"] is False
    assert result["reason"] == "apply_disabled"
```

**验证命令：**

```powershell
python -m pytest backend/tests/test_hermes_data_audit_service.py -q
```

**提交：**

```powershell
git add backend/tests/test_hermes_data_audit_service.py
git commit -m "Lock Hermes data audit safety boundaries"
```

### Task 1: 新增审计模型和迁移

**目标：** 数据库能保存 Hermes 核验 run 和修正 action。

**测试先行：**

- [ ] 新建 `backend/tests/test_hermes_data_audit_service.py`。
- [ ] 写一个最小测试：能创建 `HermesDataAuditRun` 和 `HermesDataCorrectionAction`。

测试示例：

```python
from datetime import date

from app.models.hermes_data_audit import HermesDataAuditRun, HermesDataCorrectionAction


def test_can_persist_hermes_data_audit_run(db_session):
    run = HermesDataAuditRun(
        business_date=date(2026, 6, 18),
        status="completed",
        request_payload={"fields": ["total_output"]},
        mes_payload={"total_output": 100},
        hub_payload={"total_output": 90},
        output_skill_payload={"total_output": 100},
        diff_payload={"total_output": {"status": "hub_mismatch"}},
    )
    db_session.add(run)
    db_session.commit()

    saved = db_session.query(HermesDataAuditRun).one()
    assert saved.business_date == date(2026, 6, 18)
    assert saved.diff_payload["total_output"]["status"] == "hub_mismatch"


def test_can_persist_hermes_data_correction_action(db_session):
    run = HermesDataAuditRun(
        business_date=date(2026, 6, 18),
        status="completed",
        request_payload={},
        mes_payload={},
        hub_payload={},
        output_skill_payload={},
        diff_payload={},
    )
    db_session.add(run)
    db_session.flush()

    action = HermesDataCorrectionAction(
        audit_run_id=run.id,
        action_type="mapping_alias_upsert",
        target_table="master_code_aliases",
        target_key="workshop:精整车间",
        before_payload={},
        after_payload={"canonical": "精整"},
        evidence_payload={"source": "output_skill"},
        rollback_payload={"delete_inserted_alias": True},
    )
    db_session.add(action)
    db_session.commit()

    saved = db_session.query(HermesDataCorrectionAction).one()
    assert saved.status == "pending"
```

**实现：**

- [ ] 新建 `backend/app/models/hermes_data_audit.py`。
- [ ] 在 `backend/app/models/__init__.py` 导入新模型。
- [ ] 新建 `backend/alembic/versions/0049_hermes_data_audit.py`。
- [ ] 迁移里用项目现有 `_has_table` 风格，避免重复建表失败。
- [ ] JSON 字段按项目当前数据库兼容方式写。

**验证命令：**

```powershell
python -m pytest backend/tests/test_hermes_data_audit_service.py -q
python -m compileall backend/app/models/hermes_data_audit.py
```

**预期结果：**

```text
2 passed
```

**提交：**

```powershell
git add backend/app/models/hermes_data_audit.py backend/app/models/__init__.py backend/alembic/versions/0049_hermes_data_audit.py backend/tests/test_hermes_data_audit_service.py
git commit -m "Add Hermes data audit persistence"
```

### Task 2: 新增 Hermes MES 只读服务

**目标：** Hermes 能通过受控入口读 MES，但不能执行任意写 SQL。

**设计约束：**

- 只暴露固定查询 key。
- 不接受用户直接传 SQL。
- 默认限制行数。
- 记录查询 key、日期、范围，不记录密码和连接串。

安全查询 key：

```python
SAFE_MES_QUERY_KEYS = {
    "workshop_process_records",
    "stock_records",
    "material_records",
    "yield_records",
    "inbound_records",
    "delivery_records",
    "device_records",
    "craft_records",
    "product_problem_records",
}
```

**测试先行：**

- [ ] 新建 `backend/tests/test_hermes_mes_read_service.py`。
- [ ] 用 fake adapter 验证只调用白名单方法。
- [ ] 验证非法 query key 会报错。

测试示例：

```python
from datetime import date

import pytest

from app.services.hermes_mes_read_service import HermesMesReadService


class FakeMesAdapter:
    def list_workshop_process_records(self, **kwargs):
        return [{"field": "output", "value": 10}]

    def list_stock_records(self, **kwargs):
        return [{"field": "wip", "value": 5}]


def test_reads_only_safe_mes_query_keys():
    service = HermesMesReadService(adapter=FakeMesAdapter())

    result = service.read_sources(
        business_date=date(2026, 6, 18),
        query_keys=["workshop_process_records", "stock_records"],
    )

    assert "workshop_process_records" in result
    assert "stock_records" in result


def test_rejects_unsafe_mes_query_key():
    service = HermesMesReadService(adapter=FakeMesAdapter())

    with pytest.raises(ValueError, match="Unsupported MES query key"):
        service.read_sources(
            business_date=date(2026, 6, 18),
            query_keys=["drop_table"],
        )
```

**实现：**

- [ ] 新建 `backend/app/services/hermes_mes_read_service.py`。
- [ ] 包装 `SqlServerMesAdapter` 的现有方法。
- [ ] 所有方法只返回普通 dict/list，避免把数据库连接对象传出去。
- [ ] 默认 `limit=5000`，后续要全量再单独设计分页。

核心实现示例：

```python
class HermesMesReadService:
    def __init__(self, adapter: SqlServerMesAdapter):
        self.adapter = adapter

    def read_sources(self, *, business_date: date, query_keys: list[str], limit: int = 5000) -> dict[str, list[dict[str, Any]]]:
        results = {}
        for query_key in query_keys:
            if query_key not in SAFE_MES_QUERY_KEYS:
                raise ValueError(f"Unsupported MES query key: {query_key}")
            results[query_key] = self._read_one(query_key, business_date=business_date, limit=limit)
        return results
```

**验证命令：**

```powershell
python -m pytest backend/tests/test_hermes_mes_read_service.py -q
python -m compileall backend/app/services/hermes_mes_read_service.py
```

**预期结果：**

```text
2 passed
```

**提交：**

```powershell
git add backend/app/services/hermes_mes_read_service.py backend/tests/test_hermes_mes_read_service.py
git commit -m "Add read-only MES access for Hermes audit"
```

### Task 3: 接入输出 skill 只读读取 helper

**目标：** Hermes 能读取 `D:\skill` 或 `OUTPUT_SKILL_ROOT` 指向的历史成品，但不能修改它。

**测试先行：**

- [ ] 在 `backend/tests/test_hermes_data_audit_service.py` 增加输出 skill 读取 helper 测试。
- [ ] 用临时目录模拟 `D:\skill`。
- [ ] 验证能按业务日期找到日报正文和核对记录。
- [ ] 验证路径逃逸会被拒绝。
- [ ] 验证参考目录不存在时返回 `source_status.output_skill=missing`，不是 500。

测试示例：

```python
from datetime import date

import pytest

from app.services.hermes_data_audit_service import HermesDataAuditService, OutputSkillPathViolationError


def test_reads_reference_files_for_business_date(tmp_path):
    (tmp_path / "2026-6-18_日报正文.txt").write_text("全厂总产量 100 吨", encoding="utf-8")
    (tmp_path / "2026-6-18_核对记录.txt").write_text("total_electricity_kwh=200", encoding="utf-8")

    service = HermesDataAuditService(output_skill_root=tmp_path)

    result = service._read_output_skill_business_date(date(2026, 6, 18))

    assert result["files"]
    assert "全厂总产量" in result["raw_text"]


def test_rejects_path_outside_output_skill_root(tmp_path):
    service = HermesDataAuditService(output_skill_root=tmp_path)

    with pytest.raises(OutputSkillPathViolationError):
        service._read_output_skill_file("../secret.txt")
```

**实现：**

- [ ] 不新增 `backend/app/services/hermes_output_skill_service.py`。
- [ ] 在 `backend/app/services/hermes_data_audit_service.py` 内新增 `_read_output_skill_business_date()` 和 `_read_output_skill_file()` 私有 helper。
- [ ] 默认 root 从环境变量读取，例如 `OUTPUT_SKILL_ROOT`。
- [ ] 没有配置或目录不存在时，返回明确的 `source_status.output_skill=missing`。
- [ ] 只读 `txt`、`json`、`csv`、`xls`、`xlsx` 的元信息和可解析内容。
- [ ] 解析文件内容时优先调用现有 `parse_output_skill_reference_file()`。
- [ ] 不把原始文件写回。

核心实现示例：

```python
def _read_output_skill_business_date(self, business_date: date) -> dict[str, Any]:
    root_path = self._resolve_output_skill_root()
    if root_path is None or not root_path.exists():
        return {"files": [], "raw_text": "", "parsed": {}, "status": "missing"}

    patterns = self._date_patterns(business_date)
    files = [path for path in root_path.iterdir() if any(pattern in path.name for pattern in patterns)]
    parsed_files = [parse_output_skill_reference_file(path) for path in files if path.is_file()]
    return self._summarize_output_skill_files(parsed_files)
```

**验证命令：**

```powershell
python -m pytest backend/tests/test_hermes_data_audit_service.py -q
python -m compileall backend/app/services/hermes_data_audit_service.py
```

**预期结果：**

```text
all passed
```

**提交：**

```powershell
git add backend/app/services/hermes_data_audit_service.py backend/tests/test_hermes_data_audit_service.py
git commit -m "Read output skill references for Hermes audit"
```

### Task 4: 新增三边核验服务

**目标：** Hermes 能把 MES、数据中枢、输出 skill 放到同一张对比表里。

**第一批字段：**

```python
DEFAULT_AUDIT_FIELDS = [
    "total_output",
    "workshop_output",
    "wip_total",
    "inbound_total",
    "total_electricity_kwh",
    "total_gas_m3",
    "yield_rate",
    "contract_amount",
    "ton_cost",
]
```

**差异分类：**

```python
DIFF_CATEGORIES = {
    "matched",
    "hub_mismatch",
    "mes_missing",
    "hub_missing",
    "output_skill_missing",
    "unit_mismatch",
    "date_window_mismatch",
    "alias_mismatch",
    "formula_mismatch",
    "cannot_decide",
}
```

**测试先行：**

- [ ] 在 `backend/tests/test_hermes_data_audit_service.py` 增加三边核验测试。
- [ ] fake MES 返回 100。
- [ ] fake 数据中枢返回 90。
- [ ] fake 输出 skill 返回 100。
- [ ] 预期分类为 `hub_mismatch`，并生成修正建议。

测试示例：

```python
from datetime import date

from app.services.hermes_data_audit_service import HermesDataAuditService


class FakeMesReadService:
    def read_sources(self, **kwargs):
        return {"summary": {"total_output": 100}}


class FakeHubReadService:
    def read_current_values(self, **kwargs):
        return {"total_output": 90}


class FakeOutputSkillService:
    def read_business_date(self, business_date):
        return {"parsed": {"total_output": 100}, "files": ["2026-6-18_日报正文.txt"]}


def test_three_way_audit_marks_hub_mismatch(db_session):
    service = HermesDataAuditService(
        db=db_session,
        mes_read_service=FakeMesReadService(),
        hub_read_service=FakeHubReadService(),
        output_skill_service=FakeOutputSkillService(),
    )

    run = service.create_run(
        business_date=date(2026, 6, 18),
        fields=["total_output"],
        actor_user_id=1,
        dry_run=True,
    )

    diff = run.diff_payload["total_output"]
    assert diff["category"] == "hub_mismatch"
    assert diff["mes_value"] == 100
    assert diff["hub_value"] == 90
    assert diff["output_skill_value"] == 100
```

**实现：**

- [ ] 新建 `backend/app/services/hermes_data_audit_service.py`。
- [ ] 实现 `create_run()`。
- [ ] 实现 `_compare_field()`。
- [ ] 实现 `_build_correction_suggestions()`。
- [ ] 核验完成后写 `HermesDataAuditRun`。
- [ ] dry-run 默认只生成建议，不修改数据中枢。

核心比较逻辑示例：

```python
def compare_values(field: str, mes_value: Any, hub_value: Any, output_value: Any) -> dict[str, Any]:
    normalized_mes = normalize_value(field, mes_value)
    normalized_hub = normalize_value(field, hub_value)
    normalized_output = normalize_value(field, output_value)

    if normalized_mes == normalized_hub == normalized_output:
        category = "matched"
    elif normalized_mes == normalized_output and normalized_hub != normalized_mes:
        category = "hub_mismatch"
    elif normalized_mes is None:
        category = "mes_missing"
    elif normalized_hub is None:
        category = "hub_missing"
    elif normalized_output is None:
        category = "output_skill_missing"
    else:
        category = "cannot_decide"

    return {
        "field": field,
        "category": category,
        "mes_value": mes_value,
        "hub_value": hub_value,
        "output_skill_value": output_value,
    }
```

**验证命令：**

```powershell
python -m pytest backend/tests/test_hermes_data_audit_service.py -q
python -m compileall backend/app/services/hermes_data_audit_service.py
```

**预期结果：**

```text
3 passed
```

**提交：**

```powershell
git add backend/app/services/hermes_data_audit_service.py backend/tests/test_hermes_data_audit_service.py
git commit -m "Add Hermes three-way data audit service"
```

### Task 5: 新增数据中枢读取与低风险修正执行器

**目标：** Hermes 能读数据中枢当前值，也能执行受控的数据中枢修正动作。

**第一阶段支持的 action_type：**

```python
SUPPORTED_CORRECTION_ACTIONS = {
    "mapping_alias_upsert",
    "mapping_field_rule_upsert",
    "mapping_reconciliation_run",
    "daily_report_recalculate",
}
```

**设计重点：**

- 数据中枢允许 Hermes 操作，但实现上仍要分类型执行。
- 每个 action 执行前先记录 `before_payload`。
- 每个 action 执行后记录 `after_payload`。
- 能回滚的 action 写 `rollback_payload`。
- 不能回滚的 action 必须标明原因。

**测试先行：**

- [ ] 在 `backend/tests/test_hermes_data_audit_service.py` 增加 correction action 测试。
- [ ] 创建一个 `mapping_alias_upsert` action。
- [ ] dry-run 时不改数据库，只把 action 保持 `pending`。
- [ ] 非 dry-run 时执行，并把 action 改成 `applied`。

测试示例：

```python
def test_apply_correction_dry_run_does_not_write_hub(db_session):
    service = build_service(db_session)
    run = make_run_with_pending_action(db_session, action_type="mapping_alias_upsert")

    result = service.apply_corrections(run_id=run.id, action_ids=[run.actions[0].id], dry_run=True, actor_user_id=1)

    assert result["dry_run"] is True
    assert db_session.get(HermesDataCorrectionAction, run.actions[0].id).status == "pending"


def test_apply_correction_records_audit_payloads(db_session):
    service = build_service(db_session)
    run = make_run_with_pending_action(db_session, action_type="mapping_alias_upsert")

    service.apply_corrections(run_id=run.id, action_ids=[run.actions[0].id], dry_run=False, actor_user_id=1)

    action = db_session.get(HermesDataCorrectionAction, run.actions[0].id)
    assert action.status == "applied"
    assert action.after_payload
    assert action.rollback_payload
```

**实现：**

- [ ] 在 `HermesDataAuditService` 中增加 `apply_corrections()`。
- [ ] 新增内部执行器方法：
  - `_apply_mapping_alias_upsert()`
  - `_apply_mapping_field_rule_upsert()`
  - `_run_mapping_reconciliation()`
  - `_trigger_daily_report_recalculate()`
- [ ] 第一版可以只真正落地 `mapping_alias_upsert` 和 `mapping_reconciliation_run`。
- [ ] 其他 action 可以先生成 `pending`，但不要假装已执行。

**验证命令：**

```powershell
python -m pytest backend/tests/test_hermes_data_audit_service.py -q
```

**预期结果：**

```text
5 passed
```

**提交：**

```powershell
git add backend/app/services/hermes_data_audit_service.py backend/tests/test_hermes_data_audit_service.py
git commit -m "Add auditable hub corrections for Hermes data audit"
```

### Task 6: 新增 API router

**目标：** 管理端或 Agent 可以通过 API 触发 Hermes 数据核验和数据中枢修正。

**权限原则：**

- 读取 run：后台登录用户可读。
- 创建 run：管理员或 Hermes 高权限身份可用。
- 应用修正：管理员或 Hermes 高权限身份可用。
- MES 仍只读。

**测试先行：**

- [ ] 新建 `backend/tests/test_hermes_data_audit_router.py`。
- [ ] 参考 `test_mapping_reconciliation_route.py` 的权限 override 风格。
- [ ] 测试 `POST /api/v1/hermes/data-audit/runs`。
- [ ] 测试 `GET /api/v1/hermes/data-audit/runs/{run_id}`。
- [ ] 测试 `POST /api/v1/hermes/data-audit/runs/{run_id}/corrections`。

测试示例：

```python
def test_create_hermes_data_audit_run(client):
    response = client.post(
        "/api/v1/hermes/data-audit/runs",
        json={
            "business_date": "2026-06-18",
            "fields": ["total_output"],
            "dry_run": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["business_date"] == "2026-06-18"
    assert "match_rate" in body


def test_get_hermes_data_audit_run(client, existing_audit_run):
    response = client.get(f"/api/v1/hermes/data-audit/runs/{existing_audit_run.id}")

    assert response.status_code == 200
    assert response.json()["id"] == existing_audit_run.id
```

**实现：**

- [ ] 新建 `backend/app/schemas/hermes_data_audit.py`。
- [ ] 新建 `backend/app/routers/hermes_data_audit.py`。
- [ ] 在 `backend/app/main.py` 注册 router：

```python
from app.routers import hermes_data_audit

app.include_router(
    hermes_data_audit.router,
    prefix="/api/v1/hermes/data-audit",
    tags=["Hermes Data Audit"],
)
```

**验证命令：**

```powershell
python -m pytest backend/tests/test_hermes_data_audit_router.py -q
python -m compileall backend/app/routers/hermes_data_audit.py backend/app/schemas/hermes_data_audit.py
```

**预期结果：**

```text
3 passed
```

**提交：**

```powershell
git add backend/app/routers/hermes_data_audit.py backend/app/schemas/hermes_data_audit.py backend/app/main.py backend/tests/test_hermes_data_audit_router.py
git commit -m "Expose Hermes data audit API"
```

### Task 7: 接入输出 skill 默认字段映射

**目标：** 把当前 0% 字段匹配问题先修掉一批。

第一批映射：

```python
DEFAULT_OUTPUT_SKILL_FIELD_ALIASES = {
    "total_electricity_kwh": ["total_electricity_kwh", "energy_kwh", "高压总用电", "总用电"],
    "total_gas_m3": ["total_gas_m3", "gas_m3", "天然气合计", "总天然气"],
    "wip_total": ["wip_total", "wip_tons", "在制料", "在制总量"],
    "total_output": ["车间总产量", "全厂总产量", "总产量"],
    "inbound_total": ["入库成品日合计", "入库量", "入库合计"],
    "yield_rate": ["日成品率", "成品率", "yield_rate"],
    "contract_amount": ["当天接合同", "合同量", "contract_amount"],
    "remaining_contract_amount": ["总余合同量", "剩余合同量"],
}
```

**测试先行：**

- [ ] 在 `backend/tests/test_hermes_data_audit_service.py` 增加中文字段解析测试。
- [ ] 输入 `入库成品日合计 123.4 吨`。
- [ ] 预期解析到 `inbound_total=123.4`。

测试示例：

```python
def test_parses_default_output_skill_aliases(tmp_path):
    (tmp_path / "2026-6-18_日报正文.txt").write_text(
        "入库成品日合计 123.4 吨\n日成品率 96.5%",
        encoding="utf-8",
    )
    service = HermesDataAuditService(output_skill_root=tmp_path)

    result = service._read_output_skill_business_date(date(2026, 6, 18))

    assert result["parsed"]["inbound_total"] == 123.4
    assert result["parsed"]["yield_rate"] == 96.5
```

**实现：**

- [ ] 在 `HermesDataAuditService` 的输出 skill 私有 helper 内新增轻量字段提取。
- [ ] 优先复用已有 `parse_output_skill_reference_file`。
- [ ] 只补关键字段，不做全量自然语言理解。
- [ ] 保留 raw_text，方便人工核查。

**验证命令：**

```powershell
python -m pytest backend/tests/test_hermes_data_audit_service.py backend/tests/test_mapping_reconciliation_route.py -q
```

**预期结果：**

```text
all passed
```

**提交：**

```powershell
git add backend/app/services/hermes_data_audit_service.py backend/tests/test_hermes_data_audit_service.py
git commit -m "Map key output skill fields for Hermes audit"
```

### Task 8: 历史三天回放脚本

**目标：** 一条命令跑 2026-06-16、2026-06-17、2026-06-18 三天核验，输出匹配率、差异和建议动作。

**新增文件：**

- `backend/scripts/run_hermes_data_audit_backfill.py`

**测试先行：**

- [ ] 如果项目已有 scripts 测试风格，按现有风格补。
- [ ] 如果没有，先只测 service，不单测脚本。

脚本参数：

```text
--start-date 2026-06-16
--end-date 2026-06-18
--dry-run
--fields total_output,inbound_total,total_electricity_kwh,total_gas_m3,yield_rate
```

脚本输出示例：

```text
2026-06-16 match_rate=0.87 diff_count=2 correction_action_count=2
2026-06-17 match_rate=0.91 diff_count=1 correction_action_count=1
2026-06-18 match_rate=0.86 diff_count=3 correction_action_count=2
```

**实现：**

- [ ] 新增脚本，只调用 `HermesDataAuditService`。
- [ ] 默认 `--dry-run` 为 true。
- [ ] 输出不要包含密码、连接串、token。
- [ ] 非 dry-run 必须显式传 `--apply-corrections`。

**验证命令：**

```powershell
python backend/scripts/run_hermes_data_audit_backfill.py --start-date 2026-06-16 --end-date 2026-06-18 --dry-run
```

**预期结果：**

```text
三天都有 run 结果
没有敏感信息输出
失败时能指出是哪一天、哪个字段、哪个来源失败
```

**提交：**

```powershell
git add backend/scripts/run_hermes_data_audit_backfill.py
git commit -m "Add Hermes historical data audit backfill script"
```

### Task 9: 云端只读验证和数据中枢 dry-run

**目标：** 用真实云端环境验证 Hermes 能看见三边数据，但先不自动改生产数据。

**执行前检查：**

- [ ] 确认 MES 使用只读账号。
- [ ] 确认数据中枢环境变量里没有把密码打印到日志。
- [ ] 确认 `OUTPUT_SKILL_ROOT` 指向云端挂载的只读参考目录。
- [ ] 确认数据库迁移已执行。

**云端 dry-run：**

```powershell
curl -X POST "https://<data-hub-host>/api/v1/hermes/data-audit/runs" `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer <admin-token>" `
  -d "{\"business_date\":\"2026-06-18\",\"fields\":[\"total_output\",\"inbound_total\",\"total_electricity_kwh\",\"total_gas_m3\",\"yield_rate\"],\"dry_run\":true}"
```

**验收：**

- [ ] API 返回 `status=completed`。
- [ ] `match_rate` 有数值。
- [ ] `diff_payload` 中能看到 MES、数据中枢、输出 skill 三边值。
- [ ] `correction_action_count` 大于等于 0。
- [ ] 日志里没有密码、连接串、token。

**注意：**

这一步只做 dry-run，不自动改生产数据。

### Task 10: 第一批低风险修正和重跑

**目标：** 只对数据中枢做低风险修正，然后重跑核验，确认对齐率提升。

**可执行修正：**

- 字段映射。
- 别名映射。
- 对齐结果保存。
- 数据中枢重算触发。

**执行：**

- [ ] 对 2026-06-16 执行低风险修正。
- [ ] 重跑 2026-06-16。
- [ ] 对 2026-06-17 执行低风险修正。
- [ ] 重跑 2026-06-17。
- [ ] 对 2026-06-18 执行低风险修正。
- [ ] 重跑 2026-06-18。

**验收标准：**

```text
三天关键字段平均 match_rate >= 0.85
所有 applied action 都有 before_payload
所有 applied action 都有 after_payload
所有 applied action 都有 evidence_payload
可回滚 action 都有 rollback_payload
未对齐字段都有 category
```

**失败时处理：**

- [ ] 如果 MES 缺数据，标记 `mes_missing`，不要编造。
- [ ] 如果输出 skill 缺数据，标记 `output_skill_missing`，不要编造。
- [ ] 如果是单位问题，标记 `unit_mismatch`，补单位规则。
- [ ] 如果是日期窗口问题，标记 `date_window_mismatch`，补业务日规则。
- [ ] 如果无法判断，标记 `cannot_decide`，交给人工或后续任务。

## 5. 必须画清楚的系统图

### 5.1 总架构图

```text
                ┌──────────────────────────┐
                │ 外部 MES SQL Server       │
                │ 只读，不允许 Hermes 写     │
                └────────────┬─────────────┘
                             │ read-only query
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ HermesMesReadService                                         │
│ 白名单 query_key + limit + source_status + 脱敏错误           │
└────────────┬─────────────────────────────────────────────────┘
             │
             │ mes summary/hash/source refs
             ▼
┌──────────────────────────────────────────────────────────────┐
│ HermesDataAuditService                                       │
│ 三边核验、差异分类、修正建议、action 幂等、match_rate 计算       │
└───────┬───────────────────┬───────────────────┬─────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐
│ 数据中枢 DB   │    │ Mapping 服务     │    │ D:\输出skill       │
│ 可读可写      │    │ 现有 dry-run     │    │ 只读参考源         │
└──────┬───────┘    └────────┬────────┘    └─────────┬────────┘
       │                     │                       │
       ▼                     ▼                       ▼
┌──────────────────────────────────────────────────────────────┐
│ hermes_data_audit_runs / hermes_data_correction_actions       │
│ 所有 run、差异、修正、失败、回滚、来源状态都留痕                 │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 四条数据路径

```text
Happy path:
  请求日期 -> MES ok -> 数据中枢 ok -> 输出skill ok -> 差异分类 -> 生成 action -> dry-run/低风险 apply

Nil path:
  请求字段为空 -> 使用 DEFAULT_AUDIT_FIELDS -> 记录 request_payload.default_fields=true

Empty path:
  某来源返回空数组 -> source_status.<source>=empty -> 字段标记 <source>_missing -> 不生成自动修正

Error path:
  某来源超时/解析失败 -> source_status.<source>=failed -> source_errors 写脱敏摘要 -> run.status=failed 或 completed_with_source_error
```

### 5.3 run 状态机

```text
pending
  │ start
  ▼
running
  ├── all sources comparable ──────────────▶ completed
  ├── non-critical source empty ───────────▶ completed_with_missing_source
  ├── source failed / validation failed ───▶ failed
  └── correction apply requested ──────────▶ correcting

correcting
  ├── all selected actions applied ────────▶ corrected
  ├── some actions failed ─────────────────▶ correction_partial_failed
  └── feature flag disabled ───────────────▶ completed
```

### 5.4 action 状态机

```text
pending
  ├── dry-run preview ─────────────▶ pending
  ├── feature flag disabled ───────▶ blocked
  ├── duplicate idempotency key ───▶ skipped_duplicate
  ├── low-risk apply ok ───────────▶ applied
  └── apply failed ────────────────▶ failed

applied
  ├── rollback ok ─────────────────▶ rolled_back
  └── rollback failed ─────────────▶ rollback_failed
```

## 6. Error & Rescue Registry

这里的“Rescue”就是“出错后系统怎么接住”。不能只写“处理异常”，必须写清楚谁抛错、谁接住、用户看到什么。

| 方法 / 路径 | 可能出错 | 建议异常名 | 是否接住 | 接住后动作 | 用户 / 调用方看到 |
|---|---|---|---|---|---|
| `HermesMesReadService.read_sources()` | query_key 不在白名单 | `UnsupportedMesQueryKeyError` | 是 | 返回 400，不查 MES | `unsupported_mes_query_key` |
| `HermesMesReadService.read_sources()` | SQL Server 超时 | `MesReadTimeoutError` | 是 | 标记 `source_status.mes=failed`，不生成自动修正 | `mes_source_failed` |
| `HermesMesReadService.read_sources()` | MES 返回空 | 无异常 | 是 | 标记 `source_status.mes=empty` | 字段分类 `mes_missing` |
| `HermesDataAuditService._read_output_skill_business_date()` | 参考目录不存在 | `OutputSkillSourceMissingError` | 是 | 标记 `source_status.output_skill=missing` | `output_skill_source_missing` |
| `HermesDataAuditService._read_output_skill_file()` | 路径逃逸 | `OutputSkillPathViolationError` | 是 | 返回 400，记录安全日志 | `invalid_reference_file` |
| `parse_output_skill_reference_file()` | 不支持文件类型 | 无异常，已有 `unsupported` | 是 | 原样转成 `source_status.output_skill=unsupported` | `unsupported_reference_file` |
| `HermesDataAuditService.create_run()` | 三边都不可比 | `NoComparableDataError` | 是 | run 写 `failed` | `no_comparable_data` |
| `compare_values()` | 单位不明 | `UnitRuleMissingError` | 是 | 字段分类 `unit_mismatch` | `unit_mismatch` |
| `apply_corrections()` | feature flag 关闭 | `CorrectionApplyDisabledError` | 是 | action 写 `blocked` | `apply_disabled` |
| `apply_corrections()` | 重复执行同一 action | `DuplicateCorrectionActionError` | 是 | action 写 `skipped_duplicate` | `duplicate_action_skipped` |
| `_apply_mapping_alias_upsert()` | 唯一键冲突 | `IntegrityError` | 是 | 回滚事务，action 写 `failed` | `correction_failed` |
| `_trigger_daily_report_recalculate()` | 后台任务触发失败 | `ReportRecalculateFailedError` | 是 | action 写 `failed`，保留错误摘要 | `recalculate_failed` |

禁止：

- 禁止 `except Exception: pass`。
- 禁止吞掉 MES 失败后继续算“成功”。
- 禁止把错误详情里的密码、token、连接串返回给前端或写入日志。

## 7. Failure Modes Registry

| Codepath | Failure mode | Rescued? | Test? | User sees? | Logged? | 严重度 |
|---|---|---|---|---|---|---|
| 创建 run | 同一天同字段重复提交 | 是，靠 `run_key` | 必须 | 返回已有或新 run，不重复污染 | 是 | P1 |
| MES 查询 | 超时或连接失败 | 是 | 必须 | `mes_source_failed` | 是 | P1 |
| MES 查询 | 返回 0 行 | 是 | 必须 | `mes_missing` | 是 | P1 |
| 输出 skill 读取 | 参考目录未挂载 | 是 | 必须 | `output_skill_source_missing` | 是 | P1 |
| 输出 skill 读取 | 读到 `.exe/.cmd/.ps1` | 是 | 必须 | `unsupported_reference_file` | 是 | P1 |
| 数据中枢读取 | 查询条件导致全表大扫 | 是，靠 limit 和日期必填 | 必须 | `invalid_audit_scope` | 是 | P1 |
| 差异比较 | kg/吨单位不明 | 是 | 必须 | `unit_mismatch` | 是 | P1 |
| 修正 apply | feature flag 关闭 | 是 | 必须 | `apply_disabled` | 是 | P1 |
| 修正 apply | action 执行一半失败 | 是，单事务 | 必须 | `correction_failed` | 是 | P1 |
| 修正 apply | 高风险 action 被自动执行 | 必须防止 | 必须 | `risk_level_not_allowed` | 是 | P0 |
| 重跑核验 | 修正后匹配率下降 | 是 | 必须 | `match_rate_regressed` | 是 | P1 |
| 审计记录 | payload 过大 | 是，存摘要/hash | 必须 | `payload_summarized` | 是 | P2 |

任何 P0/P1 没有测试，不能进入云端 apply。

## 8. 安全、观测、部署和回滚门禁

### 8.1 安全门禁

| 项 | 要求 |
|---|---|
| MES 权限 | 只读账号，只走白名单 query_key，不接受任意 SQL |
| 数据中枢 apply | 默认 feature flag 关闭，管理员或 Hermes 高权限身份才可打开 |
| 路径安全 | 输出 skill 路径必须 resolve 后仍在 root 内 |
| 文件类型 | 只读文本、JSON、Excel、CSV；拒绝脚本和可执行文件 |
| 审计脱敏 | 密码、token、连接串、私钥片段必须脱敏 |
| IDOR 防护 | `GET /runs/{id}` 和 apply 接口必须校验用户权限 |
| 高风险动作 | 删除、批量覆盖日报、真实外发、MES 写入全部禁止自动执行 |

### 8.2 观测指标

必须有结构化日志字段：

```text
run_id
run_key
business_date
actor_user_id
source=mes|hub|output_skill
source_status
field_name
diff_category
action_id
action_type
risk_level
idempotency_key
duration_ms
```

建议指标：

| 指标 | 含义 |
|---|---|
| `hermes_data_audit_run_total` | run 创建数 |
| `hermes_data_audit_source_failed_total` | 来源失败次数 |
| `hermes_data_audit_match_rate` | 每次 run 的匹配率 |
| `hermes_data_correction_action_total` | action 数 |
| `hermes_data_correction_apply_failed_total` | apply 失败数 |
| `hermes_data_audit_duration_ms` | run 耗时 |

第一阶段告警：

- MES 连续 3 次失败。
- 输出 skill 参考目录连续 3 次缺失。
- 任意高风险 action 被请求 apply。
- 修正后匹配率下降超过 5 个百分点。
- 审计日志写入失败。

### 8.3 部署顺序

```text
1. 部署迁移：只加表和索引，不改旧表语义
2. 部署代码：feature flag 默认关闭
3. 后台 dry-run：跑三天历史数据
4. 看日志和 run 结果：确认 source_status 和 diff_category 正常
5. 打开低风险 apply flag：只给管理员/Hermes 高权限身份
6. 对一日执行低风险修正
7. 重跑同一日核验
8. 三日全部通过后，再保留开关进入常态
```

### 8.4 回滚流程

```text
发现问题
  │
  ├── 只是 API 或服务报错
  │     └── 关闭 HERMES_DATA_AUDIT_APPLY_ENABLED，保留 dry-run
  │
  ├── 低风险规则写错
  │     └── 按 hermes_data_correction_actions.rollback_payload 回滚
  │
  ├── 新迁移影响线上
  │     └── 回滚代码，保留新表不读；必要时执行 Alembic downgrade
  │
  └── 审计表写入异常
        └── 禁止 apply，只允许 read-only audit，修复后再打开
```

### 8.5 云端验收硬门槛

上线 apply 前必须满足：

```text
三天 dry-run 都能生成 run
三天 source_status 都不是 silent failure
所有 P0/P1 failure mode 都有测试
三天平均 match_rate >= 0.85
match_rate 下降时会阻断 apply
所有 applied action 都有 before/after/evidence/rollback
日志和审计中没有真实密码、token、连接串
```

## 9. 最终验证清单

本 plan 实施完后，至少运行：

```powershell
python -m pytest backend/tests/test_hermes_mes_read_service.py -q
python -m pytest backend/tests/test_hermes_data_audit_service.py -q
python -m pytest backend/tests/test_hermes_data_audit_router.py -q
python -m pytest backend/tests/test_mapping_reconciliation_route.py -q
python -m compileall backend/app/models/hermes_data_audit.py backend/app/services/hermes_mes_read_service.py backend/app/services/hermes_data_audit_service.py backend/app/routers/hermes_data_audit.py
git diff --check
```

敏感信息检查：

```powershell
rg -n "password|passwd|pwd|secret|token|连接串|数据库密码" backend/app backend/tests docs/superpowers/plans/2026-06-19-hermes-high-privilege-data-audit-and-hub-correction-plan.md
```

这里不是要求没有任何命中，而是要求没有真实密码、token、连接串明文。

## 10. 上线顺序

推荐上线顺序：

1. 合并模型、迁移和服务，不开放自动修正。
2. 开放 dry-run API，只允许管理员用。
3. 用三天历史数据跑 dry-run。
4. 补字段映射和别名映射。
5. 只开放低风险修正。
6. 重跑三天历史数据。
7. 对齐率达到 85% 后，再讨论是否做统一事实包。

## 11. 完成标准

这项工作完成时，应该能回答这几个问题：

- 2026-06-16、2026-06-17、2026-06-18 每天 MES 原始值是多少。
- 同一天数据中枢当前值是多少。
- 同一天 `D:\输出skill` 成品值是多少。
- 哪些字段对齐，哪些字段不对齐。
- 不对齐是因为字段名、单位、日期、别名、缺数据，还是算法口径。
- Hermes 改了数据中枢哪张表、哪条规则。
- 每次修改的改前值、改后值、原因、证据和回滚方式是什么。
- 修完后匹配率是否达到 85% 以上。

如果这些问题答不上来，就不能算完成。

## 12. 后续阶段，不在本次实现

第一阶段通过后，再考虑：

- 关键字段 95% 以上同口径匹配。
- 日报正文自动生成结果接近 `D:\输出skill` 成品。
- 高风险数据中枢修正进入审批流。
- Hermes 自动识别当天缺哪类数据。
- 统一事实包。
- 前端增加 Hermes 数据审计工作台。

## 13. NOT in scope

本轮明确不做这些，避免计划膨胀：

- 前端 Hermes 数据审计工作台：先用 API、脚本和数据库记录跑通三天历史验收。
- 统一事实包：当前用户明确说数据不准，先查准和修准，再谈事实包。
- MES 写入：MES 永远只读。
- 输出 skill 原始文件修改：它是参考源，不是被修对象。
- 高风险自动修正：删除、批量覆盖日报、真实外发、改历史业务数据都不自动执行。
- 图片 OCR 全量解析：输出 skill 图片很多，第一阶段只处理可解析文本、JSON、Excel。
- 95% 全字段匹配：第一阶段验收是关键字段 85%+，95% 放到后续阶段。

## 14. What already exists

这些现有能力必须复用：

| 已有能力 | 文件 / 入口 | 本计划怎么用 |
|---|---|---|
| MES SQL Server 只读 adapter | `backend/app/adapters/sqlserver_mes_adapter.py` | Hermes 包装白名单读，不重写 MES 连接 |
| 输出 skill 解析 | `backend/app/services/mapping_reconciliation_service.py` 的 `parse_output_skill_reference_file()` | Hermes 只做只读包装和关键字段提取 |
| 输出 skill 对齐 run | `backend/app/routers/mapping_reconciliation.py`、`MappingReconciliationRun` | Hermes 触发 dry-run 和读取结果 |
| 对账差异模型 | `DataReconciliationItem` | 继续作为通用差异记录，不塞高权限 action |
| Hermes 治理服务 | `backend/app/services/hermes_governance_service.py` | 复用安全/脱敏/治理思路 |
| outbox 和外部日志 | `agent_outbox_messages`、`external_message_logs` | 真实外发仍走原通道，不让 Hermes 绕过 |

## 15. Dream state delta

这份计划完成后，系统还不是“全自动可信数据平台”，但会跨过最重要的一步：

```text
现在：
  数据中枢有数据，但 Hermes 不知道哪些数可信，哪些数缺口，哪些数口径不同。

本计划完成：
  Hermes 能把 MES、数据中枢、输出 skill 三边摆在一张表里，并安全修数据中枢低风险规则。

还没完成：
  全量 95%+ 匹配、前端审计工作台、高风险审批流、统一事实包、图片 OCR、长期数据质量仪表盘。
```

## 16. Stale Diagram Audit

本计划新增的 ASCII 图都在本文件内，当前没有触碰代码文件里的旧图。

实施后如果新增代码注释图，必须同步检查：

- `HermesDataAuditService` 的数据流图是否还对应真实方法。
- run/action 状态机是否和数据库状态枚举一致。
- 部署和回滚流程是否和实际 feature flag 名称一致。

## 17. Implementation Tasks

Synthesized from this review's findings. Each task derives from a specific finding above.

- [ ] **T1 (P1, human: ~2h / CC: ~15min)** — Safety gate — Add feature flag and idempotency tests before implementing apply
  - Surfaced by: CEO Review P1 risks — duplicate correction and accidental production writes.
  - Files: `backend/tests/test_hermes_data_audit_service.py`, `backend/app/services/hermes_data_audit_service.py`
  - Verify: `python -m pytest backend/tests/test_hermes_data_audit_service.py -q`

- [ ] **T2 (P1, human: ~3h / CC: ~20min)** — Persistence — Add `run_key`, `source_status`, `source_errors`, `idempotency_key`, `risk_level`, `rollback_status`
  - Surfaced by: Data model review — current model cannot prove source failures or duplicate action prevention.
  - Files: `backend/app/models/hermes_data_audit.py`, `backend/alembic/versions/0049_hermes_data_audit.py`
  - Verify: `python -m pytest backend/tests/test_hermes_data_audit_service.py -q`

- [ ] **T3 (P1, human: ~2h / CC: ~15min)** — Error handling — Implement named exception classes and no silent source failures
  - Surfaced by: Error & Rescue Registry — MES/output skill failures must be visible.
  - Files: `backend/app/services/hermes_mes_read_service.py`, `backend/app/services/hermes_data_audit_service.py`
  - Verify: `python -m pytest backend/tests/test_hermes_mes_read_service.py backend/tests/test_hermes_data_audit_service.py -q`

- [ ] **T4 (P1, human: ~2h / CC: ~15min)** — Observability — Add structured logs and basic metrics for run/action/source status
  - Surfaced by: Observability review — without logs, a bad run cannot be reconstructed.
  - Files: `backend/app/services/hermes_data_audit_service.py`, existing logging/metrics helper files if present
  - Verify: unit tests assert log context or metrics calls through project test patterns.

- [ ] **T5 (P1, human: ~2h / CC: ~15min)** — Rollout — Add cloud dry-run checklist and block apply until three-day replay passes
  - Surfaced by: Deployment review — production apply must not open before dry-run proves source status and match rate.
  - Files: `backend/scripts/run_hermes_data_audit_backfill.py`, docs in this plan
  - Verify: script dry-run for 2026-06-16 to 2026-06-18 returns no silent failures.

- [ ] **T6 (P2, human: ~1h / CC: ~10min)** — Operator experience — Shape API and script output around scan-first audit decisions
  - Surfaced by: Design Review — first phase has no UI, so API/script output must carry the hierarchy a UI would otherwise provide.
  - Files: `backend/app/schemas/hermes_data_audit.py`, `backend/app/routers/hermes_data_audit.py`, `backend/scripts/run_hermes_data_audit_backfill.py`
  - Verify: router tests assert response contains `headline_status`, `source_health`, `diff_summary`, `recommended_next_step`.

## 18. Plan Design Review: Operator Experience Contract

### 18.1 UI scope assessment

This phase has no UI scope.

No new screen, page, component, navigation change, design-system change, responsive behavior, or visual mockup is in scope. The first phase is API, service, database audit, script, and cloud dry-run only.

Design score:

```text
Initial design applicability: no frontend scope
Operator experience completeness before this section: 5/10
Operator experience completeness after this section: 8/10
```

Why not 10/10: a true 10 would include a dedicated data audit workbench with saved filters, diff tables, rollback preview, keyboard shortcuts, and reviewed empty/error states. That is explicitly deferred.

### 18.2 What the operator or Agent should see first

Even without a frontend, response shape still has design. The API and backfill script must be scan-first.

Every run result should be ordered like this:

```text
1. headline_status
   completed / failed / completed_with_missing_source / corrected / correction_partial_failed

2. decision_gate
   can_apply=false/true, blocking reason, feature flag status

3. source_health
   MES status, 数据中枢 status, output skill status

4. match_summary
   match_rate, matched_fields, unmatched_fields, regressed=false/true

5. diff_summary
   grouped by category: unit, date, alias, missing source, formula, cannot_decide

6. correction_actions
   sorted by risk_level, then action_type, each with evidence and rollback label

7. recommended_next_step
   one short machine-readable next action
```

小白版理解：不要让人先看一大坨 JSON。先告诉他“能不能信、能不能改、卡在哪里、下一步做什么”。

### 18.3 API response design contract

`POST /api/v1/hermes/data-audit/runs` and `GET /runs/{run_id}` should return a human-scannable envelope:

```json
{
  "id": 1,
  "headline_status": "completed_with_missing_source",
  "business_date": "2026-06-18",
  "decision_gate": {
    "can_apply": false,
    "reason": "output_skill_source_missing",
    "apply_enabled": false
  },
  "source_health": {
    "mes": {"status": "ok", "row_count": 120, "error": null},
    "hub": {"status": "ok", "row_count": 36, "error": null},
    "output_skill": {"status": "missing", "row_count": 0, "error": "output_skill_source_missing"}
  },
  "match_summary": {
    "match_rate": 0.0,
    "matched_fields": 0,
    "unmatched_fields": 9,
    "regressed": false
  },
  "diff_summary": {
    "unit_mismatch": 0,
    "date_window_mismatch": 0,
    "alias_mismatch": 0,
    "missing_source": 9,
    "cannot_decide": 0
  },
  "correction_actions": [],
  "recommended_next_step": "mount_output_skill_reference_and_rerun"
}
```

Rules:

- `headline_status` must be the first meaningful status in responses and scripts.
- `decision_gate.can_apply=false` must explain why in one machine-readable reason.
- `source_health` must appear before field diffs, because source failure explains many diffs.
- `correction_actions` must never hide risk. Show `risk_level`, `status`, `target_table`, `target_key`, `rollback_available`.
- If a run is not safe to apply, do not return a primary-looking apply recommendation.

### 18.4 Script output design contract

`backend/scripts/run_hermes_data_audit_backfill.py` should print one scan-friendly row per business date:

```text
DATE        STATUS                         APPLY  MATCH   MES  HUB  OUTSKILL  DIFFS  NEXT
2026-06-16 completed_with_missing_source   no     0.00    ok   ok   missing   9      mount_output_skill_reference_and_rerun
2026-06-17 completed                       no     0.86    ok   ok   ok        3      review_low_risk_actions
2026-06-18 corrected                       yes    0.89    ok   ok   ok        2      rerun_daily_report_preview
```

Verbose mode may print field details, but default mode should stay one line per day.

### 18.5 Interaction state coverage for API and script

| Feature | Loading | Empty | Error | Success | Partial |
|---|---|---|---|---|---|
| Create audit run | Return `running` only if async; otherwise block until completed with timeout | `no_comparable_data` with source counts | Named error and `source_health` | `completed` with match and diff summary | `completed_with_missing_source` |
| View run | `404` only when run truly missing | Empty correction list is valid | `run_lookup_failed` | Full envelope | Show missing payload sections explicitly |
| Apply corrections | `correcting` if async | No action IDs means `no_actions_selected` | `correction_failed` with action IDs | `applied_count` and rollback refs | `correction_partial_failed` |
| Rerun | `running` if async | Reuse old run source context only if explicit | `rerun_failed` | New run ID and comparison to previous | `match_rate_regressed` blocks apply |
| Backfill script | Print date currently running | Print `no_comparable_data` row | Print failed row, continue next date | One row per date | One row with source-specific missing status |

### 18.6 Future UI guardrails, not in this phase

If a Hermes data audit workbench is added later, it must follow app UI rules:

- No marketing hero.
- No decorative card grid.
- No generic “AI assistant” page copy.
- First viewport should show source health, match trend, blocking reasons, and low-risk actions.
- Use dense but readable tables for diffs.
- Keep `数据中枢` as the product identity, with MES shown only as an external source.
- Primary action must be `Run dry-run` until the feature flag and three-day replay pass.
- `Apply corrections` must never be visually stronger than `Review evidence` when there are unresolved P1 risks.
- Empty state should say what source is missing and what to mount or configure next.
- Error state should show named error, affected source, run ID, and retry/review action.

### 18.7 Design review completion summary

```text
System Audit         | No DESIGN.md found; no UI scope in current phase
Step 0               | Design review not applicable to visuals; operator output still needed hierarchy
Pass 1 Info Arch     | 5/10 -> 8/10 by adding scan-first response hierarchy
Pass 2 States        | 4/10 -> 8/10 by adding API/script state table
Pass 3 Journey       | 5/10 -> 8/10 by defining operator first-read flow
Pass 4 AI Slop       | 8/10 -> 9/10 because no UI; future UI guardrails added
Pass 5 Design System | N/A because no DESIGN.md and no UI
Pass 6 Responsive    | N/A because no UI
Pass 7 Decisions     | First phase remains API/script only; future workbench deferred
Mockups              | Skipped because no UI scope
```

## 19. Plan Eng Review: Final Execution Lock

这一节是最终工程锁定，优先级高于前面所有早期草案描述。

### 19.1 工程审查结论

CodeGraph 审查确认：

- 现有 `SqlServerMesAdapter` 已经能做 MES SQL Server 只读数据采集，不能再绕开它开放任意 SQL。
- 现有 `parse_output_skill_reference_file()` 已经能读输出 skill 成品文件，不能再重写一套 Excel/TXT/JSON 解析器。
- 现有 `build_scope_summary()`、`get_current_user`、`redact_secret_text()` 已经覆盖权限和脱敏基础能力，新增路由必须复用。
- 现有 `mapping_reconciliation` 已经有 run、reference file、admin-only 路由和测试样例，新功能应借鉴它的测试写法，但不要塞进同一个 service 里。

复杂度检查触发：原 plan 曾经规划 3 个新 service、4 组新测试、1 个 router、1 个 migration、1 个脚本，容易过度设计。

最终收敛为：

- 保留 `HermesMesReadService`，只负责 MES 白名单只读采集。
- 保留 `HermesDataAuditService`，负责输出 skill 读取 helper、数据中枢快照读取、三边核验、修正建议和 apply 编排。
- 不新增 `HermesOutputSkillService`。
- 不新增前端页面。
- 不新增新调度系统、新数据平台、新指标后端。
- 第一阶段只做 dry-run、审计记录、低风险数据中枢修正；MES 仍然只读。

### 19.2 最终文件范围

| 类型 | 文件 | 说明 |
|---|---|---|
| 新增 | `backend/app/models/hermes_data_audit.py` | audit run 和 correction action 表 |
| 新增 | `backend/alembic/versions/0049_hermes_data_audit.py` | Alembic 迁移，包含索引 |
| 新增 | `backend/app/schemas/hermes_data_audit.py` | API 入参和出参 |
| 新增 | `backend/app/services/hermes_mes_read_service.py` | MES 只读白名单包装 |
| 新增 | `backend/app/services/hermes_data_audit_service.py` | 核验主服务，含输出 skill 私有 helper |
| 新增 | `backend/app/routers/hermes_data_audit.py` | 管理员专用 API |
| 新增 | `backend/scripts/run_hermes_data_audit_backfill.py` | 历史日期 dry-run 回放 |
| 修改 | `backend/app/models/__init__.py` | 导入新模型 |
| 修改 | `backend/app/main.py` | 注册 router |
| 测试 | `backend/tests/test_hermes_mes_read_service.py` | MES 只读边界 |
| 测试 | `backend/tests/test_hermes_data_audit_service.py` | 三边核验、输出 skill helper、apply 门禁 |
| 测试 | `backend/tests/test_hermes_data_audit_router.py` | 权限、响应 envelope、错误状态 |
| 不做 | `backend/app/services/hermes_output_skill_service.py` | 不新增，避免重复抽象 |
| 不做 | `backend/tests/test_hermes_output_skill_service.py` | 不新增，相关测试放进 audit service 测试 |

### 19.3 最终依赖方向

```text
API router
  -> HermesDataAuditService
      -> HermesMesReadService
          -> SqlServerMesAdapter
      -> parse_output_skill_reference_file()
      -> 数据中枢现有 ORM 查询
      -> HermesDataAuditRun / HermesCorrectionAction
      -> redacted structured logs
```

禁止反向依赖：

- `SqlServerMesAdapter` 不能依赖 Hermes。
- `mapping_reconciliation_service.py` 不能依赖 Hermes。
- 输出 skill helper 不能写文件。
- MES 侧不能有 `INSERT`、`UPDATE`、`DELETE`、`MERGE`、`EXEC`。

### 19.4 测试覆盖矩阵

| 路径 | 必测分支 |
|---|---|
| `POST /hermes-data-audit/runs` | admin 成功、非 admin 403、缺 business_date 400、MES 失败、输出 skill 缺失、数据中枢为空、三边都不可比 |
| `HermesMesReadService.read_sources()` | query_key 白名单、limit 上限、SQL Server timeout、空结果、敏感错误脱敏 |
| 输出 skill helper | 目录缺失、路径逃逸、中文字段解析、unsupported file、raw_text 保留 |
| `HermesDataAuditService.create_run()` | 完全匹配、有差异、单位不明、source_status 部分失败、match_rate 计算 |
| `POST /corrections:apply` | feature flag off、dry-run only、重复 idempotency_key、高风险阻断、低风险成功、事务失败回滚 |
| 回放脚本 | 三天连续执行、单天失败不中断下一天、输出一行摘要、match_rate 下降阻断 apply |

最低测试命令：

```powershell
python -m pytest backend/tests/test_hermes_mes_read_service.py -q
python -m pytest backend/tests/test_hermes_data_audit_service.py -q
python -m pytest backend/tests/test_hermes_data_audit_router.py -q
python -m pytest backend/tests/test_mapping_reconciliation_route.py -q
python -m pytest backend/tests/test_sqlserver_mes_adapter.py -q
python -m compileall backend/app/models/hermes_data_audit.py backend/app/services/hermes_mes_read_service.py backend/app/services/hermes_data_audit_service.py backend/app/routers/hermes_data_audit.py
git diff --check
```

### 19.5 性能和体积限制

- 所有 run 必须带 `business_date`，禁止无日期全表扫描。
- MES 每个 source 默认 `limit=5000`，最大 `limit=20000`。
- 单个 source 读取超时建议 20 秒，整次 run 超时建议 60 秒。
- audit run 表只保存摘要、差异、证据 hash 和必要 before/after，不保存大段原始文件全文。
- 原始行明细如必须保存，应截断并记录 `raw_payload_truncated=true`。
- 索引至少覆盖：`business_date`、`status`、`run_key`、`created_by_id`、`audit_run_id`、`idempotency_key`。
- 日志只打 run_id、source、status、耗时、数量、错误码；不打连接串、密码、token。

### 19.6 事务和迁移准则

- 写数据中枢时一批 correction action 使用同一个 SQLAlchemy transaction。
- 任意 action 失败时，本批次回滚，并把 action 写成 `failed` 或 `blocked`。
- Alembic migration 只做可回滚结构变更：建表、建索引、删表、删索引。
- 不在 migration 里访问 MES，不在 migration 里跑历史回放。
- FastAPI router 用现有 `Depends(get_current_user)` 和 `build_scope_summary()`，只允许 admin 进入真实 apply。

官方工程参考：

- SQLAlchemy Session transaction: https://docs.sqlalchemy.org/en/latest/orm/session_transaction.html
- FastAPI dependencies/security: https://fastapi.tiangolo.com/tutorial/dependencies/
- Alembic operations: https://alembic.sqlalchemy.org/en/latest/ops.html

### 19.7 并行实施策略

可以并行，但不要让多个分支同时改同一个核心 service。

| Lane | 可并行工作 | 依赖 | 合并顺序 |
|---|---|---|---|
| A | model + migration + model import | 无 | 第一 |
| B | `HermesMesReadService` + tests | 无 | 第二 |
| C | `HermesDataAuditService` + output skill helper + tests | A、B 的接口稳定 | 第三 |
| D | router + API tests | A、C | 第四 |
| E | backfill script + docs 命令 | C | 第五 |

如果只由一个 agent 实施，按 A -> B -> C -> D -> E 顺序做。

### 19.8 上线门禁

真实 apply 必须同时满足：

- `HERMES_DATA_AUDIT_APPLY_ENABLED=true`。
- 最近三天 dry-run 都完成。
- 三天都没有 silent source failure。
- 三天平均 `match_rate >= 0.85`。
- 当前 run 的 `match_rate` 没有低于上一轮。
- 所有待 apply action 都有 `idempotency_key`。
- 所有 action 都有 before、after、evidence、rollback_status。
- 没有 P0/P1 failure mode 未覆盖测试。
- 审计日志没有真实密码、token、连接串。

不满足任一条件时，API 必须返回 `decision_gate.can_apply=false` 和明确 reason。

### 19.9 数据源扩展补充：WMS 与钉钉聊天资料

2026-06-21 新增要求：Hermes 的原始数据来源不再只看 MES SQL Server、数据中枢和输出 skill。后续计划必须把 `wms.xintaily.com` 和钉钉聊天记录中的文件、文本纳入可审计来源。

小白版理解：Hermes 不能只问一个系统。它以后要能同时看生产系统、仓储系统、数据中枢、历史成品文件、以及现场人员在钉钉里发过的文字和文件。但每个来源都要标清楚“从哪里来、谁发的、什么时候发的、能不能信、能不能自动改”。

#### 19.9.1 新增来源边界

| 来源 | 系统身份 | 第一阶段权限 | Hermes 用途 | 禁止事项 |
|---|---|---|---|---|
| MES SQL Server | 外部生产系统 | 高权限只读 | 生产、工序、在制、包装入库候选 | 禁止写 MES，禁止任意 SQL |
| `wms.xintaily.com` | 外部 WMS 仓储系统 | 只读，账号和接口待确认 | 成品入库、出库、库存、库位、寄存、调拨、客户/合同仓储口径 | 禁止写 WMS，禁止把 WMS 当 MES |
| 数据中枢 | 本系统 | Hermes 高权限可写，受审计和 feature flag 控制 | 补齐缺失映射、低风险修正、保存审计 run/action | 禁止无审计写入 |
| `D:\输出skill` / 云端只读挂载 | 历史成品参考源 | 只读 | 对齐历史日报成品、验证 Hermes 输出是否贴近案例成品 | 禁止修改原文件 |
| 钉钉聊天文本 | 现场沟通证据源 | 只读采集授权群/授权人的消息 | 现场解释、人工确认、班组补充说明、异常原因 | 禁止全量无授权抓群，禁止把聊天口径直接当最终事实 |
| 钉钉聊天文件 | 现场文件证据源 | 只读下载授权消息附件 | 临时报表、截图、Excel、TXT、日报口径补充，进入 RAG 或审计证据 | 禁止把密钥文件入库，禁止提交到 Git |

#### 19.9.2 WMS 接入原则

- `wms.xintaily.com` 是独立外部 WMS 数据源，不要把它命名成 MES。
- 第一版只读采集，不做 WMS 写入。
- 新增 WMS adapter 时必须白名单 query key，例如：
  - `finished_inbound_records`
  - `finished_outbound_records`
  - `stock_balance_records`
  - `stock_transfer_records`
  - `customer_storage_records`
- WMS 每个 query 必须带业务日期窗口、limit、source_status、source_errors。
- WMS 错误只能记录脱敏摘要，不能输出 cookie、token、密码、连接串。
- WMS 字段进入 Hermes 审计时新增 `source_status.wms`，不能塞进 `source_status.mes`。
- WMS 值与 MES SQL Server 中已有 `WMS_InStockDetail/WMS_Stock` 候选口径冲突时，必须标记 `wms_conflict`，不能自动挑一个当真值。

#### 19.9.3 钉钉聊天文件和文本接入原则

现有代码已经有基础能力可复用：

- `backend/scripts/agent_cli.py` 已能记录钉钉消息到 `ChatInboxMessage`。
- `backend/scripts/agent_cli.py` 已有 `rag-ingest-file`，可以把授权文件入 RAG。
- 现有钉钉用户绑定、allowed/owner 用户校验、outbox/inbox 审计不能绕开。

新增能力应按下面方式收敛：

- 只采集授权群、授权用户、授权时间窗口内的消息。
- 每条聊天文本必须保存来源摘要：
  - `channel`
  - `group_id`
  - `message_id` 或 `trace_id`
  - `sender_external_id`
  - `sent_at`
  - `ingested_by`
- 附件必须先做安全检查：
  - 允许：`txt`、`md`、`csv`、`json`、`log`、`xls`、`xlsx`、常见图片格式。
  - 拒绝：可执行文件、脚本、密钥文件、超大文件。
  - 文件内容进入 RAG 或审计证据，不进入 Git。
- Hermes 使用钉钉资料时必须把它标为 `dingtalk_text` 或 `dingtalk_file`，不能伪装成 MES/WMS/数据中枢事实。
- 钉钉资料只能作为证据、解释和人工确认来源。要变成数据中枢事实，必须经过 Hermes audit run、差异解释、人工或规则门禁。

#### 19.9.4 后续实施 Lane

| Lane | 目标 | 主要文件 | 验证 |
|---|---|---|---|
| F | WMS 只读 adapter 和 Hermes source 聚合 | `backend/app/services/hermes_wms_read_service.py`、`backend/app/services/hermes_data_audit_service.py` | WMS 白名单、只读、source_status.wms、脱敏错误、WMS/MES 冲突标记 |
| G | 钉钉聊天文本/文件作为 Hermes 证据源 | `backend/scripts/agent_cli.py`、RAG service、Hermes audit service | 授权群/用户校验、附件安全检查、RAG 入库、dingtalk_text/file provenance |
| H | WMS + 钉钉资料参与三天回放 | backfill script、Hermes audit tests | 脚本输出增加 WMS/DING source health，不破坏一日一行 |

这些 Lane 不阻塞 A-E 的收口。A-E 仍然先完成 MES、数据中枢、输出 skill 三边核验；F/G/H 是下一轮数据源扩展。

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | clean | Optimized plan directly because interactive AskUserQuestion was unavailable; added safety gates, diagrams, error registry, observability, rollout and rollback gates |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | not_run | Not run |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | Final execution lock added; scope reduced to two services; output skill standalone service removed; test matrix, performance limits, transactions, parallel lanes and apply gates defined |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | clean | No UI scope, so no mockups; added operator output hierarchy, API/script state coverage, and future UI guardrails |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not_run | Not run |

- **UNRESOLVED:** 0 product/engineering blockers. Tooling note: full interactive AskUserQuestion review gates were not available in the current mode, so conservative defaults were applied directly into the plan.
- **VERDICT:** Final plan is ready for implementation. Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` for the build phase.
