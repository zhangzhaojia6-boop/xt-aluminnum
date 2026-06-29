# Hermes Root Owner Production Evidence Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the real root_owner DingTalk private-chat loop where Hermes understands flexible natural language, prioritizes DingTalk group files/chat as the highest fact source, reads external readonly sources by domain, answers in one natural paragraph, and leaves trace/outbox/external-log evidence.

**Architecture:** Reuse the existing DingTalk inbound router, `ChatInboxMessage`, `AgentRun`, `AgentOutboxMessage`, `ExternalMessageLog`, `HermesDataAuditService`, and `HermesMesReadService`. Add small focused Hermes services for flexible root_owner message understanding, external readonly source registration, evidence priority selection, and private reply orchestration.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, existing DingTalk service/outbox, existing Hermes services, existing MES readonly adapter.

---

## Plain-Language Direction

This plan makes the software smaller and the agent stronger.

Software does less:

- No new dashboard.
- No new messaging system.
- No new database table for the first registry version.
- No second data hub.

Hermes does more:

- It accepts loose root_owner messages like `今天咋样`.
- It does not require exact keywords.
- It checks DingTalk group files and chat first.
- It treats MES as the production-domain readonly fact source.
- It writes every answer into existing trace and outbox records.

## Spec Source

Approved spec:

`docs/superpowers/specs/2026-06-27-hermes-root-owner-production-evidence-loop-design.md`

Important rules from the spec:

- DingTalk group files and group chat are the highest fact source.
- External readonly databases are fact sources inside their own business domains.
- Data hub projections, DailyFactBundle, and history are lower-priority evidence.
- root_owner real private chat is the acceptance entry.
- Message recognition must stay soft and forgiving.

## File Structure

Create:

- `backend/app/services/hermes_root_owner_message_service.py`  
  Flexible root_owner message understanding. This is the anti-hardcoding layer.

- `backend/tests/test_hermes_root_owner_message_service.py`  
  Tests for colloquial text, typos, omitted dates, follow-up messages, and clarification fallback.

- `backend/app/services/external_readonly_source_registry.py`  
  Config-based readonly source registry and health summary. First version includes MES and a future energy slot.

- `backend/tests/test_external_readonly_source_registry.py`  
  Tests for MES registration, domain priority, readonly flag, and energy placeholder health.

- `backend/app/services/hermes_root_owner_evidence_service.py`  
  Evidence planner. It orders DingTalk group content above external readonly databases and data hub snapshots.

- `backend/tests/test_hermes_root_owner_evidence_service.py`  
  Tests that DingTalk beats MES when they conflict, MES beats hub in production, and missing data is explicit.

- `backend/app/services/hermes_root_owner_reply_channel_service.py`  
  General root_owner personal DingTalk work-notice channel bootstrap. It avoids hardcoding a single person.

- `backend/tests/test_hermes_root_owner_reply_channel_service.py`  
  Tests that root_owner private reply channels are user-scoped, real-send capable, and idempotent.

- `backend/app/services/hermes_root_owner_production_orchestrator.py`  
  The private-chat turn orchestrator. It creates inbox/run trace, plans evidence, builds answer, queues outbox, and dispatches.

- `backend/tests/test_hermes_root_owner_production_orchestrator.py`  
  Tests for answer generation, conflict trace, best-effort estimates, missing evidence, outbox logging, and retry behavior.

- `backend/scripts/run_hermes_root_owner_private_smoke.py`  
  A small production smoke helper that posts a real inbound payload to the existing DingTalk inbound endpoint.

- `backend/tests/test_hermes_root_owner_private_smoke_script.py`  
  Tests that the smoke helper builds the correct request without printing secrets.

Modify:

- `backend/app/routers/dingtalk.py`  
  Route root_owner private messages into the new orchestrator and stop turning flexible parse failures into hard 400s.

- `backend/app/services/hermes_langchain_tools.py`  
  Narrow change: make `dingtalk_evidence` tool return DingTalk group evidence in priority order.

- `backend/app/hermes/fact_source_map.json`  
  Change priority source names so DingTalk group content is first and MES is above data hub projections in production-domain rows.

- `backend/app/services/hermes_fact_source_map_service.py`  
  Allow the new DingTalk group fact-source condition names while keeping validation strict.

- `backend/tests/test_hermes_fact_source_map_service.py`  
  Assert the source map uses the new priority model.

- `docs/software-minus-agent-plus-prd.md`  
  Sync the approved direction in plain language.

- `docs/agent-operating-guide.md`  
  Make the agent rule explicit: DingTalk group files/chat first, then external readonly source by domain.

- `docs/system-design-direction.md`  
  Clarify that data hub is a projection/cache/audit layer under higher fact sources.

- `docs/hermes/fact-source-map.md`  
  Regenerate from `backend/app/hermes/fact_source_map.json`.

Do not create:

- A new frontend page.
- A new dashboard route.
- A new messaging table.
- A second outbox.
- A new root-owner env var. Use existing `HERMES_OWNER_DINGTALK_USER_IDS`.

---

## Task 1: Flexible Root Owner Message Understanding

**Files:**
- Create: `backend/app/services/hermes_root_owner_message_service.py`
- Create: `backend/tests/test_hermes_root_owner_message_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_hermes_root_owner_message_service.py`:

```python
from datetime import date

from app.services.hermes_root_owner_message_service import understand_root_owner_message


def test_understands_colloquial_factory_overview_without_hard_keywords() -> None:
    plan = understand_root_owner_message(
        "今天咋样",
        default_business_date=date(2026, 6, 27),
    )

    assert plan.business_date == date(2026, 6, 27)
    assert plan.domain == "factory_overview"
    assert plan.intent == "overview"
    assert plan.needs_clarification is False
    assert plan.confidence >= 0.5
    assert "soft_default_today" in plan.recognition_reason


def test_tolerates_common_typos_for_production_question() -> None:
    plan = understand_root_owner_message(
        "今添产亮咋样",
        default_business_date=date(2026, 6, 27),
    )

    assert plan.domain == "production"
    assert plan.intent == "production_summary"
    assert "total_output_daily" in plan.metric_keys
    assert plan.needs_clarification is False
    assert "typo_normalized" in plan.recognition_reason


def test_understands_energy_question_without_exact_sentence() -> None:
    plan = understand_root_owner_message(
        "电这块今天高不高",
        default_business_date=date(2026, 6, 27),
    )

    assert plan.domain == "energy"
    assert plan.intent == "energy_summary"
    assert "total_electricity_kwh" in plan.metric_keys
    assert plan.needs_clarification is False


def test_uses_previous_domain_for_short_follow_up() -> None:
    plan = understand_root_owner_message(
        "那为啥对不上",
        default_business_date=date(2026, 6, 27),
        previous_domain="production",
    )

    assert plan.domain == "production"
    assert plan.intent == "conflict_explanation"
    assert plan.needs_clarification is False
    assert "context_follow_up" in plan.recognition_reason


def test_asks_short_clarification_when_message_is_not_business_question() -> None:
    plan = understand_root_owner_message(
        "给我讲个轻松笑话",
        default_business_date=date(2026, 6, 27),
    )

    assert plan.domain == "general"
    assert plan.needs_clarification is True
    assert plan.clarification_question == "你想看生产、库存、能耗还是异常？"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_root_owner_message_service.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'app.services.hermes_root_owner_message_service'
```

- [ ] **Step 3: Create the message service**

