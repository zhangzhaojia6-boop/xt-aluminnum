# Hermes Single-Ingress Fact Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让生产 NousResearch Hermes 成为唯一钉钉实时入口，并让钉钉、MES/WMS、扫码补录形成可持久化、可追 trace、最近三业务日可通过 compare-only 门禁的日报事实闭环。

**Architecture:** 保留现有 `hermes-gateway.service`、`/api/v1/dingtalk/agent-inbound`、`MultimodalEvidence`、`DailyFactBundle` 和 `/manage` 页面。先阻止非法指标和参考答案旁路，再让真实 Hermes Gateway 把所有授权范围事件送入证据入口，最后统一证据读取、每日落库、管理端 trace 和真实生产门禁。

**Tech Stack:** NousResearch Hermes Agent、Python 3.11、FastAPI、SQLAlchemy、PostgreSQL、DingTalk Stream SDK、Vue 3、Vitest、pytest、systemd、nginx、GitHub Actions、gstack browser。

---

## 实施边界

本计划跨两个 Git 仓库：

1. 当前仓库：`aluminum-bypass`，负责数据中枢、日报、管理端、部署和验收。
2. NousResearch Hermes 仓库：生产路径当前为 `/srv/hermes-cloud/runtime/.hermes/hermes-agent`，负责真正的钉钉 Stream 接收和 Hermes 推理。

两个仓库必须各自有提交号。禁止只在生产目录改文件而不提交。

## 文件结构

### aluminum-bypass

- Create: `backend/app/services/report/metric_contracts.py`：五个关键指标的单位、合法来源、容差和必要元数据。
- Create: `backend/tests/test_metric_contracts.py`：指标合同测试。
- Modify: `backend/app/services/report/mes_factory_production_fact.py`：移除跨窗口非法成品率。
- Modify: `backend/app/services/report/template_daily_fact_sources.py`：禁止成品入库替代总产量。
- Modify: `backend/app/services/report/output_skill_reconciliation.py`：逐字段容差。
- Modify: `backend/app/services/report/daily_report_fact_closure.py`：纯真实源、trace 和合同门禁。
- Modify: `backend/app/services/dingtalk_stream_gateway_service.py`：候选证据默认 `machine_only`。
- Modify: `backend/app/services/dingtalk_stream_event_service.py`：全应用授权范围事件规范化。
- Modify: `backend/app/routers/dingtalk.py`：统一幂等入口和未知事件留证。
- Create: `backend/app/services/hermes_dingtalk_evidence_service.py`：统一读取 `MultimodalEvidence`。
- Modify: `backend/app/services/hermes_root_owner_evidence_service.py`：复用统一证据读取器。
- Modify: `backend/app/services/hermes_data_audit_service.py`：复用统一证据读取器。
- Modify: `backend/app/services/report/daily_fact_bundle.py`：复用统一证据并附合同元数据。
- Create: `backend/app/tasks/daily_fact_closure.py`：调用现有事实包持久化能力的单次任务。
- Modify: `backend/app/core/scheduler.py`：调度已结束业务日的事实闭环。
- Modify: `backend/app/schemas/ai_assistant.py`：返回事实状态和 trace。
- Modify: `backend/app/services/report/daily_overview_builder.py`：把最近事实闭环表面并入现有 `/dashboard/daily-production`。
- Modify: `frontend/src/utils/manageDailyReportSurface.js`：标准化来源、状态和 trace。
- Modify: `frontend/src/views/manage/today/TodayPage.vue`：展示真实来源，不再固定猜测。
- Modify: `frontend/src/composables/useAlertsTimeline.js`：加入事实/Hermes/钉钉异常。
- Modify: `backend/app/services/hermes_20_question_acceptance.py`：真实值门禁。
- Create: `backend/app/routers/version.py`：暴露数据中枢与 Hermes 运行 SHA。
- Modify: `backend/app/main.py`：注册版本路由。
- Modify: `.github/workflows/production-sync-status.yml`：统一可回滚部署和运行 SHA 验证。
- Modify: `.github/workflows/configure-dingtalk-stream-prod.yml`：只配置真实 Hermes Gateway，不再把数据中枢 Stream 脚本当生产进程。

### NousResearch Hermes

- Create: `gateway/xintai_evidence_relay.py`：幂等发送钉钉原始事件到数据中枢。
- Create: `tests/gateway/test_xintai_evidence_relay.py`：转发、重试和脱敏测试。
- Modify: `gateway/platforms/dingtalk.py`：文本、文件、附件和未知事件先留证。
- Modify: `gateway/run.py`：删除固定关键词业务门槛，让 Hermes 语义决定工具调用。
- Create: `gateway/xintai_stream_health.py`：暴露 Stream 和 evidence relay 指标。
- Create: `tests/gateway/test_xintai_stream_health.py`：连接、成功、失败和最后事件时间测试。
- Modify: `SOUL.md`：只保留中文身份与事实边界，不定义研发身份。

## Task 1: 建立两个仓库的可回滚基线

**Files:**
- Inspect: `/srv/hermes-cloud/runtime/.hermes/hermes-agent`
- Create: `docs/deploy/hermes-runtime-baseline.md`

- [ ] **Step 1: 记录当前数据中枢基线**

Run:

```powershell
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

Expected: 当前功能工作树只包含计划施工产生的改动，起点可追溯到 `51bccce1`。

- [ ] **Step 2: 只读采集生产 Hermes Git 状态**

Run through the existing production SSH configuration:

```bash
cd /srv/hermes-cloud/runtime/.hermes/hermes-agent
git status --short --branch
git rev-parse HEAD
git remote -v
git diff --stat
find . -maxdepth 3 -type f \( -name '*.bak' -o -name '*.backup' \) -print
```

Expected: 输出当前 SHA、远端、脏改动和备份文件清单；不删除任何文件。

- [ ] **Step 3: 归档生产 Hermes 现状**

Run:

```bash
stamp=$(date +%Y%m%d-%H%M%S)
mkdir -p /var/backups/xintai-hermes/$stamp
git diff --binary > /var/backups/xintai-hermes/$stamp/working-tree.patch
git status --porcelain=v2 > /var/backups/xintai-hermes/$stamp/status.txt
git bundle create /var/backups/xintai-hermes/$stamp/repository.bundle --all
git bundle verify /var/backups/xintai-hermes/$stamp/repository.bundle
```

Expected: `git bundle verify` 成功，之后才允许整理生产 Hermes 仓库。

- [ ] **Step 4: 在 Hermes 仓库建立功能分支并提交现有鑫泰改动**

```bash
git switch -c feature/xintai-single-ingress-fact-closure
git add gateway SOUL.md pyproject.toml uv.lock package.json package-lock.json
git commit -m "chore: capture Xintai Hermes production baseline"
```

Expected: 业务修改进入提交；`.bak`、运行缓存和密钥不进入提交。

- [ ] **Step 5: 写基线文档并提交**

`docs/deploy/hermes-runtime-baseline.md` 只记录两个 SHA、服务名、仓库远端和备份目录，不记录密钥或聊天内容。

```powershell
git add docs/deploy/hermes-runtime-baseline.md
git commit -m "docs: record Hermes runtime baseline"
```

## Task 2: 先阻止非法日报数字

**Files:**
- Create: `backend/app/services/report/metric_contracts.py`
- Create: `backend/tests/test_metric_contracts.py`
- Modify: `backend/app/services/report/mes_factory_production_fact.py`
- Modify: `backend/app/services/report/template_daily_fact_sources.py`
- Test: `backend/tests/test_mes_factory_production_fact.py`
- Test: `backend/tests/test_template_daily_fact_sources.py`

- [ ] **Step 1: 写指标合同失败测试**

```python
from app.services.report.metric_contracts import contract_for


def test_daily_yield_requires_same_basis_inputs():
    contract = contract_for("daily_yield_rate")
    assert contract.unit == "%"
    assert contract.requires_same_business_window is True
    assert "mes_feeding_to_finished_inbound" not in contract.allowed_source_types


def test_total_output_rejects_finished_inbound_source():
    contract = contract_for("total_output_daily")
    assert "finished_inbound_output" not in contract.allowed_source_types
    assert "mes_stock_header_records" not in contract.allowed_source_types
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
python -m pytest backend/tests/test_metric_contracts.py -q
```

Expected: FAIL because `metric_contracts` does not exist.

- [ ] **Step 3: 实现最小指标合同**

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricContract:
    field: str
    unit: str
    tolerance: float
    allowed_source_types: frozenset[str]
    requires_same_business_window: bool = False


_CONTRACTS = {
    "total_output_daily": MetricContract(
        "total_output_daily", "吨", 20.0,
        frozenset({"dingtalk_confirmed", "mes_packaging_output", "mes_verified"}),
    ),
    "finished_inbound_daily": MetricContract(
        "finished_inbound_daily", "吨", 20.0,
        frozenset({"dingtalk_confirmed", "finished_inbound_output", "wms_direct", "mes_stock_header_records"}),
    ),
    "wip_total": MetricContract(
        "wip_total", "吨", 20.0,
        frozenset({"dingtalk_confirmed", "mes_wip_distribution", "mes_wip_total_snapshot"}),
    ),
    "total_electricity_kwh": MetricContract(
        "total_electricity_kwh", "kWh", 20.0,
        frozenset({"dingtalk_confirmed", "iot_energy", "owner_daily", "data_hub_manual"}),
    ),
    "daily_yield_rate": MetricContract(
        "daily_yield_rate", "%", 0.2,
        frozenset({"dingtalk_confirmed", "owner_daily", "quality_yield_daily", "computed_same_basis"}),
        requires_same_business_window=True,
    ),
}


def contract_for(field: str) -> MetricContract:
    return _CONTRACTS[field]


def tolerance_for(field: str) -> float:
    contract = _CONTRACTS.get(field)
    return contract.tolerance if contract else 0.0
```

- [ ] **Step 4: 写非法成品率和总产量替代回归测试**

```python
def test_factory_fact_does_not_compute_yield_from_inbound_and_feeding(db_session, target_date):
    fact = build_factory_production_fact(db_session, target_date=target_date)
    assert fact["daily_yield_rate"] is None
    assert fact["month_yield_rate"] is None
    assert fact["yield_rate_source"] == "unavailable_requires_same_basis"


def test_template_total_output_never_adopts_finished_inbound_when_packaging_differs():
    result = _official_template_total_output(
        db=None,
        target_date=date(2026, 7, 7),
        plant_output={
            "daily_output": 6.5,
            "monthly_output": 60.0,
            "finished_inbound_output": 53.24,
            "finished_inbound_monthly_output": 300.0,
            "finished_inbound_source": "mes_stock_header_records",
        },
    )
    assert result["daily"] == 6.5
    assert result["source_type"] == "mes_packaging_output"
```

- [ ] **Step 5: 实现止错改动**

在 `build_factory_production_fact()` 中返回：

```python
"daily_yield_rate": None,
"month_yield_rate": None,
"yield_rate_source": "unavailable_requires_same_basis",
```

把 `_official_template_total_output()` 收紧为只使用包装产量：

```python
source_type = "mes_packaging_output"
daily = plant_output.get("daily_output")
monthly = plant_output.get("monthly_output")
yesterday = plant_output.get("yesterday_output")
```

删除 `_should_use_finished_inbound_as_template_total_output()` 及其常量；保留成品入库作为独立字段。

- [ ] **Step 6: 运行测试并提交**

```powershell
python -m pytest backend/tests/test_metric_contracts.py backend/tests/test_mes_factory_production_fact.py backend/tests/test_template_daily_fact_sources.py -q
git add backend/app/services/report backend/tests/test_metric_contracts.py backend/tests/test_mes_factory_production_fact.py backend/tests/test_template_daily_fact_sources.py
git commit -m "fix: block invalid daily production facts"
```