Create `backend/app/services/hermes_root_owner_message_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
import re

from app.core.business_time import resolve_production_business_date


@dataclass(frozen=True, slots=True)
class RootOwnerMessagePlan:
    raw_text: str
    normalized_text: str
    business_date: date
    domain: str
    intent: str
    metric_keys: tuple[str, ...]
    confidence: float
    needs_clarification: bool
    clarification_question: str | None
    recognition_reason: str


_TYPO_REPLACEMENTS = {
    "今添": "今天",
    "今田": "今天",
    "产亮": "产量",
    "电号": "电耗",
    "入哭": "入库",
}

_DOMAIN_TERMS = {
    "production": ("产量", "生产", "入库", "投料", "在制", "余合同", "库存", "日报"),
    "energy": ("能耗", "电耗", "用电", "电这块", "用气", "气耗", "吨电耗", "电"),
    "anomaly": ("异常", "对不上", "为什么", "为啥", "不一致", "差异", "缺", "少"),
}

_DOMAIN_INTENT = {
    "production": ("production_summary", ("total_output_daily", "finished_inbound_daily", "wip_total")),
    "energy": ("energy_summary", ("total_electricity_kwh", "total_gas_m3", "electricity_per_ton")),
    "anomaly": ("anomaly_summary", ("anomaly_explanation_daily",)),
    "factory_overview": (
        "overview",
        ("total_output_daily", "finished_inbound_daily", "total_electricity_kwh", "anomaly_explanation_daily"),
    ),
}


def understand_root_owner_message(
    text: str,
    *,
    default_business_date: date | None = None,
    previous_domain: str | None = None,
) -> RootOwnerMessagePlan:
    raw_text = str(text or "").strip()
    business_date = default_business_date or resolve_production_business_date()
    normalized, typo_changed = _normalize_text(raw_text)
    if not normalized:
        return RootOwnerMessagePlan(
            raw_text=raw_text,
            normalized_text=normalized,
            business_date=business_date,
            domain="general",
            intent="clarify",
            metric_keys=(),
            confidence=0.0,
            needs_clarification=True,
            clarification_question="你想看生产、库存、能耗还是异常？",
            recognition_reason="empty_message",
        )

    if _looks_like_follow_up(normalized) and previous_domain in {"production", "energy", "anomaly"}:
        intent = "conflict_explanation" if _has_any(normalized, ("对不上", "为啥", "为什么", "差异")) else "follow_up"
        metric_keys = _DOMAIN_INTENT.get(previous_domain, _DOMAIN_INTENT["factory_overview"])[1]
        return RootOwnerMessagePlan(
            raw_text=raw_text,
            normalized_text=normalized,
            business_date=business_date,
            domain=previous_domain,
            intent=intent,
            metric_keys=metric_keys,
            confidence=0.68,
            needs_clarification=False,
            clarification_question=None,
            recognition_reason=_join_reasons("context_follow_up", "soft_semantic_match", typo_changed),
        )

    scored = _score_domains(normalized)
    domain, score = max(scored.items(), key=lambda item: item[1])
    if score > 0:
        intent, metric_keys = _DOMAIN_INTENT[domain]
        if domain == "anomaly" and _has_any(normalized, ("对不上", "不一致", "差异", "为啥", "为什么")):
            intent = "conflict_explanation"
        return RootOwnerMessagePlan(
            raw_text=raw_text,
            normalized_text=normalized,
            business_date=business_date,
            domain=domain,
            intent=intent,
            metric_keys=metric_keys,
            confidence=min(0.95, 0.45 + score * 0.12),
            needs_clarification=False,
            clarification_question=None,
            recognition_reason=_join_reasons("soft_semantic_match", domain, typo_changed),
        )

    if _has_any(normalized, ("今天", "咋样", "怎么样", "现在", "今日")):
        intent, metric_keys = _DOMAIN_INTENT["factory_overview"]
        return RootOwnerMessagePlan(
            raw_text=raw_text,
            normalized_text=normalized,
            business_date=business_date,
            domain="factory_overview",
            intent=intent,
            metric_keys=metric_keys,
            confidence=0.52,
            needs_clarification=False,
            clarification_question=None,
            recognition_reason=_join_reasons("soft_default_today", typo_changed),
        )

    return RootOwnerMessagePlan(
        raw_text=raw_text,
        normalized_text=normalized,
        business_date=business_date,
        domain="general",
        intent="clarify",
        metric_keys=(),
        confidence=0.2,
        needs_clarification=True,
        clarification_question="你想看生产、库存、能耗还是异常？",
        recognition_reason=_join_reasons("business_domain_unclear", typo_changed),
    )


def _normalize_text(text: str) -> tuple[str, bool]:
    value = str(text or "").strip()
    typo_changed = False
    for wrong, right in _TYPO_REPLACEMENTS.items():
        if wrong in value:
            value = value.replace(wrong, right)
            typo_changed = True
    value = re.sub(r"\s+", "", value)
    return value, typo_changed


def _score_domains(text: str) -> dict[str, int]:
    scores = {domain: 0 for domain in _DOMAIN_TERMS}
    for domain, terms in _DOMAIN_TERMS.items():
        for term in terms:
            if term in text:
                scores[domain] += 3
            elif _fuzzy_contains(text, term):
                scores[domain] += 1
    return scores


def _fuzzy_contains(text: str, term: str) -> bool:
    if len(term) < 2 or len(text) < 2:
        return False
    width = len(term)
    for index in range(0, max(1, len(text) - width + 1)):
        chunk = text[index : index + width]
        if SequenceMatcher(None, chunk, term).ratio() >= 0.67:
            return True
    return False


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _looks_like_follow_up(text: str) -> bool:
    return _has_any(text, ("那", "这个", "那个", "刚才", "为啥", "为什么", "对不上"))


def _join_reasons(*items: object) -> str:
    parts: list[str] = []
    for item in items:
        if item is True:
            parts.append("typo_normalized")
        elif isinstance(item, str) and item:
            parts.append(item)
    return ",".join(dict.fromkeys(parts))
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_root_owner_message_service.py -q
```

Expected:

```text
5 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/hermes_root_owner_message_service.py backend/tests/test_hermes_root_owner_message_service.py
git commit -m "feat: add flexible root owner message understanding"
```

---

## Task 2: External Readonly Source Registry

**Files:**
- Create: `backend/app/services/external_readonly_source_registry.py`
- Create: `backend/tests/test_external_readonly_source_registry.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_external_readonly_source_registry.py`:

```python
from app.services.external_readonly_source_registry import (
    ExternalReadonlyHealth,
    build_external_readonly_sources,
    health_check_sources,
)


def test_registry_declares_mes_as_production_domain_readonly_fact_source() -> None:
    sources = build_external_readonly_sources()
    mes = next(item for item in sources if item.source_key == "mes_readonly")

    assert mes.domain == "production"
    assert mes.readonly is True
    assert mes.priority == 20
    assert mes.fact_role == "domain_fact_source"


def test_registry_keeps_future_energy_slot_without_claiming_it_is_connected() -> None:
    sources = build_external_readonly_sources(energy_dsn="")
    energy = next(item for item in sources if item.source_key == "energy_readonly")

    assert energy.domain == "energy"
    assert energy.readonly is True
    assert energy.enabled is False
    assert energy.fact_role == "future_domain_fact_source"


def test_health_check_reports_mes_probe_result_without_writing_data() -> None:
    sources = build_external_readonly_sources(energy_dsn="")

    def probe(source):
        if source.source_key == "mes_readonly":
            return ExternalReadonlyHealth(
                source_key=source.source_key,
                domain=source.domain,
                status="ok",
                readonly=True,
                last_success_at="2026-06-27T10:00:00+08:00",
                failure_reason=None,
            )
        return None

    result = health_check_sources(sources, probe=probe)

    assert result["mes_readonly"]["status"] == "ok"
    assert result["mes_readonly"]["readonly"] is True
    assert result["energy_readonly"]["status"] == "disabled"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
python -m pytest tests/test_external_readonly_source_registry.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'app.services.external_readonly_source_registry'
```

- [ ] **Step 3: Create registry service**

Create `backend/app/services/external_readonly_source_registry.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from typing import Callable


@dataclass(frozen=True, slots=True)
class ExternalReadonlySource:
    source_key: str
    domain: str
    priority: int
    readonly: bool
    enabled: bool
    fact_role: str
    health_query_key: str | None = None


@dataclass(frozen=True, slots=True)
class ExternalReadonlyHealth:
    source_key: str
    domain: str
    status: str
    readonly: bool
    last_success_at: str | None
    failure_reason: str | None


HealthProbe = Callable[[ExternalReadonlySource], ExternalReadonlyHealth | None]


def build_external_readonly_sources(*, energy_dsn: str | None = None) -> tuple[ExternalReadonlySource, ...]:
    energy_value = os.getenv("ENERGY_READONLY_DSN", "") if energy_dsn is None else energy_dsn
    return (
        ExternalReadonlySource(
            source_key="mes_readonly",
            domain="production",
            priority=20,
            readonly=True,
            enabled=True,
            fact_role="domain_fact_source",
            health_query_key="workshop_process_records",
        ),
        ExternalReadonlySource(
            source_key="energy_readonly",
            domain="energy",
            priority=20,
            readonly=True,
            enabled=bool(str(energy_value or "").strip()),
            fact_role="future_domain_fact_source",
            health_query_key=None,
        ),
    )


def health_check_sources(
    sources: tuple[ExternalReadonlySource, ...] | list[ExternalReadonlySource],
    *,
    probe: HealthProbe,
) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for source in sources:
        if not source.enabled:
            result[source.source_key] = asdict(
                ExternalReadonlyHealth(
                    source_key=source.source_key,
                    domain=source.domain,
                    status="disabled",
                    readonly=source.readonly,
                    last_success_at=None,
                    failure_reason="source_not_configured",
                )
            )
            continue
        checked = probe(source)
        if checked is None:
            checked = ExternalReadonlyHealth(
                source_key=source.source_key,
                domain=source.domain,
                status="unknown",
                readonly=source.readonly,
                last_success_at=None,
                failure_reason="probe_not_registered",
            )
        result[source.source_key] = asdict(checked)
    return result
```

- [ ] **Step 4: Run registry tests**

Run:

```bash
cd backend
python -m pytest tests/test_external_readonly_source_registry.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/external_readonly_source_registry.py backend/tests/test_external_readonly_source_registry.py
git commit -m "feat: add external readonly source registry"
```

---

## Task 3: Evidence Priority Planner

**Files:**
- Create: `backend/app/services/hermes_root_owner_evidence_service.py`
- Create: `backend/tests/test_hermes_root_owner_evidence_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_hermes_root_owner_evidence_service.py`:

```python
from datetime import date

from app.services.hermes_root_owner_evidence_service import (
    EvidenceCandidate,
    choose_primary_evidence,
    collect_root_owner_evidence,
)
from app.services.hermes_root_owner_message_service import RootOwnerMessagePlan


def _message_plan(domain: str = "production") -> RootOwnerMessagePlan:
    return RootOwnerMessagePlan(
        raw_text="今天产量咋样",
        normalized_text="今天产量咋样",
        business_date=date(2026, 6, 27),
        domain=domain,
        intent="production_summary",
        metric_keys=("total_output_daily",),
        confidence=0.8,
        needs_clarification=False,
        clarification_question=None,
        recognition_reason="test",
    )


def test_dingtalk_group_content_wins_over_mes_when_conflicting() -> None:
    candidates = [
        EvidenceCandidate(
            source_key="mes_readonly",
            source_type="external_readonly",
            domain="production",
            priority=20,
            status="ok",
            value={"total_output_daily": 100.0},
            summary="MES 只读库显示 100 吨",
            trace_ref={"query_key": "workshop_process_records"},
        ),
        EvidenceCandidate(
            source_key="dingtalk_group_chat",
            source_type="dingtalk_group_content",
            domain="production",
            priority=10,
            status="ok",
            value={"total_output_daily": 118.0},
            summary="负责人群里确认 118 吨",
            trace_ref={"trace_id": "trace-ding-001"},
        ),
    ]

    decision = choose_primary_evidence(candidates, domain="production")

    assert decision.primary.source_key == "dingtalk_group_chat"
    assert decision.primary.value["total_output_daily"] == 118.0
    assert decision.conflicts[0]["lower_source"] == "mes_readonly"
    assert decision.conflicts[0]["chosen_source"] == "dingtalk_group_chat"


def test_mes_wins_over_data_hub_projection_in_production_domain() -> None:
    candidates = [
        EvidenceCandidate(
            source_key="data_hub_projection",
            source_type="data_hub",
            domain="production",
            priority=40,
            status="ok",
            value={"total_output_daily": 99.0},
            summary="数据中枢投影 99 吨",
            trace_ref={},
        ),
        EvidenceCandidate(
            source_key="mes_readonly",
            source_type="external_readonly",
            domain="production",
            priority=20,
            status="ok",
            value={"total_output_daily": 100.0},
            summary="MES 只读库 100 吨",
            trace_ref={},
        ),
    ]

    decision = choose_primary_evidence(candidates, domain="production")

    assert decision.primary.source_key == "mes_readonly"
    assert decision.primary.value["total_output_daily"] == 100.0


def test_collect_records_missing_sources_explicitly() -> None:
    decision = collect_root_owner_evidence(
        db=None,
        message_plan=_message_plan(),
        trace_id="trace-evidence-missing",
        dingtalk_reader=lambda **_kwargs: [],
        mes_reader=None,
        hub_reader=lambda **_kwargs: None,
    )

    assert decision.primary is None
    assert decision.missing_sources == ["dingtalk_group_content", "mes_readonly", "data_hub_projection"]
    assert decision.trace["trace_id"] == "trace-evidence-missing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_root_owner_evidence_service.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'app.services.hermes_root_owner_evidence_service'
```

- [ ] **Step 3: Create evidence planner**

Create `backend/app/services/hermes_root_owner_evidence_service.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping

from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.services.hermes_data_audit_service import HermesDataAuditService
from app.services.hermes_mes_read_service import HermesMesReadService
from app.services.report import template_daily_report


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    source_key: str
    source_type: str
    domain: str
    priority: int
    status: str
    value: Mapping[str, Any] | list[Any] | None
    summary: str
    trace_ref: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class EvidenceDecision:
    primary: EvidenceCandidate | None
    candidates: tuple[EvidenceCandidate, ...]
    conflicts: tuple[dict[str, Any], ...]
    missing_sources: list[str]
    trace: dict[str, Any]


DINGTALK_PRIORITY = 10
EXTERNAL_READONLY_PRIORITY = 20
DATA_HUB_PRIORITY = 40

_PRODUCTION_QUERY_KEYS = {
    "total_output_daily": "workshop_process_records",
    "workshop_output_daily": "workshop_process_records",
    "finished_inbound_daily": "finished_inbound_records",
    "daily_input_weight": "material_records",
    "wip_total": "wip_totals",
    "remaining_contract_weight": "stock_records",
}


DingTalkReader = Callable[..., list[EvidenceCandidate]]
HubReader = Callable[..., Mapping[str, Any] | None]


def collect_root_owner_evidence(
    db: Session | None,
    *,
    message_plan: Any,
    trace_id: str,
    dingtalk_reader: DingTalkReader | None = None,
    mes_reader: HermesMesReadService | None = None,
    hub_reader: HubReader | None = None,
) -> EvidenceDecision:
    candidates: list[EvidenceCandidate] = []
    missing_sources: list[str] = []

    dingtalk_candidates = (
        dingtalk_reader(db=db, business_date=message_plan.business_date, trace_id=trace_id)
        if dingtalk_reader is not None
        else _read_dingtalk_candidates(db, business_date=message_plan.business_date)
    )
    if dingtalk_candidates:
        candidates.extend(dingtalk_candidates)
    else:
        missing_sources.append("dingtalk_group_content")

    if message_plan.domain in {"production", "factory_overview", "anomaly"}:
        if mes_reader is None:
            missing_sources.append("mes_readonly")
        else:
            mes_candidate = _read_mes_candidate(mes_reader, message_plan=message_plan)
            if mes_candidate is None:
                missing_sources.append("mes_readonly")
            else:
                candidates.append(mes_candidate)

    hub_payload = hub_reader(db=db, business_date=message_plan.business_date) if hub_reader else _read_hub_payload(db, message_plan.business_date)
    if hub_payload:
        candidates.append(
            EvidenceCandidate(
                source_key="data_hub_projection",
                source_type="data_hub",
                domain=message_plan.domain,
                priority=DATA_HUB_PRIORITY,
                status=str(hub_payload.get("status") or "ok"),
                value=filter_sensitive_mapping(dict(hub_payload)),
                summary="数据中枢投影已读取",
                trace_ref={"source": "template_daily_report"},
            )
        )
    else:
        missing_sources.append("data_hub_projection")

    decision = choose_primary_evidence(candidates, domain=message_plan.domain)
    return EvidenceDecision(
        primary=decision.primary,
        candidates=decision.candidates,
        conflicts=decision.conflicts,
        missing_sources=missing_sources,
        trace={
            "trace_id": trace_id,
            "business_date": message_plan.business_date.isoformat(),
            "domain": message_plan.domain,
            "intent": message_plan.intent,
            "source_order": [candidate.source_key for candidate in decision.candidates],
            "missing_sources": missing_sources,
            "conflicts": list(decision.conflicts),
        },
    )


def choose_primary_evidence(candidates: list[EvidenceCandidate], *, domain: str) -> EvidenceDecision:
    usable = [candidate for candidate in candidates if candidate.status in {"ok", "confirmed", "candidate"}]
    sorted_candidates = tuple(sorted(usable, key=lambda item: item.priority))
    primary = sorted_candidates[0] if sorted_candidates else None
    conflicts: list[dict[str, Any]] = []
    if primary is not None:
        for candidate in sorted_candidates[1:]:
            if _candidate_value_differs(primary.value, candidate.value):
                conflicts.append(
                    {
                        "domain": domain,
                        "chosen_source": primary.source_key,
                        "lower_source": candidate.source_key,
                        "chosen_priority": primary.priority,
                        "lower_priority": candidate.priority,
                        "reason": "higher_priority_fact_source",
                    }
                )
    return EvidenceDecision(
        primary=primary,
        candidates=sorted_candidates,
        conflicts=tuple(conflicts),
        missing_sources=[],
        trace={"domain": domain},
    )


def _read_dingtalk_candidates(db: Session | None, *, business_date) -> list[EvidenceCandidate]:
    if db is None:
        return []
    payload = HermesDataAuditService(db)._read_dingtalk_evidence(business_date=business_date)
    result: list[EvidenceCandidate] = []
    for source_name in ("dingtalk_file", "dingtalk_text"):
        source_payload = payload.get(source_name) or {}
        items = source_payload.get("items") or []
        if not items:
            continue
        source_key = "dingtalk_group_file" if source_name == "dingtalk_file" else "dingtalk_group_chat"
        result.append(
            EvidenceCandidate(
                source_key=source_key,
                source_type="dingtalk_group_content",
                domain="factory",
                priority=DINGTALK_PRIORITY,
                status=str(source_payload.get("status") or "ok"),
                value=filter_sensitive_mapping({"items": items}),
                summary=f"{source_key} 命中 {len(items)} 条",
                trace_ref={"source": source_name, "count": len(items)},
            )
        )
    return result


def _read_mes_candidate(mes_reader: HermesMesReadService, *, message_plan: Any) -> EvidenceCandidate | None:
    query_keys = sorted(
        {
            _PRODUCTION_QUERY_KEYS[metric_key]
            for metric_key in message_plan.metric_keys
            if metric_key in _PRODUCTION_QUERY_KEYS
        }
    )
    if not query_keys:
        query_keys = ["workshop_process_records", "finished_inbound_records"]
    payload = mes_reader.read_sources(business_date=message_plan.business_date, query_keys=query_keys)
    status = str((payload.get("source_status") or {}).get("mes") or "empty")
    if status not in {"ok", "partial_failed"}:
        return None
    return EvidenceCandidate(
        source_key="mes_readonly",
        source_type="external_readonly",
        domain="production",
        priority=EXTERNAL_READONLY_PRIORITY,
        status="ok" if status == "ok" else "candidate",
        value=filter_sensitive_mapping(payload.get("records") or {}),
        summary="MES 只读库已读取",
        trace_ref={
            "query_keys": query_keys,
            "source_status": filter_sensitive_mapping(payload.get("source_status") or {}),
            "source_errors": redact_secret_text(str(payload.get("source_errors") or {})),
        },
    )


def _read_hub_payload(db: Session | None, business_date) -> Mapping[str, Any] | None:
    if db is None:
        return None
    try:
        return template_daily_report.build_template_daily_report_payload(db, target_date=business_date)
    except Exception:
        return None


def _candidate_value_differs(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    return asdict(left) != asdict(right) if hasattr(left, "__dataclass_fields__") and hasattr(right, "__dataclass_fields__") else left != right
```