Expected: selected tests PASS; production no longer has a code path that derives 819% from inbound/feeding.

## Task 3: 收紧 compare-only 和逐字段容差

**Files:**
- Modify: `backend/app/services/report/output_skill_reconciliation.py`
- Modify: `backend/app/services/report/daily_report_fact_closure.py`
- Test: `backend/tests/test_output_skill_reconciliation.py`
- Test: `backend/tests/test_daily_report_fact_closure.py`

- [ ] **Step 1: 写逐字段容差失败测试**

```python
def test_yield_rate_does_not_use_twenty_point_tolerance():
    result = reconcile_field_values(
        {"daily_yield_rate": 80.0},
        {"daily_yield_rate": 95.0},
    )
    difference = next(item for item in result["differences"] if item["field"] == "daily_yield_rate")
    assert difference["delta"] == 15.0
    assert difference["tolerance"] == 0.2


def test_unknown_numeric_field_is_strict_by_default():
    result = reconcile_field_values({"unknown_count": 10}, {"unknown_count": 11})
    assert result["field_match_rate"] == 0.0
```

- [ ] **Step 2: 实现字段容差选择**

```python
from collections.abc import Mapping

from app.services.report.metric_contracts import tolerance_for


def _field_tolerance(field: str, overrides: Mapping[str, float] | None) -> float:
    if overrides and field in overrides:
        return max(0.0, float(overrides[field]))
    return tolerance_for(field)


def reconcile_field_values(
    actual_fields: Mapping[str, Any],
    expected_fields: Mapping[str, Any],
    *,
    field_tolerances: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    differences = []
    matched = 0
    tolerance_matched = 0
    for field, expected_value in expected_fields.items():
        actual_value = actual_fields.get(field)
        tolerance = _field_tolerance(field, field_tolerances)
        delta = _numeric_delta(actual_value, expected_value)
        if _display(actual_value) == _display(expected_value):
            matched += 1
        elif delta is not None and delta <= tolerance:
            matched += 1
            tolerance_matched += 1
        else:
            differences.append({
                "field": field,
                "actual": actual_value,
                "expected": expected_value,
                "delta": _display(delta) if delta is not None else None,
                "tolerance": tolerance,
            })
    expected_count = len(expected_fields)
    return {
        "field_match_rate": round(matched / expected_count * 100, 2) if expected_count else 0.0,
        "matched_fields": matched,
        "expected_fields": expected_count,
        "differences": differences,
        "tolerance_matched_fields": tolerance_matched,
    }
```

`reconcile_rendered_daily_report()` 解析文本后调用 `reconcile_field_values()`，并把字符匹配结果合并进返回值。

- [ ] **Step 3: 写纯真实源闭环失败测试**

```python
def critical_bundle(*, source_type: str, trace_id: str | None) -> dict:
    facts = {}
    sources = {}
    for field in CRITICAL_DAILY_FACT_FIELDS:
        facts[field] = {"value": 1, "source_type": source_type, "trace_id": trace_id}
        sources[field] = {"source_type": source_type, "trace_id": trace_id}
    return {
        "facts": facts,
        "sources": sources,
        "trace_id": trace_id,
        "output_skill_alignment": {"differences": []},
        "missing": [],
    }


@pytest.mark.parametrize("source_type", [
    "official_daily_report",
    "datahub_final_daily_report",
    "daily_fact_bundle",
    "output_skill",
])
def test_critical_field_rejects_derived_or_reference_source(source_type):
    bundle = critical_bundle(source_type=source_type, trace_id="trace-1")
    closure = build_daily_report_fact_closure(bundle)
    assert closure["status"] == "blocked"


def test_critical_field_requires_nonempty_trace():
    bundle = critical_bundle(source_type="mes_packaging_output", trace_id=None)
    closure = build_daily_report_fact_closure(bundle)
    assert closure["status"] == "blocked"
    assert closure["critical_fields"][0]["status"] == "needs_evidence"
```

- [ ] **Step 4: 实现严格门禁**

从关键字段允许来源中移除：

```python
DERIVED_OR_REFERENCE_SOURCES = {
    "official_daily_report",
    "datahub_final_daily_report",
    "daily_fact_bundle",
    "historical_report",
    "output_skill",
}
```

在 `_field_status()` 中加入合同和 trace：

```python
if any(source in DERIVED_OR_REFERENCE_SOURCES for source in source_types):
    return "needs_evidence"
if not trace_id:
    return "needs_evidence"
```

调整函数签名，让 `_field_status()` 接收 `trace_id`，同一 trace 写入输出。

- [ ] **Step 5: 运行测试并提交**

```powershell
python -m pytest backend/tests/test_output_skill_reconciliation.py backend/tests/test_daily_report_fact_closure.py backend/tests/test_check_daily_report_output_skill_alignment_script.py -q
git add backend/app/services/report backend/tests
git commit -m "fix: enforce real-source daily report gate"
```

## Task 4: 让数据中枢入口“全收消息、默认候选”

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/dingtalk_stream_event_service.py`
- Modify: `backend/app/services/dingtalk_stream_gateway_service.py`
- Modify: `backend/app/routers/dingtalk.py`
- Test: `backend/tests/test_dingtalk_stream_event_service.py`
- Test: `backend/tests/test_dingtalk_stream_gateway_service.py`
- Test: `backend/tests/test_dingtalk_agent_inbound_route.py`

- [ ] **Step 1: 写全范围与默认候选测试**

```python
def text_event(text: str) -> NormalizedDingTalkEvent:
    return NormalizedDingTalkEvent(
        source="dingtalk_stream",
        channel="dingtalk_stream",
        group_id="cid-new",
        trace_id="msg-1",
        message_id="msg-1",
        sender_staff_id="user-1",
        sender_union_id=None,
        message_type="text",
        message_text=text,
        file_name=None,
        download_code=None,
        file_id=None,
        event_time=None,
        raw_payload={},
    )


def test_star_scope_accepts_any_conversation_id():
    event = text_event("任意内容")
    assert validate_authorized_group(event, {"*"}) == event


def test_stream_text_starts_as_machine_only(db_session):
    result = ingest_dingtalk_stream_event(db_session, text_event("产量大概六十吨"))
    row = db_session.get(MultimodalEvidence, result["evidence_id"])
    assert row.payload["confirmation_status"] == "machine_only"


def test_unknown_event_is_kept_as_metadata_evidence(client, inbound_headers):
    response = client.post(
        "/api/v1/dingtalk/agent-inbound",
        headers=inbound_headers,
        json={"trace_id": "evt-unknown-1", "message_type": "unknown", "raw_event": {"kind": "new_kind"}},
    )
    assert response.status_code == 200
    assert response.json()["evidence_status"] == "machine_only"
```

- [ ] **Step 2: 运行测试确认至少一个失败**

```powershell
python -m pytest backend/tests/test_dingtalk_stream_event_service.py backend/tests/test_dingtalk_stream_gateway_service.py backend/tests/test_dingtalk_agent_inbound_route.py -q
```

- [ ] **Step 3: 实现全范围和候选状态**

保留现有 `is_authorized_group()` 的星号规则，并确保 `app/config.py` 不再把 `*` 判成缺少授权范围：

```python
clean_allowed = {_clean_text(item) for item in allowed_group_ids if _clean_text(item)}
if ALL_GROUPS_MARKER in clean_allowed:
    return True
return _clean_text(group_id) in clean_allowed
```

所有 Stream 自动入站调用统一使用：

```python
confirmation_status="machine_only"
```

未知事件保存：

```python
payload = {
    "source": "dingtalk",
    "channel": channel,
    "trace_id": trace_id,
    "message_type": message_type or "unknown",
    "parse_status": "text_unavailable",
    "confirmation_status": "machine_only",
    "raw_event_meta": redact_event_metadata(source_payload),
}
```

只保留元数据，不把密钥、完整用户隐私字段或二进制内容写进日志。

- [ ] **Step 4: 将幂等查询改为数据库可过滤字段或有限窗口**

当前入口会扫描全部 payload。保持无迁移前提下，至少限制业务窗口和最近记录：

```python
rows = (
    db.query(MultimodalEvidence)
    .filter(MultimodalEvidence.payload.isnot(None))
    .order_by(MultimodalEvidence.id.desc())
    .limit(5000)
    .all()
)
```

以 `trace_id + channel + group_id` 幂等；文件额外使用 `file_hash`。

- [ ] **Step 5: 运行测试并提交**

```powershell
python -m pytest backend/tests/test_dingtalk_stream_event_service.py backend/tests/test_dingtalk_stream_gateway_service.py backend/tests/test_dingtalk_agent_inbound_route.py -q
git add backend/app/config.py backend/app/services/dingtalk_stream_event_service.py backend/app/services/dingtalk_stream_gateway_service.py backend/app/routers/dingtalk.py backend/tests
git commit -m "fix: retain DingTalk events as candidate evidence"
```

## Task 5: 改造真正运行的 NousResearch Hermes Gateway

**Files (Hermes repository):**
- Create: `gateway/xintai_evidence_relay.py`
- Create: `gateway/xintai_stream_health.py`
- Create: `tests/gateway/test_xintai_evidence_relay.py`
- Create: `tests/gateway/test_xintai_stream_health.py`
- Modify: `gateway/platforms/dingtalk.py`
- Modify: `gateway/run.py`
- Modify: `SOUL.md`

- [ ] **Step 1: 写转发器失败测试**

```python
@pytest.mark.asyncio
async def test_relay_posts_every_event_without_keyword_filter(httpx_mock):
    httpx_mock.add_response(
        url="https://datahub.example/api/v1/dingtalk/agent-inbound",
        method="POST",
        json={"accepted": True},
    )
    relay = XintaiEvidenceRelay(
        base_url="https://datahub.example",
        token="test-token",
        enabled=True,
    )
    result = await relay.submit({"trace_id": "evt-1", "text": "接着上条说"})
    assert result.accepted is True
    assert result.trace_id == "evt-1"


@pytest.mark.asyncio
async def test_relay_does_not_log_token(caplog, failing_httpx_mock):
    relay = XintaiEvidenceRelay("https://datahub.example", "secret-token", True)
    await relay.submit({"trace_id": "evt-2"})
    assert "secret-token" not in caplog.text
```

- [ ] **Step 2: 实现最小异步转发器**

```python
from dataclasses import dataclass
import asyncio
import httpx


@dataclass(frozen=True)
class RelayResult:
    accepted: bool
    trace_id: str
    error: str | None = None


class XintaiEvidenceRelay:
    def __init__(self, base_url: str, token: str, enabled: bool = True):
        self.url = base_url.rstrip("/") + "/api/v1/dingtalk/agent-inbound"
        self.token = token
        self.enabled = enabled

    async def submit(self, payload: dict) -> RelayResult:
        trace_id = str(payload.get("trace_id") or payload.get("message_id") or "")
        if not self.enabled:
            return RelayResult(False, trace_id, "relay_disabled")
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(
                        self.url,
                        headers={"X-DingTalk-Inbound-Token": self.token},
                        json=payload,
                    )
                response.raise_for_status()
                return RelayResult(True, trace_id)
            except (httpx.HTTPError, ValueError) as exc:
                if attempt == 2:
                    return RelayResult(False, trace_id, type(exc).__name__)
                await asyncio.sleep(0.25 * (2 ** attempt))
        return RelayResult(False, trace_id, "retry_exhausted")
```

- [ ] **Step 3: 实现可证明的 Stream 健康状态**

```python
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass
class XintaiStreamHealth:
    connected: bool = False
    last_event_at: str | None = None
    relay_success_count: int = 0
    relay_failure_count: int = 0
    last_error: str | None = None

    def record_event(self) -> None:
        self.last_event_at = datetime.now(timezone.utc).isoformat()

    def record_relay(self, result: RelayResult) -> None:
        if result.accepted:
            self.relay_success_count += 1
            self.last_error = None
        else:
            self.relay_failure_count += 1
            self.last_error = result.error

    def snapshot(self) -> dict:
        return asdict(self)