- [ ] **Step 4: Run evidence tests**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_root_owner_evidence_service.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/hermes_root_owner_evidence_service.py backend/tests/test_hermes_root_owner_evidence_service.py
git commit -m "feat: prioritize root owner evidence sources"
```

---

## Task 4: General Root Owner Private Reply Channel

**Files:**
- Create: `backend/app/services/hermes_root_owner_reply_channel_service.py`
- Create: `backend/tests/test_hermes_root_owner_reply_channel_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_hermes_root_owner_reply_channel_service.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.agent_communication import AgentChannelBinding, AgentProfile, CommunicationChannel
from app.services.hermes_root_owner_reply_channel_service import ensure_root_owner_private_reply_channel


def _db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def test_ensure_root_owner_private_reply_channel_is_user_scoped_and_real_send_capable() -> None:
    db = _db_session()
    try:
        outcome = ensure_root_owner_private_reply_channel(
            db,
            agent_code="factory_dispatch",
            dingtalk_user_id="dt-root-001",
            owner_name="root_owner",
        )

        assert outcome["channel_type"] == "dingtalk_work_notice"
        assert outcome["channel_key"] == "dt-root-001"
        assert outcome["dry_run"] is False

        agent = db.query(AgentProfile).filter(AgentProfile.code == "factory_dispatch").one()
        channel = db.query(CommunicationChannel).filter(CommunicationChannel.channel_key == "dt-root-001").one()
        binding = db.query(AgentChannelBinding).one()

        assert agent.is_active is True
        assert channel.target_type == "user"
        assert channel.target_key == "dt-root-001"
        assert channel.dry_run is False
        assert channel.metadata_payload["root_owner_reply_channel"] is True
        assert binding.agent_profile_id == agent.id
        assert binding.channel_id == channel.id
    finally:
        db.close()


def test_ensure_root_owner_private_reply_channel_is_idempotent() -> None:
    db = _db_session()
    try:
        first = ensure_root_owner_private_reply_channel(
            db,
            agent_code="factory_dispatch",
            dingtalk_user_id="dt-root-001",
            owner_name="root_owner",
        )
        second = ensure_root_owner_private_reply_channel(
            db,
            agent_code="factory_dispatch",
            dingtalk_user_id="dt-root-001",
            owner_name="root_owner",
        )

        assert first == second
        assert db.query(AgentProfile).count() == 1
        assert db.query(CommunicationChannel).count() == 1
        assert db.query(AgentChannelBinding).count() == 1
    finally:
        db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_root_owner_reply_channel_service.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'app.services.hermes_root_owner_reply_channel_service'
```

- [ ] **Step 3: Create reply channel service**

Create `backend/app/services/hermes_root_owner_reply_channel_service.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services import agent_communication_service


def ensure_root_owner_private_reply_channel(
    db: Session,
    *,
    agent_code: str,
    dingtalk_user_id: str,
    owner_name: str,
) -> dict:
    clean_agent_code = str(agent_code or "").strip() or "factory_dispatch"
    clean_user_id = str(dingtalk_user_id or "").strip()
    clean_owner_name = str(owner_name or "").strip() or "root_owner"
    if not clean_user_id:
        raise ValueError("root_owner_dingtalk_user_id_required")

    agent_communication_service.register_agent(
        db,
        code=clean_agent_code,
        name="Hermes root_owner 私聊 Agent",
        agent_type="factory_brain",
        scope_type="user",
        config_payload={
            "owner_name": clean_owner_name,
            "owner_dingtalk_user_id": clean_user_id,
            "capabilities": ["root_owner_private_reply", "evidence_trace", "readonly_source_query"],
            "requires_outbox": True,
        },
    )
    channel = agent_communication_service.register_channel(
        db,
        channel_type="dingtalk_work_notice",
        channel_key=clean_user_id,
        name=f"{clean_owner_name} root_owner 私聊回复通道",
        target_type="user",
        target_key=clean_user_id,
        dry_run=False,
        metadata_payload={
            "root_owner_reply_channel": True,
            "owner_name": clean_owner_name,
            "owner_dingtalk_user_id": clean_user_id,
            "managed_by": "ensure_root_owner_private_reply_channel",
        },
    )
    agent_communication_service.bind_agent_to_channel(
        db,
        agent_code=clean_agent_code,
        channel_key=channel.channel_key,
        channel_type=channel.channel_type,
        min_severity="info",
    )
    return {
        "agent_code": clean_agent_code,
        "channel_type": channel.channel_type,
        "channel_key": channel.channel_key,
        "target_key": channel.target_key,
        "dry_run": channel.dry_run,
    }
```

- [ ] **Step 4: Run reply channel tests**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_root_owner_reply_channel_service.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/hermes_root_owner_reply_channel_service.py backend/tests/test_hermes_root_owner_reply_channel_service.py
git commit -m "feat: add root owner private reply channel"
```

---

## Task 5: Root Owner Production Turn Orchestrator

**Files:**
- Create: `backend/app/services/hermes_root_owner_production_orchestrator.py`
- Create: `backend/tests/test_hermes_root_owner_production_orchestrator.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_hermes_root_owner_production_orchestrator.py`:

```python
from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.agent_communication import AgentRun, ChatInboxMessage, ExternalMessageLog
from app.models.system import User
from app.services.hermes_root_owner_evidence_service import EvidenceCandidate, EvidenceDecision
from app.services.hermes_root_owner_production_orchestrator import run_root_owner_production_turn


def _db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def _root_owner() -> User:
    return User(
        id=1,
        username="root-owner",
        password_hash="x",
        name="root_owner",
        role="admin",
        is_active=True,
        dingtalk_user_id="dt-root-001",
        dingtalk_union_id="union-root-001",
    )


def test_turn_answers_with_dingtalk_primary_and_records_trace(monkeypatch) -> None:
    db = _db_session()
    db.add(_root_owner())
    db.commit()

    primary = EvidenceCandidate(
        source_key="dingtalk_group_chat",
        source_type="dingtalk_group_content",
        domain="production",
        priority=10,
        status="ok",
        value={"total_output_daily": 118.0},
        summary="负责人群里确认 118 吨",
        trace_ref={"trace_id": "trace-ding-001"},
    )
    decision = EvidenceDecision(
        primary=primary,
        candidates=(primary,),
        conflicts=(),
        missing_sources=[],
        trace={"source_order": ["dingtalk_group_chat"]},
    )
    monkeypatch.setattr(
        "app.services.hermes_root_owner_production_orchestrator.collect_root_owner_evidence",
        lambda *_args, **_kwargs: decision,
    )
    sent = []

    def fake_dispatch(_db, outbox_message_id, *, sender=None):
        sent.append(outbox_message_id)
        message = _db.get(__import__("app.models.agent_communication", fromlist=["AgentOutboxMessage"]).AgentOutboxMessage, outbox_message_id)
        message.status = "sent"
        _db.add(
            ExternalMessageLog(
                outbox_message_id=outbox_message_id,
                channel_type="dingtalk_work_notice",
                channel_key="dt-root-001",
                status="sent",
                detail="sent",
            )
        )
        _db.commit()
        return SimpleNamespace(status="sent", detail="sent", outbox_message_id=outbox_message_id)

    monkeypatch.setattr(
        "app.services.hermes_root_owner_production_orchestrator.agent_communication_service.dispatch_outbox_message",
        fake_dispatch,
    )

    try:
        result = run_root_owner_production_turn(
            db,
            text="今天产量咋样",
            current_user=db.get(User, 1),
            sender_external_id="dt-root-001",
            trace_id="trace-root-turn-001",
            source_payload={"source": "test"},
            default_business_date=date(2026, 6, 27),
        )

        assert result.status == "answered"
        assert "负责人群里确认 118 吨" in result.answer
        assert "钉钉" in result.answer
        assert result.dispatch_status == "sent"
        assert sent == [result.outbox_message_id]

        inbox = db.query(ChatInboxMessage).one()
        run = db.query(AgentRun).one()
        assert inbox.channel == "dingtalk_private"
        assert run.trace_id == "trace-root-turn-001"
        assert run.result_payload["evidence"]["primary_source"] == "dingtalk_group_chat"
        assert run.result_payload["recognition"]["domain"] == "production"
    finally:
        db.close()


def test_turn_asks_short_clarification_for_unclear_message(monkeypatch) -> None:
    db = _db_session()
    db.add(_root_owner())
    db.commit()
    monkeypatch.setattr(
        "app.services.hermes_root_owner_production_orchestrator.agent_communication_service.dispatch_outbox_message",
        lambda _db, outbox_message_id, *, sender=None: SimpleNamespace(status="sent", detail="sent", outbox_message_id=outbox_message_id),
    )

    try:
        result = run_root_owner_production_turn(
            db,
            text="给我讲个轻松笑话",
            current_user=db.get(User, 1),
            sender_external_id="dt-root-001",
            trace_id="trace-root-turn-clarify",
            source_payload={},
            default_business_date=date(2026, 6, 27),
        )

        assert result.status == "clarifying"
        assert result.answer == "你想看生产、库存、能耗还是异常？"
        run = db.query(AgentRun).one()
        assert run.result_payload["recognition"]["needs_clarification"] is True
    finally:
        db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_root_owner_production_orchestrator.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'app.services.hermes_root_owner_production_orchestrator'
```