```

对应测试必须断言成功数、失败数、最后事件时间和最后错误都随事件变化。

- [ ] **Step 4: 在 DingTalk 适配器中先转发、后推理**

在 `_on_message` 或对应回调中构造不依赖业务关键词的 payload：

```python
payload = {
    "trace_id": event_id or message_id,
    "message_id": message_id,
    "channel": "dingtalk_stream",
    "group_id": conversation_id,
    "sender_id": sender_id,
    "event_time": event_time,
    "message_type": message_type,
    "text": text,
    "file_id": file_id,
    "file_name": file_name,
    "download_code": download_code,
    "raw_event": safe_raw_event(raw_event),
}
relay_result = await self.xintai_evidence_relay.submit(payload)
self.stream_health.record_relay(relay_result)
```

转发失败时继续让 Hermes 回答，但健康状态必须失败，不能记录为已留证。

- [ ] **Step 5: 删除 `gateway/run.py` 固定关键词门槛**

删除 `xt_factory_keywords` 的 `any(keyword in text ...)` 分支。保留工具本身，但工具是否调用由 Hermes 模型和工具描述决定：

```python
context.metadata["xintai_evidence_relay"] = relay_result.accepted
return await self.agent.handle_message(context)
```

不要把所有消息强制执行 `dingtalk-command`；那会把“宽松理解”变成“每句都查库”。

- [ ] **Step 6: 文件事件下载并转交现有入口**

使用钉钉 SDK 提供的 download code/media API 下载文件，发送以下之一：

```python
payload["file_content_base64"] = base64.b64encode(file_bytes).decode("ascii")
payload["file_hash"] = hashlib.sha256(file_bytes).hexdigest()
```

超过 `DINGTALK_FILE_TEXT_MAX_BYTES` 时只发送元数据和 `parse_status=file_too_large`，不截断后伪装成完整文件。

- [ ] **Step 7: 固定中文身份**

`SOUL.md` 必须包含：

```text
你是鑫泰铝业智能大脑。
你只用中文与业务人员交流。
你可以主动查证、调用工具、追问、推动补录和生成可执行动作。
你不能猜测生产数字；数字必须来自钉钉证据、MES/WMS 只读查询或数据中枢已确认事实。
```

删除研发工程师、软件公司、CEO 等旧身份描述。

- [ ] **Step 8: 运行 Hermes 测试并提交**

```bash
pytest tests/gateway/test_xintai_evidence_relay.py tests/gateway/test_xintai_stream_health.py -q
pytest tests/gateway -q
git add gateway tests/gateway SOUL.md
git commit -m "feat: relay all DingTalk events into Xintai facts"
```

## Task 6: 统一 Hermes、审计和日报的钉钉证据读取

**Files:**
- Create: `backend/app/services/hermes_dingtalk_evidence_service.py`
- Modify: `backend/app/services/hermes_root_owner_evidence_service.py`
- Modify: `backend/app/services/hermes_data_audit_service.py`
- Modify: `backend/app/services/report/daily_fact_bundle.py`
- Create: `backend/tests/test_hermes_dingtalk_evidence_service.py`

- [ ] **Step 1: 写统一查询失败测试**

```python
def seed_dingtalk_evidence(db, content_kind: str, text: str, status: str):
    payload = {
        "source": "dingtalk",
        "trace_id": f"trace-{content_kind}",
        "business_date": "2026-07-07",
        "parse_status": "text_captured",
        "confirmation_status": status,
        content_kind: text,
    }
    row = MultimodalEvidence(
        evidence_type="attachment" if content_kind != "message_text" else "text",
        recognized_text=text,
        confirmation_status=status,
        payload=payload,
    )
    db.add(row)
    db.commit()
    return row


def test_query_returns_text_file_and_attachment_in_business_window(db_session):
    seed_dingtalk_evidence(db_session, "message_text", "产量 60 吨", "machine_only")
    seed_dingtalk_evidence(db_session, "file_text", "日报 总产量 62 吨", "specialist_sampled")
    rows = query_dingtalk_evidence(db_session, business_date=date(2026, 7, 7))
    assert {row.content_kind for row in rows} == {"message_text", "file_text"}
    assert all(row.trace_id for row in rows)


def test_machine_only_is_visible_to_hermes_but_not_adoptable():
    row = DingTalkEvidenceItem(
        evidence_id=1,
        trace_id="trace-1",
        business_date=date(2026, 7, 7),
        event_time=None,
        group_id="cid-1",
        sender_id="user-1",
        content_kind="message_text",
        text="产量大概六十吨",
        parse_status="text_captured",
        confirmation_status="machine_only",
    )
    assert row.visible_to_hermes is True
    assert row.adoptable_as_fact is False
```

- [ ] **Step 2: 实现统一返回类型**

```python
@dataclass(frozen=True)
class DingTalkEvidenceItem:
    evidence_id: int
    trace_id: str
    business_date: date | None
    event_time: datetime | None
    group_id: str | None
    sender_id: str | None
    content_kind: str
    text: str
    parse_status: str
    confirmation_status: str

    @property
    def visible_to_hermes(self) -> bool:
        return bool(self.text or self.trace_id)

    @property
    def adoptable_as_fact(self) -> bool:
        return self.parse_status == "text_captured" and self.confirmation_status in {
            "specialist_sampled", "confirmed"
        }
```

查询只读取 `MultimodalEvidence` 中 `source=dingtalk` 的记录，并统一提取 `message_text`、`file_text`、`attachment_text`。

- [ ] **Step 3: 三条消费链改用统一服务**

- root owner：候选证据可用于理解和追问，只有 `adoptable_as_fact` 可作为数字结论。
- data audit：候选证据进入缺口分析，不自动修正数据。
- DailyFactBundle：只采用 `adoptable_as_fact`，候选证据写入 diagnostics。

- [ ] **Step 4: 运行测试并提交**

```powershell
python -m pytest backend/tests/test_hermes_dingtalk_evidence_service.py backend/tests/test_hermes_root_owner_evidence_service.py backend/tests/test_hermes_data_audit_service.py backend/tests/test_daily_fact_bundle_service.py -q
git add backend/app/services backend/tests
git commit -m "refactor: unify DingTalk evidence reads"
```

## Task 7: 将真实 MES 事实和每日持久化接入生产调度

**Files:**
- Create: `backend/app/tasks/daily_fact_closure.py`
- Modify: `backend/app/core/scheduler.py`
- Modify: `backend/app/services/report/daily_fact_bundle.py`
- Test: `backend/tests/test_scheduler.py`
- Create: `backend/tests/test_daily_fact_closure_task.py`

- [ ] **Step 1: 写每日持久化失败测试**

```python
def test_daily_fact_closure_task_persists_run_and_snapshot(db_session, monkeypatch):
    monkeypatch.setattr(task_module, "last_completed_production_business_date", lambda now=None: date(2026, 7, 7))
    result = run_daily_fact_closure(db_session, now=datetime(2026, 7, 8, 8, 5, tzinfo=SHANGHAI))
    assert result["business_date"] == "2026-07-07"
    assert db_session.query(DailyFactBundleRun).count() == 1
    assert db_session.query(DailyFactBundleSnapshot).count() == 1


def test_daily_fact_closure_task_is_idempotent(db_session):
    run_daily_fact_closure(db_session, target_date=date(2026, 7, 7))
    run_daily_fact_closure(db_session, target_date=date(2026, 7, 7))
    assert db_session.query(DailyFactBundleRun).count() == 1
```

- [ ] **Step 2: 实现单次任务**

```python
def run_daily_fact_closure(db: Session, *, target_date: date | None = None, now: datetime | None = None) -> dict:
    business_date = target_date or last_completed_production_business_date(now)
    trace_id = f"daily-fact-closure:{business_date.isoformat()}"
    bundle = build_daily_fact_bundle(
        db,
        business_date=business_date,
        trace_id=trace_id,
        persist_run=True,
        snapshot_reason="scheduled_daily_closure",
    )
    db.commit()
    return {
        "business_date": business_date.isoformat(),
        "trace_id": trace_id,
        "status": bundle["fact_closure"]["status"],
    }
```

- [ ] **Step 3: 在现有 scheduler 注册，不新建服务**

按现有 advisory lock 和任务包装模式注册每日 08:05 执行；调度失败写现有任务日志，不吞异常。

- [ ] **Step 4: 让 MES 直接来源带 trace 进入事实包**

每个直接 MES/WMS 字段写入：

```python
{
    "source_type": "mes_packaging_output",
    "source_ref": "sqlserver:MES_ProductProcessRecord",
    "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
    "unit": "吨",
    "trace_id": "mes:total_output_daily:2026-07-07",
    "metric_contract_version": "2026-07-11",
}
```

- [ ] **Step 5: 运行测试并提交**

```powershell
python -m pytest backend/tests/test_daily_fact_closure_task.py backend/tests/test_scheduler.py backend/tests/test_daily_fact_bundle_service.py -q
git add backend/app/tasks/daily_fact_closure.py backend/app/core/scheduler.py backend/app/services/report/daily_fact_bundle.py backend/tests
git commit -m "feat: persist daily fact closure on schedule"
```

## Task 8: 把真实来源、状态和 trace 接到现有管理端

**Files:**
- Modify: `backend/app/schemas/ai_assistant.py`
- Modify: `backend/app/services/report/daily_overview_builder.py`
- Modify: `frontend/src/utils/manageDailyReportSurface.js`
- Modify: `frontend/src/views/manage/today/TodayPage.vue`
- Modify: `frontend/src/composables/useAlertsTimeline.js`
- Test: `frontend/tests/manageDailyReportSurface.test.js`
- Test: `frontend/tests/manageTodayPage.test.js`
- Test: `frontend/tests/manageAlertsTimeline.test.js`

- [ ] **Step 1: 写前端标准化失败测试**

```javascript
test('fact closure surface keeps backend value unit time source status and trace', () => {
  const result = buildFactClosureSurface({
    status: 'pass',
    critical_fields: [{
      field: 'total_output_daily',
      value: 62,
      unit: '吨',
      source: 'mes_packaging_output',
      status: 'confirmed',
      business_window: '2026-07-07 07:50/2026-07-08 07:50',
      trace_id: 'mes:total_output_daily:2026-07-07',
    }],
  })
  assert.equal(result.criticalFields[0].traceId, 'mes:total_output_daily:2026-07-07')
  assert.equal(result.criticalFields[0].source, 'mes_packaging_output')
  assert.equal(result.criticalFields[0].businessWindow, '2026-07-07 07:50/2026-07-08 07:50')
  assert.equal(result.criticalFields[0].value, 62)
  assert.equal(result.criticalFields[0].unit, '吨')
})
```

- [ ] **Step 2: 后端返回统一事实表面**

每个关键字段返回：

```json
{
  "field": "total_output_daily",
  "value": 62.0,
  "unit": "吨",
  "status": "confirmed",
  "source": "mes_packaging_output",
  "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
  "trace_id": "mes:total_output_daily:2026-07-07"
}
```

不存在时返回 `status=missing`，不使用前端默认数字。

- [ ] **Step 3: TodayPage 使用后端真实标签**

移除固定来源文字和猜测来源。扩展现有 `buildFactClosureSurface()`，再把结果传给现有 `KpiBar` 和事实闭环区域：

```vue
<KpiBar :items="kpiItems" />
<button
  v-for="fact in factClosureSurface.criticalFields"
  :key="fact.key"
  type="button"
  @click="openTrace(fact.traceId)"
>
  <span>{{ fact.source }}</span>
  <time>{{ fact.businessWindow }}</time>