- [ ] **Step 3: Create orchestrator**

Create `backend/app/services/hermes_root_owner_production_orchestrator.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping
from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.system import User
from app.services import agent_communication_service
from app.services.hermes_mes_read_service import HermesMesReadService
from app.services.hermes_root_owner_evidence_service import EvidenceDecision, collect_root_owner_evidence
from app.services.hermes_root_owner_message_service import RootOwnerMessagePlan, understand_root_owner_message
from app.services.hermes_root_owner_reply_channel_service import ensure_root_owner_private_reply_channel


@dataclass(frozen=True, slots=True)
class RootOwnerProductionTurnResult:
    trace_id: str
    status: str
    answer: str
    chat_inbox_id: int
    agent_run_id: int
    outbox_message_id: int
    dispatch_status: str
    dispatch_detail: str


def should_route_root_owner_production_turn(text: str, *, default_business_date: date | None = None) -> bool:
    plan = understand_root_owner_message(text, default_business_date=default_business_date)
    return plan.domain != "general" or plan.needs_clarification


def run_root_owner_production_turn(
    db: Session,
    *,
    text: str,
    current_user: User,
    sender_external_id: str | None,
    trace_id: str | None,
    source_payload: dict[str, Any] | None,
    default_business_date: date | None = None,
    mes_reader: HermesMesReadService | None = None,
) -> RootOwnerProductionTurnResult:
    clean_trace_id = str(trace_id or "").strip() or uuid4().hex
    clean_text = str(text or "").strip()
    sender_id = str(sender_external_id or getattr(current_user, "dingtalk_user_id", "") or "").strip()
    plan = understand_root_owner_message(clean_text, default_business_date=default_business_date)

    inbox = ChatInboxMessage(
        channel="dingtalk_private",
        group_id=None,
        sender_external_id=sender_id or None,
        text=clean_text,
        agent_code="factory_dispatch",
        trace_id=clean_trace_id,
        source_payload=filter_sensitive_mapping(
            {
                **(source_payload or {}),
                "source": "dingtalk_inbound",
                "root_owner_private_loop": True,
                "recognition_reason": plan.recognition_reason,
            }
        ),
    )
    db.add(inbox)
    db.flush()

    if plan.needs_clarification:
        decision = EvidenceDecision(primary=None, candidates=(), conflicts=(), missing_sources=[], trace={})
        answer = plan.clarification_question or "你想看生产、库存、能耗还是异常？"
        status = "clarifying"
    else:
        decision = collect_root_owner_evidence(
            db,
            message_plan=plan,
            trace_id=clean_trace_id,
            mes_reader=mes_reader,
        )
        answer = _build_natural_answer(plan=plan, decision=decision)
        status = "answered"

    run = AgentRun(
        trace_id=clean_trace_id,
        agent_code="factory_dispatch",
        chat_inbox_id=inbox.id,
        status=status,
        status_color=_status_color(decision),
        answer=answer,
        rag_citation_count=0,
        result_payload={
            "recognition": _message_plan_payload(plan),
            "evidence": _evidence_payload(decision),
            "source_payload": filter_sensitive_mapping(source_payload or {}),
        },
    )
    db.add(run)
    db.flush()

    channel = ensure_root_owner_private_reply_channel(
        db,
        agent_code="factory_dispatch",
        dingtalk_user_id=sender_id,
        owner_name=str(getattr(current_user, "name", None) or "root_owner"),
    )
    message = agent_communication_service.queue_bound_message(
        db,
        agent_code="factory_dispatch",
        channel_key=channel["channel_key"],
        channel_type=channel["channel_type"],
        title="Hermes root_owner 私聊回复",
        content=answer,
        business_date=plan.business_date,
        source_summary=(decision.primary.source_key if decision.primary else "clarification"),
        trace_id=clean_trace_id,
        payload={
            "chat_inbox_id": inbox.id,
            "agent_run_id": run.id,
            "recognition": _message_plan_payload(plan),
            "evidence": _evidence_payload(decision),
        },
        dedupe_key=f"root-owner-private:{clean_trace_id}",
    )
    dispatch = agent_communication_service.dispatch_outbox_message(db, message.id)
    run.result_payload = {
        **(run.result_payload or {}),
        "outbox_message_id": message.id,
        "dispatch_status": dispatch.status,
        "dispatch_detail": dispatch.detail,
    }
    db.flush()

    return RootOwnerProductionTurnResult(
        trace_id=clean_trace_id,
        status=status,
        answer=answer,
        chat_inbox_id=inbox.id,
        agent_run_id=run.id,
        outbox_message_id=message.id,
        dispatch_status=dispatch.status,
        dispatch_detail=dispatch.detail,
    )


def _build_natural_answer(*, plan: RootOwnerMessagePlan, decision: EvidenceDecision) -> str:
    if decision.primary is None:
        missing = "、".join(decision.missing_sources) or "事实源"
        return f"{plan.business_date.isoformat()} 这条问题我没有查到可用事实，缺少 {missing}；我已记录 trace，建议先补齐对应来源。"
    source_label = _source_label(decision.primary.source_key)
    conflict_text = "；来源有冲突，我已按最高优先级来源采用当前口径" if decision.conflicts else ""
    return (
        f"{plan.business_date.isoformat()} 我按{source_label}回答：{decision.primary.summary}"
        f"{conflict_text}；trace_id 会记录本次采用来源、未采用来源和缺失来源。"
    )


def _source_label(source_key: str) -> str:
    labels = {
        "dingtalk_group_chat": "钉钉群聊天内容",
        "dingtalk_group_file": "钉钉群文件",
        "mes_readonly": "MES 只读库",
        "data_hub_projection": "数据中枢投影",
    }
    return labels.get(source_key, source_key)


def _status_color(decision: EvidenceDecision) -> str:
    if decision.primary is None:
        return "yellow"
    if decision.conflicts:
        return "orange"
    return "green"


def _message_plan_payload(plan: RootOwnerMessagePlan) -> dict[str, Any]:
    return {
        "raw_text": plan.raw_text,
        "normalized_text": plan.normalized_text,
        "business_date": plan.business_date.isoformat(),
        "domain": plan.domain,
        "intent": plan.intent,
        "metric_keys": list(plan.metric_keys),
        "confidence": plan.confidence,
        "needs_clarification": plan.needs_clarification,
        "clarification_question": plan.clarification_question,
        "recognition_reason": plan.recognition_reason,
    }


def _evidence_payload(decision: EvidenceDecision) -> dict[str, Any]:
    return {
        "primary_source": decision.primary.source_key if decision.primary else None,
        "candidate_sources": [candidate.source_key for candidate in decision.candidates],
        "conflicts": list(decision.conflicts),
        "missing_sources": list(decision.missing_sources),
        "trace": filter_sensitive_mapping(decision.trace),
    }
```