</button>
```

在 `<script setup>` 中使用现有 `/manage/alerts` 钻取，不新建 trace 页面：

```javascript
import { RouterLink, useRouter } from 'vue-router'

const router = useRouter()

function openTrace(traceId) {
  if (!traceId) return
  router.push({ path: '/manage/alerts', query: { trace_id: traceId } })
}
```

非法或缺失成品率显示 `--` 和状态，不显示 0% 或计算值。

- [ ] **Step 4: alerts 加入事实链异常**

把以下类型映射到现有时间线：

```javascript
const factAlerts = [
  ...payload.factConflicts,
  ...payload.factMissing,
  ...payload.hermesFailures,
  ...payload.dingtalkInboundFailures,
]
```

每条必须保留 `traceId` 和目标钻取地址。

- [ ] **Step 5: 运行测试并提交**

```powershell
npm --prefix frontend test -- --run frontend/tests/manageDailyReportSurface.test.js frontend/tests/manageTodayPage.test.js frontend/tests/manageAlertsTimeline.test.js
npm --prefix frontend run build
git add backend/app/schemas frontend/src frontend/tests
git commit -m "feat: show fact sources and traces in manage"
```

## Task 9: 让 Hermes 20 问验证真实能力

**Files:**
- Modify: `backend/app/services/hermes_20_question_acceptance.py`
- Modify: `backend/app/services/hermes_20_question_runner.py`
- Test: `backend/tests/test_hermes_20_question_real_acceptance.py`

- [ ] **Step 1: 写全 missing 不得通过的测试**

```python
def missing_answer(index: int) -> dict:
    return {
        "question_id": f"q-{index + 1}",
        "field": None,
        "status": "missing",
        "value": None,
        "source": None,
        "trace_id": None,
        "business_date": "2026-07-07",
        "action": "请责任人补充证据",
    }


def valid_answers() -> list[dict]:
    fields = [
        "total_output_daily",
        "finished_inbound_daily",
        "wip_total",
        "total_electricity_kwh",
        "daily_yield_rate",
    ]
    answers = []
    for index in range(20):
        field = fields[index] if index < len(fields) else None
        answers.append({
            "question_id": f"q-{index + 1}",
            "field": field,
            "status": "confirmed",
            "value": 1,
            "source": "mes_verified",
            "trace_id": f"trace-{index + 1}",
            "business_date": "2026-07-07",
            "answer": "已按真实来源核验。",
        })
    return answers


def test_twenty_missing_answers_fail_acceptance():
    result = evaluate_answers([missing_answer(index) for index in range(20)])
    assert result["passed"] is False
    assert result["confirmed_count"] == 0


def test_critical_questions_require_confirmed_value_source_and_trace():
    answers = valid_answers()
    answers[0]["trace_id"] = None
    result = evaluate_answers(answers)
    assert result["passed"] is False
    assert "trace" in result["failures"][0]["reason"]
```

- [ ] **Step 2: 实现状态门禁**

```python
CRITICAL_FIELDS = {
    "total_output_daily",
    "finished_inbound_daily",
    "wip_total",
    "total_electricity_kwh",
    "daily_yield_rate",
}


def answer_is_confirmed(answer: Mapping[str, Any]) -> bool:
    return (
        answer.get("status") == "confirmed"
        and answer.get("value") not in (None, "")
        and bool(answer.get("source"))
        and bool(answer.get("trace_id"))
        and bool(answer.get("business_date") or answer.get("business_window"))
    )
```

关键字段全部 confirmed；其他问题允许 conflict/missing，但必须给具体原因和 action。

- [ ] **Step 3: 增加语言和灵活性样例**

20 问至少包含：

```python
"昨天一共出了多少？"
"那入库呢？"
"电用了多少度，和群文件对得上吗"
"成品率咋这么高，帮我查下是不是口径错了"
"接着上一个问题，把证据编号给我"
```

断言回答为中文，且不依赖旧关键词列表。

- [ ] **Step 4: 运行测试并提交**

```powershell
python -m pytest backend/tests/test_hermes_20_question_real_acceptance.py backend/tests/test_hermes_20_question_runner.py -q
git add backend/app/services/hermes_20_question_acceptance.py backend/app/services/hermes_20_question_runner.py backend/tests
git commit -m "test: require real facts in Hermes acceptance"
```

## Task 10: 统一部署并证明运行 SHA

**Files:**
- Create: `backend/app/routers/version.py`
- Modify: `backend/app/main.py`
- Modify: `.github/workflows/production-sync-status.yml`
- Modify: `.github/workflows/configure-dingtalk-stream-prod.yml`
- Test: `backend/tests/test_health.py`

- [ ] **Step 1: 写版本接口失败测试**

```python
def test_versionz_returns_datahub_and_hermes_sha(client, monkeypatch):
    monkeypatch.setenv("BUILD_SHA", "datahub-sha")
    monkeypatch.setenv("HERMES_BUILD_SHA", "hermes-sha")
    response = client.get("/versionz")
    assert response.status_code == 200
    assert response.json() == {
        "datahub_sha": "datahub-sha",
        "hermes_sha": "hermes-sha",
    }
```

- [ ] **Step 2: 实现版本接口**

```python
@router.get("/versionz")
def versionz() -> dict[str, str | None]:
    return {
        "datahub_sha": os.getenv("BUILD_SHA"),
        "hermes_sha": os.getenv("HERMES_BUILD_SHA"),
    }
```

- [ ] **Step 3: 收口生产工作流**

`production-sync-status.yml` 的 deploy 模式固定顺序：

```text
确认目标 SHA
-> 数据库备份并 pg_restore -l 验证
-> git fetch + checkout 精确 SHA
-> Alembic upgrade
-> 前后端构建
-> 写 BUILD_SHA/HERMES_BUILD_SHA
-> 重启 aluminum-bypass 和 hermes-gateway
-> /readyz + /versionz
-> 真实钉钉入站 smoke
-> 失败回滚两个 SHA 和数据库（迁移不兼容时）
```

`configure-dingtalk-stream-prod.yml` 不再运行数据中枢独立 Stream 脚本的假健康检查，只验证真实 `hermes-gateway` 的连接指标和最后事件时间。

- [ ] **Step 4: 运行测试和 workflow 静态检查**

```powershell
python -m pytest backend/tests/test_health.py -q
python -c "import yaml; yaml.safe_load(open('.github/workflows/production-sync-status.yml', encoding='utf-8')); yaml.safe_load(open('.github/workflows/configure-dingtalk-stream-prod.yml', encoding='utf-8'))"
git add backend/app/routers/version.py backend/app/main.py backend/tests .github/workflows
git commit -m "ops: verify running datahub and Hermes versions"
```

## Task 11: 全量回归、生产验收和目录整理

**Files:**
- Modify only if failures require fixes from Tasks 2-10.
- Artifact output: GitHub Actions artifacts or `/var/lib/aluminum-bypass/acceptance`, not repository root.

- [ ] **Step 1: 本地质量门禁**

```powershell
python -m pytest backend/tests -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
git diff --check origin/main...HEAD
git status --short
```

Expected: all tests pass; no generated reports, secrets or caches tracked.

- [ ] **Step 2: 代码评审门禁**

使用 `superpowers:requesting-code-review` 和 gstack `/review` 检查：

- 没有第二个 Stream 进程；
- 没有参考答案反向填数；
- 没有候选钉钉数字自动升级；
- 没有 MES 写操作；
- 没有密钥进入 diff；
- 每个关键字段都有 trace 门禁。

- [ ] **Step 3: 部署精确 SHA**

部署后验证：

```text
local HEAD == origin branch SHA
production datahub repo HEAD == /versionz.datahub_sha
production Hermes repo HEAD == /versionz.hermes_sha
service start time > deployment time
```

- [ ] **Step 4: 真实钉钉 smoke**

在企业应用可收到的真实会话中发送：

1. 唯一文本：`验收-20260711-143000 昨日总产量待确认 62 吨`；
2. 一个真实 XLSX 或日报附件；
3. 一个不包含旧关键词的连续追问。

数据库只读验证：

```text
MultimodalEvidence 出现 message_text
MultimodalEvidence 出现 file_text 或 attachment_text
两条记录均有 group/conversation、sender、event time、trace
初始状态 machine_only
重复事件不重复写入
```

- [ ] **Step 5: 跑最近三个业务日事实闭环**

```powershell
gh workflow run daily-report-alignment-prod.yml -f confirm=daily-align -f days=3 -f reference_mode=compare
```

Expected:

- 三日均有 `DailyFactBundleRun` 和 snapshot；
- critical 5/5 confirmed，trace 非空；
- critical match rate 100%；
- overall field match rate >= 95%；
- reference adoption count = 0；
- 任一差异包含单位、容差、来源和业务窗口。

- [ ] **Step 6: 跑 Hermes 20 问**

Expected:

- 五个关键问题全部 confirmed；
- 其余问题不得靠空 `missing` 计通过；
- 全中文；
- 连续追问保持上下文；
- 无事实时明确缺口并给出补录动作。

- [ ] **Step 7: gstack 真实浏览器回归**

使用有效扫码链接验证：

1. `/entry` 扫码登录、填报、草稿和历史；
2. 车间管理扫码进入正确车间；
3. 管理员 `/manage/today` 来源、时间、状态、trace；
4. `/manage/alerts` 事实冲突和钉钉失败；
5. `/manage/ai-assistant` 中文回答和 trace；
6. 页面无控制台错误；
7. 不再出现大于 100% 的非法全厂成品率。

- [ ] **Step 8: 整理生产目录**

先把无主脚本和备份移动到按日期命名的归档目录，验证服务和 Git 状态后再决定删除：

```bash
stamp=$(date +%Y%m%d-%H%M%S)
mkdir -p /var/backups/aluminum-bypass/untracked-$stamp
git ls-files --others --exclude-standard -z | while IFS= read -r -d '' file; do
  mkdir -p "/var/backups/aluminum-bypass/untracked-$stamp/$(dirname "$file")"
  cp -a -- "$file" "/var/backups/aluminum-bypass/untracked-$stamp/$file"
done
```

逐个确认 `backend/shift_report_query.py`、`backend/xt_daily_morning_report.py`、`backend/xt_daily_report.py` 和日期版脚本没有被 systemd、cron 或工作流引用。确认后从生产仓库目录移出，不直接递归删除。

- [ ] **Step 9: 最终提交、合并和推送**

```powershell
git status --short
git log --oneline origin/main..HEAD
git push -u origin feature/hermes-single-ingress-fact-closure
```

创建 PR，等待 CI 和生产验收产物通过后再使用 `gstack:land-and-deploy` 合并。Hermes 仓库对应分支也必须先推送和记录最终 SHA。

## 计划自审

### Spec 覆盖

- Hermes 唯一入口：Task 5。
- 不设硬群边界但保留审计：Task 4、5。
- 宽松理解、严格事实：Task 4、5、6。
- MES/WMS 只读和事实 trace：Task 2、7。
- 日报事实包每日落库：Task 7。
- 五个关键字段和逐字段容差：Task 2、3。
- `/manage` 减法和 trace：Task 8。
- Hermes 20 问真实能力：Task 9。
- 双仓库运行 SHA 和部署治理：Task 1、10、11。
- 真实钉钉文件、三日 compare-only 和扫码浏览器验收：Task 11。

### Placeholder 扫描

计划中没有未填写步骤、未来占位项或未定义的笼统处理。动态生产值通过现有 SSH/GitHub 环境读取，不写死密钥和主机秘密。

### 类型一致性

- `trace_id` 在 Hermes relay、证据、事实包、AI schema 和前端统一为字符串。
- `confirmation_status` 使用 `machine_only`、`specialist_sampled`、`confirmed`。
- 事实状态使用 `confirmed`、`candidate`、`missing`、`conflict`、`needs_evidence`。
- 容差由 `metric_contracts.tolerance_for(field)` 统一提供。