- [ ] **Step 4: Run orchestrator tests**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_root_owner_production_orchestrator.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/hermes_root_owner_production_orchestrator.py backend/tests/test_hermes_root_owner_production_orchestrator.py
git commit -m "feat: orchestrate root owner production replies"
```

---

## Task 6: Route Root Owner Private Messages Through Hermes Production Loop

**Files:**
- Modify: `backend/app/routers/dingtalk.py`
- Modify: `backend/tests/test_dingtalk_agent_inbound_route.py`

- [ ] **Step 1: Add failing route tests**

Append to `backend/tests/test_dingtalk_agent_inbound_route.py`:

```python
def test_dingtalk_agent_inbound_root_owner_private_uses_production_loop_for_soft_message(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=88,
            username="root-owner-soft",
            password_hash="x",
            name="root_owner",
            role="admin",
            is_active=True,
            dingtalk_user_id="dt-root-soft-001",
            dingtalk_union_id="union-root-soft-001",
        )
    )
    db.commit()
    seen = {}

    def fake_turn(_db, **kwargs):
        seen.update(kwargs)
        return type(
            "FakeRootOwnerTurn",
            (),
            {
                "trace_id": kwargs["trace_id"],
                "status": "answered",
                "answer": "今天整体正常，已按钉钉事实源回答。",
                "chat_inbox_id": 301,
                "agent_run_id": 401,
                "outbox_message_id": 501,
                "dispatch_status": "sent",
                "dispatch_detail": "sent",
            },
        )()

    monkeypatch.setattr("app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN", "inbound-test", raising=False)
    monkeypatch.setenv("HERMES_OWNER_DINGTALK_USER_IDS", "dt-root-soft-001")
    monkeypatch.setattr(dingtalk_router, "run_root_owner_production_turn", fake_turn)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/dingtalk/agent-inbound",
            headers={"x-dingtalk-inbound-token": "inbound-test"},
            json={
                "senderStaffId": "dt-root-soft-001",
                "senderUnionId": "union-root-soft-001",
                "text": {"content": "今天咋样"},
                "agentCode": "factory_dispatch",
                "traceId": "trace-root-soft-route-001",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "answered"
        assert payload["answer"] == "今天整体正常，已按钉钉事实源回答。"
        assert payload["outbox_message_id"] == 501
        assert payload["dispatch_status"] == "sent"
        assert seen["text"] == "今天咋样"
        assert seen["sender_external_id"] == "dt-root-soft-001"
        assert seen["trace_id"] == "trace-root-soft-route-001"
    finally:
        _restore_db_override(previous_overrides, db)


def test_dingtalk_agent_inbound_day1_parse_error_does_not_hard_fail_for_root_owner_private(monkeypatch) -> None:
    db, previous_overrides = _install_db_override()
    db.add(
        User(
            id=89,
            username="root-owner-invalid-date",
            password_hash="x",
            name="root_owner",
            role="admin",
            is_active=True,
            dingtalk_user_id="dt-root-invalid-date-001",
            dingtalk_union_id="union-root-invalid-date-001",
        )
    )
    db.commit()
    monkeypatch.setattr("app.routers.dingtalk.settings.DINGTALK_INBOUND_TOKEN", "inbound-test", raising=False)
    monkeypatch.setenv("HERMES_OWNER_DINGTALK_USER_IDS", "dt-root-invalid-date-001")
    monkeypatch.setattr(
        dingtalk_router,
        "run_root_owner_production_turn",
        lambda _db, **kwargs: type(
            "FakeRootOwnerTurn",
            (),
            {
                "trace_id": kwargs["trace_id"],
                "status": "clarifying",
                "answer": "你想看哪一天的日报或生产情况？",
                "chat_inbox_id": 302,
                "agent_run_id": 402,
                "outbox_message_id": 502,
                "dispatch_status": "sent",
                "dispatch_detail": "sent",
            },
        )(),
    )

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/dingtalk/agent-inbound",
            headers={"x-dingtalk-inbound-token": "inbound-test"},
            json={
                "senderStaffId": "dt-root-invalid-date-001",
                "senderUnionId": "union-root-invalid-date-001",
                "text": {"content": "生成 13月99日正式日报"},
                "agentCode": "factory_dispatch",
                "traceId": "trace-root-invalid-date-route-001",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "clarifying"
        assert response.json()["answer"] == "你想看哪一天的日报或生产情况？"
    finally:
        _restore_db_override(previous_overrides, db)
```

- [ ] **Step 2: Run the two route tests to verify they fail**

Run:

```bash
cd backend
python -m pytest tests/test_dingtalk_agent_inbound_route.py::test_dingtalk_agent_inbound_root_owner_private_uses_production_loop_for_soft_message tests/test_dingtalk_agent_inbound_route.py::test_dingtalk_agent_inbound_day1_parse_error_does_not_hard_fail_for_root_owner_private -q
```

Expected:

```text
FAILED
```

The first test fails because the route still falls through to the old handler.  
The second test fails because invalid Day1 date parsing still becomes a hard 400.

- [ ] **Step 3: Modify imports**

In `backend/app/routers/dingtalk.py`, add:

```python
from app.services.hermes_root_owner_production_orchestrator import (
    run_root_owner_production_turn,
    should_route_root_owner_production_turn,
)
```

- [ ] **Step 4: Keep Day1 parse errors soft for root_owner private messages**

Replace the current Day1 parse block:

```python
    try:
        day1_command = None
        if not _is_legacy_slash_daily_report_command(text):
            day1_command = parse_day1_command(text, default_year=datetime.now().year)
    except Day1CommandParseError as exc:
        raise HTTPException(status_code=400, detail=exc.code) from exc
```

with:

```python
    day1_parse_error: Day1CommandParseError | None = None
    try:
        day1_command = None
        if not _is_legacy_slash_daily_report_command(text):
            day1_command = parse_day1_command(text, default_year=datetime.now().year)
    except Day1CommandParseError as exc:
        day1_parse_error = exc
        day1_command = None
```

- [ ] **Step 5: Route root_owner private messages after evidence recording and before old factory-brain routing**

In `backend/app/routers/dingtalk.py`, insert this block after the existing Day1 `if day1_command is not None:` block and before `factory_brain_intent = _get_factory_brain_route_intent(text)`:

```python
    root_owner_decision = classify_day1_actor(
        user,
        sender_user_id=sender_external_id,
        sender_union_id=_clean_text(_first_payload_value(payload, 'senderUnionId', 'unionId')),
        channel=channel,
        group_id=group_id,
    )
    if (
        channel == 'dingtalk_private'
        and root_owner_decision.is_root_owner
        and (
            should_route_root_owner_production_turn(text)
            or day1_parse_error is not None
        )
    ):
        try:
            result = run_root_owner_production_turn(
                db,
                text=text,
                current_user=user,
                sender_external_id=sender_external_id or None,
                trace_id=trace_id or None,
                source_payload={
                    **source_payload,
                    **({'day1_parse_error': day1_parse_error.code} if day1_parse_error is not None else {}),
                },
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        return {
            'errcode': 0,
            'errmsg': 'ok',
            'trace_id': result.trace_id,
            'agent_code': 'factory_dispatch',
            'status': result.status,
            'answer': result.answer,
            'messages': [result.answer] if result.answer else [],
            'chat_inbox_id': result.chat_inbox_id,
            'agent_run_id': result.agent_run_id,
            'report_id': None,
            'outbox_message_id': result.outbox_message_id,
            'dispatch_status': result.dispatch_status,
            'dispatch_detail': result.dispatch_detail,
        }
```

- [ ] **Step 6: Run route tests**

Run:

```bash
cd backend
python -m pytest tests/test_dingtalk_agent_inbound_route.py::test_dingtalk_agent_inbound_root_owner_private_uses_production_loop_for_soft_message tests/test_dingtalk_agent_inbound_route.py::test_dingtalk_agent_inbound_day1_parse_error_does_not_hard_fail_for_root_owner_private -q
```

Expected:

```text
2 passed
```

- [ ] **Step 7: Run existing inbound route regression tests**

Run:

```bash
cd backend
python -m pytest tests/test_dingtalk_agent_inbound_route.py tests/test_dingtalk_factory_brain_inbound.py -q
```

Expected:

```text
passed
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/dingtalk.py backend/tests/test_dingtalk_agent_inbound_route.py
git commit -m "feat: route root owner private messages to Hermes"
```

---

## Task 7: Make DingTalk Evidence Tool Priority-Aware

**Files:**
- Modify: `backend/app/services/hermes_langchain_tools.py`
- Modify: `backend/tests/test_hermes_langchain_tools.py`

- [ ] **Step 1: Add failing tool test**

Append to `backend/tests/test_hermes_langchain_tools.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, ChatInboxMessage, MultimodalEvidence
from app.services.hermes_langchain_tools import build_production_tool_adapters


def test_dingtalk_evidence_tool_returns_group_content_priority_first() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine, tables=[ChatInboxMessage.__table__, MultimodalEvidence.__table__])
    db = Session(engine)
    try:
        db.add(
            ChatInboxMessage(
                channel="dingtalk_group",
                group_id="group-001",
                sender_external_id="dt-leader",
                text="负责人确认今天产量 118 吨",
                agent_code="factory_dispatch",
                trace_id="trace-dingtalk-chat",
                source_payload={"source": "dingtalk"},
            )
        )
        db.add(
            MultimodalEvidence(
                evidence_type="file",
                recognized_text="群文件确认今天产量 118 吨",
                confirmation_status="confirmed",
                payload={"source": "dingtalk", "channel": "dingtalk_group"},
            )
        )
        db.commit()

        tool = build_production_tool_adapters(db).dingtalk_evidence
        payload = tool(limit=10)

        assert payload["status"] == "ok"
        assert payload["source"] == "dingtalk_group_content"
        assert payload["facts"][0]["source_key"] in {"dingtalk_group_file", "dingtalk_group_chat"}
        assert payload["facts"][0]["priority"] == 10
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_langchain_tools.py::test_dingtalk_evidence_tool_returns_group_content_priority_first -q
```

Expected:

```text
FAILED
```

The current tool returns plain `dingtalk_evidence` rows without the new priority source model.

- [ ] **Step 3: Modify imports**

In `backend/app/services/hermes_langchain_tools.py`, change:

```python
from app.models.agent_communication import MultimodalEvidence
```

to:

```python
from app.models.agent_communication import ChatInboxMessage, MultimodalEvidence
```

- [ ] **Step 4: Replace `_dingtalk_evidence_tool`**

Replace the existing `_dingtalk_evidence_tool` function with:

```python
def _dingtalk_evidence_tool(*, db: Session, **kwargs: object) -> dict[str, object]:
    try:
        limit = max(1, min(int(kwargs.get('limit') or 20), 100))
        file_rows = (
            db.query(MultimodalEvidence)
            .filter(MultimodalEvidence.evidence_type.in_(('file', 'image', 'text')))
            .order_by(MultimodalEvidence.id.desc())
            .limit(limit)
            .all()
        )
        chat_rows = (
            db.query(ChatInboxMessage)
            .filter(ChatInboxMessage.channel == 'dingtalk_group')
            .order_by(ChatInboxMessage.created_at.desc(), ChatInboxMessage.id.desc())
            .limit(limit)
            .all()
        )
        facts: list[dict[str, object]] = []
        for row in file_rows:
            facts.append(
                {
                    'source_key': 'dingtalk_group_file',
                    'source_type': 'dingtalk_group_content',
                    'priority': 10,
                    'evidence_type': row.evidence_type,
                    'confirmation_status': row.confirmation_status,
                    'recognized_text': row.recognized_text,
                    'payload': row.payload or {},
                    'created_at': row.created_at.isoformat() if row.created_at else None,
                }
            )
        for row in chat_rows:
            facts.append(
                {
                    'source_key': 'dingtalk_group_chat',
                    'source_type': 'dingtalk_group_content',
                    'priority': 10,
                    'channel': row.channel,
                    'group_id': row.group_id,
                    'sender_external_id': row.sender_external_id,
                    'text': row.text,
                    'trace_id': row.trace_id,
                    'created_at': row.created_at.isoformat() if row.created_at else None,
                }
            )
        return {
            'status': 'ok',
            'source': 'dingtalk_group_content',
            'request': _request_payload(kwargs),
            'facts': facts[:limit],
        }
    except Exception as exc:
        return _unavailable('dingtalk_group_content', kwargs, exc)
```

- [ ] **Step 5: Run tool test**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_langchain_tools.py::test_dingtalk_evidence_tool_returns_group_content_priority_first -q
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Run existing tool tests**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_langchain_tools.py -q
```

Expected:

```text
passed
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/hermes_langchain_tools.py backend/tests/test_hermes_langchain_tools.py
git commit -m "feat: prioritize dingtalk group evidence tool"
```

---

## Task 8: Update Fact Source Map and Generated Docs

**Files:**
- Modify: `backend/app/hermes/fact_source_map.json`
- Modify: `backend/app/services/hermes_fact_source_map_service.py`
- Modify: `backend/tests/test_hermes_fact_source_map_service.py`
- Modify: `docs/hermes/fact-source-map.md`

- [ ] **Step 1: Add failing source-map tests**

Modify `backend/tests/test_hermes_fact_source_map_service.py`.

Change `DINGTALK_EVIDENCE_CONDITION_KEYS` to:

```python
DINGTALK_EVIDENCE_CONDITION_KEYS = {
    "authorized_group",
    "content_type",
    "time_range",
}
```

Add:

```python
def test_fact_source_map_prioritizes_dingtalk_group_content_first() -> None:
    source_map = load_fact_source_map()

    for metric_key in {
        "total_output_daily",
        "finished_inbound_daily",
        "total_electricity_kwh",
        "total_gas_m3",
        "anomaly_explanation_daily",
    }:
        item = find_fact_source(metric_key)
        assert item["priority_sources"][0] == "dingtalk_group_content"


def test_production_domain_metrics_put_mes_before_data_hub_projection() -> None:
    item = find_fact_source("wip_total")

    assert item["priority_sources"].index("MES/WMS readonly") < item["priority_sources"].index("data_hub_projection")
```

- [ ] **Step 2: Run source-map tests to verify they fail**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_fact_source_map_service.py -q
```

Expected:

```text
FAILED
```

The current JSON still places old source names and some data hub/DailyFactBundle priorities above the new model.

- [ ] **Step 3: Update source-map validation**

In `backend/app/services/hermes_fact_source_map_service.py`, replace:

```python
DINGTALK_EVIDENCE_CONDITION_KEYS = {
    "authorized_group",
    "specialist_sender",
    "content_type",
    "time_range",
}
```

with:

```python
DINGTALK_EVIDENCE_CONDITION_KEYS = {
    "authorized_group",
    "content_type",
    "time_range",
}
```

Replace:

```python
    if "dingtalk_specialist" in result["priority_sources"]:
```

with:

```python
    if "dingtalk_group_content" in result["priority_sources"] or "dingtalk_specialist" in result["priority_sources"]:
```

- [ ] **Step 4: Update `backend/app/hermes/fact_source_map.json` source priorities**

For these metrics, make the first priority source `dingtalk_group_content`:

```text
total_output_daily
finished_inbound_daily
total_electricity_kwh
total_gas_m3
anomaly_explanation_daily
```

Use this condition object for each row that includes `dingtalk_group_content`:

```json
"dingtalk_evidence_conditions": {
  "authorized_group": "required",
  "content_type": ["text", "file", "image"],
  "time_range": "business_day_window"
}
```

For production-domain rows that contain both `MES/WMS readonly` and `data_hub_projection`, ensure `MES/WMS readonly` appears before `data_hub_projection`.

For rows where `DailyFactBundle` remains useful, keep it after DingTalk group content and external readonly source unless the row is explicitly a report-history metric.

- [ ] **Step 5: Regenerate generated markdown**

Run:

```bash
cd backend
python scripts/hermes_fact_source_map_export.py
```

Expected:

```text
wrote ...docs\hermes\fact-source-map.md
```

- [ ] **Step 6: Run source-map tests**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_fact_source_map_service.py -q
```

Expected:

```text
passed
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/hermes/fact_source_map.json backend/app/services/hermes_fact_source_map_service.py backend/tests/test_hermes_fact_source_map_service.py docs/hermes/fact-source-map.md
git commit -m "docs: align Hermes fact source priority"
```

---

## Task 9: Sync Sealed Direction Docs

**Files:**
- Modify: `docs/software-minus-agent-plus-prd.md`
- Modify: `docs/agent-operating-guide.md`
- Modify: `docs/system-design-direction.md`

- [ ] **Step 1: Update PRD source-priority wording**

In `docs/software-minus-agent-plus-prd.md`, update the source priority sections so they state:

```markdown
Hermes 回答 root_owner 真实问题时，事实优先级为：

1. 钉钉群文件和群聊天内容。
2. 外接只读数据库在自己业务域内的事实。
3. 数据中枢本地投影。
4. DailyFactBundle / 历史日报。
5. 人工填报。
6. RAG 解释材料。

如果钉钉群内容与 MES 或其他外接库冲突，回答优先采用钉钉群内容，并把冲突写入 trace。
```

- [ ] **Step 2: Update agent operating guide**

In `docs/agent-operating-guide.md`, add this hard rule near the Hermes evidence rules:

```markdown
硬规则：

Hermes 不能只靠固定关键词识别 root_owner 消息。

root_owner 的口语、错别字、省略句和追问，必须先做语义理解和最佳努力处理；实在不清楚时，只问一个最短澄清问题。

事实采用顺序：

1. 钉钉群文件和群聊天内容。
2. 该业务域的外接只读数据库。
3. 数据中枢投影、日报包、历史记录。
4. RAG 解释材料。
```

- [ ] **Step 3: Update system design direction**

In `docs/system-design-direction.md`, add:

```markdown
数据中枢在事实链路里的定位：

数据中枢负责读取、投影、缓存、展示和审计。

它不是最高事实源。

当钉钉群事实或外接只读数据库事实与数据中枢投影冲突时，大仪表盘和 Hermes trace 应显示冲突，而不是用数据中枢投影覆盖上游事实。
```

- [ ] **Step 4: Search for old priority language**

Run:

```bash
rg -n "DailyFactBundle.*MES|MES/WMS readonly.*data_hub_projection|dingtalk_specialist" docs backend/app/hermes backend/app/services/hermes_fact_source_map_service.py
```

Expected:

```text
Only historical/archive files or consciously updated compatibility text remain.
```

For non-archive current docs, replace old priority wording with the approved priority model.

- [ ] **Step 5: Commit**

```bash
git add docs/software-minus-agent-plus-prd.md docs/agent-operating-guide.md docs/system-design-direction.md
git commit -m "docs: sync root owner evidence priority"
```

---

## Task 10: Production Smoke Helper

**Files:**
- Create: `backend/scripts/run_hermes_root_owner_private_smoke.py`
- Create: `backend/tests/test_hermes_root_owner_private_smoke_script.py`

- [ ] **Step 1: Write failing script test**

Create `backend/tests/test_hermes_root_owner_private_smoke_script.py`:

```python
import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_hermes_root_owner_private_smoke.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_hermes_root_owner_private_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_payload_uses_private_root_owner_fields() -> None:
    module = _load_module()

    payload = module.build_payload(
        text="今天咋样",
        dingtalk_user_id="dt-root-001",
        dingtalk_union_id="union-root-001",
        trace_id="trace-smoke-001",
    )

    assert payload["senderStaffId"] == "dt-root-001"
    assert payload["senderUnionId"] == "union-root-001"
    assert payload["text"]["content"] == "今天咋样"
    assert payload["traceId"] == "trace-smoke-001"
    assert "conversationId" not in payload


def test_mask_secret_hides_token() -> None:
    module = _load_module()

    assert module.mask_secret("abcdef123456") == "abcd...3456"
    assert module.mask_secret("") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_root_owner_private_smoke_script.py -q
```

Expected:

```text
FileNotFoundError
```

- [ ] **Step 3: Create smoke helper**

Create `backend/scripts/run_hermes_root_owner_private_smoke.py`:

```python
from __future__ import annotations

import argparse
import json
import os
from uuid import uuid4

import requests


def build_payload(*, text: str, dingtalk_user_id: str, dingtalk_union_id: str | None, trace_id: str) -> dict:
    payload = {
        "senderStaffId": dingtalk_user_id,
        "text": {"content": text},
        "agentCode": "factory_dispatch",
        "traceId": trace_id,
    }
    if dingtalk_union_id:
        payload["senderUnionId"] = dingtalk_union_id
    return payload


def mask_secret(value: str) -> str:
    clean = str(value or "")
    if len(clean) <= 8:
        return "*" * len(clean)
    return f"{clean[:4]}...{clean[-4:]}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("HERMES_SMOKE_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("HERMES_DINGTALK_INBOUND_TOKEN") or os.getenv("DINGTALK_INBOUND_TOKEN"))
    parser.add_argument("--user-id", default=os.getenv("HERMES_SMOKE_ROOT_OWNER_USER_ID"))
    parser.add_argument("--union-id", default=os.getenv("HERMES_SMOKE_ROOT_OWNER_UNION_ID", ""))
    parser.add_argument("--text", default="今天咋样")
    parser.add_argument("--trace-id", default=f"root-owner-smoke-{uuid4().hex}")
    args = parser.parse_args()

    if not args.token:
        raise SystemExit("inbound token is required through --token or env")
    if not args.user_id:
        raise SystemExit("root owner DingTalk user_id is required through --user-id or env")

    url = args.base_url.rstrip("/") + "/api/v1/dingtalk/agent-inbound"
    payload = build_payload(
        text=args.text,
        dingtalk_user_id=args.user_id,
        dingtalk_union_id=args.union_id,
        trace_id=args.trace_id,
    )
    response = requests.post(
        url,
        headers={"x-dingtalk-inbound-token": args.token},
        json=payload,
        timeout=20,
    )
    result = {
        "url": url,
        "token": mask_secret(args.token),
        "trace_id": args.trace_id,
        "status_code": response.status_code,
        "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    response.raise_for_status()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run script tests**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_root_owner_private_smoke_script.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/run_hermes_root_owner_private_smoke.py backend/tests/test_hermes_root_owner_private_smoke_script.py
git commit -m "test: add root owner private smoke helper"
```

---

## Task 11: Full Verification

**Files:**
- No code files changed in this task.

- [ ] **Step 1: Run targeted backend tests**

Run:

```bash
cd backend
python -m pytest tests/test_hermes_root_owner_message_service.py tests/test_external_readonly_source_registry.py tests/test_hermes_root_owner_evidence_service.py tests/test_hermes_root_owner_reply_channel_service.py tests/test_hermes_root_owner_production_orchestrator.py tests/test_dingtalk_agent_inbound_route.py tests/test_dingtalk_factory_brain_inbound.py tests/test_hermes_langchain_tools.py tests/test_hermes_fact_source_map_service.py tests/test_hermes_root_owner_private_smoke_script.py -q
```

Expected:

```text
passed
```

- [ ] **Step 2: Run source-map export check**

Run:

```bash
cd backend
python scripts/hermes_fact_source_map_export.py
git diff -- docs/hermes/fact-source-map.md
```

Expected:

```text
No diff after regeneration.
```

- [ ] **Step 3: Run whitespace check**

Run:

```bash
git diff --check
```

Expected:

```text
No whitespace errors.
```

- [ ] **Step 4: Run production-like smoke with local or deployed API**

Run with real values in the shell environment:

```bash
cd backend
python scripts/run_hermes_root_owner_private_smoke.py --base-url "$HERMES_SMOKE_BASE_URL" --text "今天咋样"
```

Expected JSON shape:

```json
{
  "trace_id": "root-owner-smoke-...",
  "status_code": 200,
  "response": {
    "errcode": 0,
    "status": "answered",
    "outbox_message_id": 1,
    "dispatch_status": "sent"
  }
}
```

The exact `outbox_message_id` will differ.

- [ ] **Step 5: Verify database evidence after smoke**

Run a read-only query in the production database console:

```sql
select trace_id, channel, sender_external_id, text
from chat_inbox
where trace_id = '<trace from smoke>';

select trace_id, agent_code, status, answer, result_payload
from agent_runs
where trace_id = '<trace from smoke>';

select id, status, trace_id, channel_id, source_summary, attempts, last_error
from agent_outbox_messages
where trace_id = '<trace from smoke>';

select channel_type, channel_key, status, detail, provider_message_id
from external_message_logs
where outbox_message_id in (
  select id from agent_outbox_messages where trace_id = '<trace from smoke>'
);
```

Expected:

```text
chat_inbox has one dingtalk_private row.
agent_runs has one factory_dispatch row.
agent_outbox_messages has one row with sent, retrying, or dead_letter.
external_message_logs has one row explaining the send result.
```

- [ ] **Step 6: Commit verification notes**

Create or update a report only after production smoke runs:

`docs/superpowers/reports/2026-06-27-hermes-root-owner-private-smoke.md`

Use this content shape:

```markdown
# Hermes root_owner 私聊生产 smoke

日期：2026-06-27

## 问题

- 今天咋样
- 今天产量咋样
- 电这块今天高不高
- 产量和入库为啥对不上
- 今天日报还缺什么

## 结果

| 问题 | trace_id | 状态 | 回复状态 | 最高事实源 |
|---|---|---|---|---|
| 今天咋样 | root-owner-smoke-... | answered | sent | dingtalk_group_content |

## 结论

真实 root_owner 钉钉私聊链路已完成 smoke。若某条为 retrying 或 dead_letter，本报告记录失败原因和下一次重试状态。
```

Commit:

```bash
git add docs/superpowers/reports/2026-06-27-hermes-root-owner-private-smoke.md
git commit -m "docs: record root owner private smoke"
```

---

## Self-Review

Spec coverage:

- root_owner private DingTalk entry: Task 6 and Task 10.
- `HERMES_OWNER_DINGTALK_USER_IDS` root_owner whitelist: Task 6 uses existing `classify_day1_actor`.
- Soft message recognition: Task 1 and Task 6.
- DingTalk group files/chat highest priority: Task 3, Task 7, Task 8.
- External readonly registry: Task 2.
- MES production-domain readonly fact source: Task 2, Task 3, Task 8.
- Data hub as projection/cache/audit layer: Task 3, Task 8, Task 9.
- Natural paragraph answer: Task 5.
- Estimate basis and confidence: Task 1 gives recognition confidence; Task 5 records evidence basis. Numeric estimation beyond available facts is not expanded in this MVP; answer text must call out missing evidence instead of inventing exact numbers.
- Missing evidence handling: Task 3 and Task 5.
- Conflict trace: Task 3 and Task 5.
- Outbox retry and external communication log: Task 4, Task 5, existing `agent_communication_service`.
- Production smoke: Task 10 and Task 11.

Placeholder scan:

- No unfilled requirement markers.
- No unfinished work markers.
- No unnamed file paths.
- No "write tests for the above" without test code.

Type consistency:

- `RootOwnerMessagePlan` is defined in Task 1 and imported by later tasks.
- `EvidenceCandidate` and `EvidenceDecision` are defined in Task 3 and imported by Task 5 tests.
- `RootOwnerProductionTurnResult` fields match the route response fields used in Task 6.
- Existing outbox channel type is `dingtalk_work_notice`, matching `agent_communication_service._default_sender`.
