# Hermes 20 Question Real Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real 20-question acceptance gate proving `鑫泰铝业智能大脑` can understand production questions, query real sources, answer in Chinese with `追踪编号`, deliver to approved DingTalk targets, and guard datahub deletions.

**Architecture:** Add a small acceptance layer around existing Hermes/root-owner services instead of creating a new agent stack. The acceptance layer records one snapshot per question, scores four gates (understanding, source, answer, DingTalk delivery), and produces a report; deletion work is protected by a reusable guard that extends the existing datahub diet audit service.

**Tech Stack:** Python 3.14, pytest, SQLAlchemy models in `backend/app/models/agent_communication.py`, existing Hermes services, existing DingTalk outbox services, existing MES read service, frontend Node tests only when `/manage` display changes.

---

## Scope Check

This plan covers three connected tracks:

1. `鑫泰铝业智能大脑` 20 问能力验收。
2. 指定测试群和指定个人的真实钉钉送达门禁。
3. 数据中枢减法删除守卫。

They stay in one plan because the approved spec requires one final gate: 20/20 核心链路、18/20 真实外发、删除不误伤主链路。

## File Structure

Create:

- `backend/app/services/hermes_20_question_acceptance.py`
  Defines the 20-question catalog, per-question snapshots, four-layer scoring, summary output, environment failure classification, and report rendering.

- `backend/app/services/hermes_20_question_runner.py`
  Runs the catalog through existing `run_root_owner_production_turn()`, rereads `AgentRun`, `AgentOutboxMessage`, and `ExternalMessageLog`, then builds acceptance snapshots.

- `backend/scripts/hermes_20_question_acceptance.py`
  CLI entry point for local, production-readonly, and approved real DingTalk runs.

- `backend/scripts/check_datahub_deletion_guard.py`
  CLI entry point that checks candidate deletes before files are removed.

- `backend/tests/test_hermes_20_question_real_acceptance.py`
  Unit tests for catalog coverage, core gate scoring, conflict/missing handling, Chinese identity, and RAG boundary.

- `backend/tests/test_hermes_20_question_runner.py`
  Tests that runner creates snapshots from existing root-owner turn outputs without real DingTalk calls.

- `backend/tests/test_hermes_real_dingtalk_delivery_gate.py`
  Tests sent, retrying, dead-letter, dry-run, and environment failure classifications.

- `backend/tests/test_datahub_deletion_guard.py`
  Tests protected paths, referenced paths, safe candidate paths, and report shape.

Modify:

- `backend/app/services/hermes_datahub_diet_audit_service.py`
  Add deletion guard types and dependency scanning. Keep existing audit behavior unchanged.

- `docs/datahub-deprecation-register.md`
  Add any actually checked delete candidates and their guard result after implementation.

- `docs/superpowers/reports/2026-06-28-hermes-20-question-real-acceptance-report.md`
  Add final run report after the real gate is executed.

Do not modify unless a task explicitly requires it:

- `frontend/src/router/index.js`
- `frontend/src/views/mobile/*`
- `frontend/src/views/manage/today/*`
- `frontend/src/views/manage/live/*`
- `frontend/src/views/manage/production/*`
- `backend/app/services/hermes_root_owner_production_orchestrator.py`
- `backend/app/services/hermes_root_owner_evidence_service.py`
- `backend/app/services/hermes_mes_read_service.py`
- `backend/app/services/agent_communication_service.py`

## Task 1: 20 问验收目录和四层评分器

**Files:**
- Create: `backend/app/services/hermes_20_question_acceptance.py`
- Test: `backend/tests/test_hermes_20_question_real_acceptance.py`

- [ ] **Step 1: Write the failing catalog and scoring tests**

Create `backend/tests/test_hermes_20_question_real_acceptance.py` with:

```python
from __future__ import annotations

from app.services.hermes_20_question_acceptance import (
    AcceptanceTurnSnapshot,
    build_20_question_catalog,
    evaluate_acceptance_summary,
    evaluate_question_snapshot,
)


def _passing_snapshot(question_id: int, *, answer: str | None = None) -> AcceptanceTurnSnapshot:
    catalog = {item.question_id: item for item in build_20_question_catalog()}
    question = catalog[question_id]
    return AcceptanceTurnSnapshot(
        question_id=question.question_id,
        trace_id=f"trace-q{question_id}",
        status="answered",
        answer=answer
        or "鑫泰铝业智能大脑回答：结论已确认。来源：钉钉群聊天内容、MES/WMS 只读链路。状态：confirmed。追踪编号：trace-q。",
        recognition={
            "domain": question.domain,
            "metric_keys": list(question.metric_keys),
            "business_date": "2026-06-27",
            "needs_clarification": False,
        },
        evidence={
            "primary_source": "dingtalk_group_chat",
            "candidate_sources": ["dingtalk_group_chat", "mes_readonly", "data_hub_projection"],
            "missing_sources": [],
            "conflicts": [],
            "trace": {
                "source_order": ["dingtalk_group_chat", "mes_readonly", "data_hub_projection"],
                "source_status": {
                    "dingtalk_group_content": {"status": "ok"},
                    "mes_readonly": {"status": "ok"},
                    "data_hub_projection": {"status": "ok"},
                },
            },
        },
        dispatch={
            "status": "sent",
            "detail": "ok",
            "outbox_message_id": 100 + question_id,
            "log_status": "sent",
            "channel_type": "dingtalk_group",
        },
        source_health={
            "energy_readonly": {
                "source_key": "energy_readonly",
                "domain": "energy",
                "status": "disabled",
                "readonly": True,
                "last_success_at": None,
                "failure_reason": "source_not_configured",
            }
        },
    )


def test_catalog_has_exactly_20_approved_questions() -> None:
    catalog = build_20_question_catalog()

    assert len(catalog) == 20
    assert catalog[0].question_id == 1
    assert catalog[0].question == "今天全厂总产量是多少？"
    assert catalog[14].metric_keys == ("dingtalk_specialist_evidence",)
    assert catalog[-1].question == "今天日报能不能自动生成？还缺什么？"


def test_evaluate_question_snapshot_passes_all_four_gates() -> None:
    result = evaluate_question_snapshot(build_20_question_catalog()[0], _passing_snapshot(1))

    assert result.core_passed is True
    assert result.delivery_passed is True
    assert result.status == "confirmed"
    assert [gate.name for gate in result.gates if not gate.passed] == []


def test_answer_gate_rejects_internal_identity_and_trace_id_copy() -> None:
    question = build_20_question_catalog()[0]
    snapshot = _passing_snapshot(
        1,
        answer="Factory Brain answered with trace_id: abc. 来源：MES。状态：confirmed。",
    )

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is False
    assert "answer" in result.failed_gate_names
    assert "public_identity_or_language_failed" in result.failed_reasons


def test_source_gate_rejects_rag_as_current_fact_source() -> None:
    question = build_20_question_catalog()[0]
    snapshot = _passing_snapshot(1)
    snapshot.evidence["primary_source"] = "rag"
    snapshot.evidence["trace"]["source_order"] = ["rag"]

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is False
    assert "rag_used_as_current_fact_source" in result.failed_reasons


def test_source_gate_accepts_energy_readonly_disabled_as_known_missing_state() -> None:
    question = build_20_question_catalog()[4]
    snapshot = _passing_snapshot(5)
    snapshot.evidence["trace"]["source_status"]["energy_readonly"] = {
        "status": "disabled",
        "reason": "source_not_configured",
    }

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is True
    assert result.status in {"confirmed", "candidate"}


def test_delivery_gate_allows_environment_failure_but_not_core_failure() -> None:
    question = build_20_question_catalog()[0]
    snapshot = _passing_snapshot(1)
    snapshot.dispatch = {
        "status": "retrying",
        "detail": "DingTalk API rate limit",
        "outbox_message_id": 101,
        "log_status": "retrying",
        "channel_type": "dingtalk_group",
    }

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is True
    assert result.delivery_passed is False
    assert result.delivery_environment_failure is True


def test_summary_requires_20_core_passes_and_allows_two_environment_delivery_failures() -> None:
    catalog = build_20_question_catalog()
    snapshots = [_passing_snapshot(item.question_id) for item in catalog]
    for snapshot in snapshots[:2]:
        snapshot.dispatch["status"] = "retrying"
        snapshot.dispatch["detail"] = "DingTalk test group permission denied"
        snapshot.dispatch["log_status"] = "retrying"

    summary = evaluate_acceptance_summary(snapshots)

    assert summary.core_passed is True
    assert summary.delivery_passed is True
    assert summary.core_pass_count == 20
    assert summary.delivery_success_count == 18
    assert summary.environment_failure_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
python -m pytest -q tests/test_hermes_20_question_real_acceptance.py
```

Expected:

```text
ModuleNotFoundError: No module named 'app.services.hermes_20_question_acceptance'
```

- [ ] **Step 3: Create the catalog and scoring service**

Create `backend/app/services/hermes_20_question_acceptance.py` with:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class HermesAcceptanceQuestion:
    question_id: int
    question: str
    metric_keys: tuple[str, ...]
    domain: str
    requires_mes: bool
    requires_dingtalk: bool
    status_hint: str = "confirmed"


@dataclass(frozen=True, slots=True)
class LayerGateResult:
    name: str
    passed: bool
    reason: str


@dataclass(slots=True)
class AcceptanceTurnSnapshot:
    question_id: int
    trace_id: str
    status: str
    answer: str
    recognition: dict[str, Any]
    evidence: dict[str, Any]
    dispatch: dict[str, Any]
    source_health: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AcceptanceQuestionResult:
    question_id: int
    question: str
    status: str
    gates: tuple[LayerGateResult, ...]
    delivery_environment_failure: bool

    @property
    def failed_gate_names(self) -> list[str]:
        return [gate.name for gate in self.gates if not gate.passed]

    @property
    def failed_reasons(self) -> list[str]:
        return [gate.reason for gate in self.gates if not gate.passed]

    @property
    def core_passed(self) -> bool:
        return all(gate.passed for gate in self.gates if gate.name != "dingtalk_delivery")

    @property
    def delivery_passed(self) -> bool:
        return next(gate.passed for gate in self.gates if gate.name == "dingtalk_delivery")


@dataclass(frozen=True, slots=True)
class AcceptanceSummary:
    core_passed: bool
    delivery_passed: bool
    core_pass_count: int
    delivery_success_count: int
    environment_failure_count: int
    total: int
    results: tuple[AcceptanceQuestionResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "core_passed": self.core_passed,
            "delivery_passed": self.delivery_passed,
            "core_pass_count": self.core_pass_count,
            "delivery_success_count": self.delivery_success_count,
            "environment_failure_count": self.environment_failure_count,
            "total": self.total,
            "results": [
                {
                    **asdict(result),
                    "core_passed": result.core_passed,
                    "delivery_passed": result.delivery_passed,
                    "failed_gate_names": result.failed_gate_names,
                    "failed_reasons": result.failed_reasons,
                }
                for result in self.results
            ],
        }


_FORBIDDEN_PUBLIC_TERMS = (
    "Factory Brain",
    "root_owner",
    "trace_id",
    "developer",
    "engineer",
    "Codex",
)
_ENVIRONMENT_FAILURE_HINTS = (
    "permission",
    "权限",
    "rate limit",
    "限流",
    "timeout",
    "network",
    "网络",
    "token",
    "not configured",
    "未配置",
    "DingTalk API",
    "钉钉接口",
    "test group",
    "测试群",
)


def build_20_question_catalog() -> tuple[HermesAcceptanceQuestion, ...]:
    return (
        HermesAcceptanceQuestion(1, "今天全厂总产量是多少？", ("total_output_daily",), "production", True, True),
        HermesAcceptanceQuestion(2, "今天各车间产量分别是多少？", ("workshop_output_daily",), "production", True, False),
        HermesAcceptanceQuestion(3, "今天成品入库多少？", ("finished_inbound_daily",), "inventory", True, True),
        HermesAcceptanceQuestion(4, "今天投料量是多少？", ("daily_input_weight",), "production", True, False),
        HermesAcceptanceQuestion(5, "今天高压总用电量是多少？", ("total_electricity_kwh",), "energy", False, True),
        HermesAcceptanceQuestion(6, "今天全厂用气量是多少？", ("total_gas_m3",), "energy", False, True),
        HermesAcceptanceQuestion(7, "今天吨电耗是多少？分母是什么？", ("electricity_per_ton",), "energy", True, False),
        HermesAcceptanceQuestion(8, "今天成品率是多少？分子分母是什么？", ("daily_yield_rate",), "quality", True, False, "candidate"),
        HermesAcceptanceQuestion(9, "今天成本折算元/吨是多少？", ("cost_per_ton",), "cost", False, False),
        HermesAcceptanceQuestion(10, "今天在制料是多少？", ("wip_total",), "production", True, False, "candidate"),
        HermesAcceptanceQuestion(11, "现在总余合同量是多少？", ("remaining_contract_weight",), "operations", True, False, "candidate"),
        HermesAcceptanceQuestion(12, "本月累计产量是多少？", ("monthly_total_output",), "operation_period", False, False),
        HermesAcceptanceQuestion(13, "今年累计产量是多少？", ("annual_total_output",), "operation_period", False, False, "candidate"),
        HermesAcceptanceQuestion(14, "今天有哪些异常说明？", ("anomaly_explanation_daily",), "anomaly", False, True),
        HermesAcceptanceQuestion(15, "哪些数字来自专项责任人钉钉证据？", ("dingtalk_specialist_evidence",), "evidence", False, True),
        HermesAcceptanceQuestion(16, "今天哪个关键数字最不可信？", ("source_status",), "anomaly", False, True, "candidate"),
        HermesAcceptanceQuestion(17, "产量和入库为什么对不上？", ("total_output_daily", "finished_inbound_daily"), "anomaly", True, True, "conflict"),
        HermesAcceptanceQuestion(18, "电耗升高可能由什么造成？", ("electricity_per_ton", "anomaly_explanation_daily"), "energy", True, True, "candidate"),
        HermesAcceptanceQuestion(19, "哪些指标缺少正式来源？", ("source_status",), "anomaly", False, True, "missing"),
        HermesAcceptanceQuestion(20, "今天日报能不能自动生成？还缺什么？", ("daily_report_readiness",), "factory_overview", True, True, "candidate"),
    )


def evaluate_question_snapshot(
    question: HermesAcceptanceQuestion,
    snapshot: AcceptanceTurnSnapshot,
) -> AcceptanceQuestionResult:
    gates = (
        _understanding_gate(question, snapshot),
        _source_gate(question, snapshot),
        _answer_gate(snapshot),
        _delivery_gate(snapshot),
    )
    return AcceptanceQuestionResult(
        question_id=question.question_id,
        question=question.question,
        status=_status_from_snapshot(snapshot),
        gates=gates,
        delivery_environment_failure=_is_environment_delivery_failure(snapshot),
    )


def evaluate_acceptance_summary(snapshots: Sequence[AcceptanceTurnSnapshot]) -> AcceptanceSummary:
    catalog = {question.question_id: question for question in build_20_question_catalog()}
    results = tuple(
        evaluate_question_snapshot(catalog[snapshot.question_id], snapshot)
        for snapshot in snapshots
        if snapshot.question_id in catalog
    )
    core_pass_count = sum(1 for result in results if result.core_passed)
    delivery_success_count = sum(1 for result in results if result.delivery_passed)
    environment_failure_count = sum(
        1
        for result in results
        if result.core_passed and not result.delivery_passed and result.delivery_environment_failure
    )
    total = len(build_20_question_catalog())
    return AcceptanceSummary(
        core_passed=core_pass_count == total,
        delivery_passed=delivery_success_count + environment_failure_count >= total
        and environment_failure_count <= 2,
        core_pass_count=core_pass_count,
        delivery_success_count=delivery_success_count,
        environment_failure_count=environment_failure_count,
        total=total,
        results=results,
    )


def render_acceptance_report(summary: AcceptanceSummary) -> str:
    lines = [
        "# 鑫泰铝业智能大脑 20 问真实验收报告",
        "",
        f"核心链路：{summary.core_pass_count}/{summary.total}",
        f"真实外发成功：{summary.delivery_success_count}/{summary.total}",
        f"环境型外发失败：{summary.environment_failure_count}",
        "",
        "| 问题 | 理解 | 来源 | 回答 | 钉钉 | 状态 |",
        "|---|---|---|---|---|---|",
    ]
    for result in summary.results:
        gates = {gate.name: gate for gate in result.gates}
        lines.append(
            "| "
            + " | ".join(
                [
                    result.question,
                    _gate_text(gates["understanding"]),
                    _gate_text(gates["source"]),
                    _gate_text(gates["answer"]),
                    _gate_text(gates["dingtalk_delivery"]),
                    result.status,
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def _understanding_gate(question: HermesAcceptanceQuestion, snapshot: AcceptanceTurnSnapshot) -> LayerGateResult:
    recognition = snapshot.recognition or {}
    if recognition.get("needs_clarification") is True:
        return LayerGateResult("understanding", False, "needs_clarification")
    metric_keys = set(_list_value(recognition.get("metric_keys")))
    if not any(metric_key in metric_keys for metric_key in question.metric_keys):
        return LayerGateResult("understanding", False, "metric_not_recognized")
    if question.domain not in {recognition.get("domain"), "factory_overview", "anomaly"}:
        return LayerGateResult("understanding", False, "domain_not_recognized")
    return LayerGateResult("understanding", True, "ok")


def _source_gate(question: HermesAcceptanceQuestion, snapshot: AcceptanceTurnSnapshot) -> LayerGateResult:
    evidence = snapshot.evidence or {}
    trace = evidence.get("trace") if isinstance(evidence.get("trace"), Mapping) else {}
    source_order = _list_value(trace.get("source_order"))
    source_status = trace.get("source_status") if isinstance(trace.get("source_status"), Mapping) else {}
    primary_source = str(evidence.get("primary_source") or "")
    if primary_source == "rag" or source_order[:1] == ["rag"]:
        return LayerGateResult("source", False, "rag_used_as_current_fact_source")
    if question.requires_dingtalk and "dingtalk_group_chat" not in source_order and "dingtalk_group_file" not in source_order:
        return LayerGateResult("source", False, "dingtalk_source_not_checked")
    if question.requires_mes and "mes_readonly" not in source_order and "mes_readonly" not in source_status:
        return LayerGateResult("source", False, "mes_readonly_not_checked")
    if not source_order and not source_status:
        return LayerGateResult("source", False, "no_real_source_trace")
    return LayerGateResult("source", True, "ok")


def _answer_gate(snapshot: AcceptanceTurnSnapshot) -> LayerGateResult:
    answer = str(snapshot.answer or "")
    if "鑫泰铝业智能大脑" not in answer or "追踪编号" not in answer:
        return LayerGateResult("answer", False, "public_identity_or_language_failed")
    if any(term in answer for term in _FORBIDDEN_PUBLIC_TERMS):
        return LayerGateResult("answer", False, "public_identity_or_language_failed")
    if "来源" not in answer or "状态" not in answer:
        return LayerGateResult("answer", False, "answer_contract_incomplete")
    return LayerGateResult("answer", True, "ok")


def _delivery_gate(snapshot: AcceptanceTurnSnapshot) -> LayerGateResult:
    status = str((snapshot.dispatch or {}).get("status") or "")
    log_status = str((snapshot.dispatch or {}).get("log_status") or "")
    if status == "sent" and log_status in {"sent", ""}:
        return LayerGateResult("dingtalk_delivery", True, "sent")
    if _is_environment_delivery_failure(snapshot):
        return LayerGateResult("dingtalk_delivery", False, "environment_failure")
    return LayerGateResult("dingtalk_delivery", False, "delivery_failed")


def _is_environment_delivery_failure(snapshot: AcceptanceTurnSnapshot) -> bool:
    dispatch = snapshot.dispatch or {}
    detail = str(dispatch.get("detail") or "")
    status = str(dispatch.get("status") or "")
    if status in {"dry_run", "sent"}:
        return False
    return any(hint.lower() in detail.lower() for hint in _ENVIRONMENT_FAILURE_HINTS)


def _status_from_snapshot(snapshot: AcceptanceTurnSnapshot) -> str:
    evidence = snapshot.evidence or {}
    conflicts = evidence.get("conflicts") or []
    missing = evidence.get("missing_sources") or []
    if conflicts:
        return "conflict"
    if missing:
        return "missing"
    if snapshot.status in {"answered", "sent"}:
        return "confirmed"
    return str(snapshot.status or "candidate")


def _list_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return [str(item) for item in value]
    return [str(value)]


def _gate_text(gate: LayerGateResult) -> str:
    return "过" if gate.passed else gate.reason
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
cd backend
python -m pytest -q tests/test_hermes_20_question_real_acceptance.py
```

Expected:

```text
7 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/hermes_20_question_acceptance.py backend/tests/test_hermes_20_question_real_acceptance.py
git commit -m "test: add hermes 20 question acceptance scoring"
```

## Task 2: 真实运行快照 Runner

**Files:**
- Create: `backend/app/services/hermes_20_question_runner.py`
- Test: `backend/tests/test_hermes_20_question_runner.py`

- [ ] **Step 1: Write the failing runner test**

Create `backend/tests/test_hermes_20_question_runner.py` with:

```python
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.agent_communication import AgentRun, AgentOutboxMessage, ExternalMessageLog
from app.models.system import User
from app.services.hermes_20_question_runner import run_20_question_acceptance


def _db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def _user() -> User:
    return User(
        id=1,
        username="root-owner",
        password_hash="x",
        name="张兆嘉",
        role="admin",
        is_active=True,
        dingtalk_user_id="dt-root-001",
    )


def test_runner_builds_snapshots_from_existing_turn_outputs(monkeypatch) -> None:
    db = _db_session()
    db.add(_user())
    db.commit()

    def fake_turn(**kwargs):
        trace_id = kwargs["trace_id"]
        outbox = AgentOutboxMessage(
            dispatch_key=f"dispatch-{trace_id}",
            status="sent",
            message_type="markdown",
            title="鑫泰铝业智能大脑私聊回复",
            content="ok",
            trace_id=trace_id,
        )
        db.add(outbox)
        db.flush()
        run = AgentRun(
            trace_id=trace_id,
            agent_code="xintai-root-owner-production",
            status="answered",
            status_color="green",
            answer=f"鑫泰铝业智能大脑回答。来源：钉钉群聊天内容。状态：confirmed。追踪编号：{trace_id}",
            result_payload={
                "recognition": {
                    "domain": "production",
                    "metric_keys": ["total_output_daily"],
                    "business_date": "2026-06-27",
                    "needs_clarification": False,
                },
                "evidence": {
                    "primary_source": "dingtalk_group_chat",
                    "candidate_sources": ["dingtalk_group_chat", "mes_readonly"],
                    "missing_sources": [],
                    "conflicts": [],
                    "trace": {
                        "source_order": ["dingtalk_group_chat", "mes_readonly"],
                        "source_status": {"mes_readonly": {"status": "ok"}},
                    },
                },
            },
        )
        db.add(run)
        db.add(
            ExternalMessageLog(
                outbox_message_id=outbox.id,
                channel_type="dingtalk_group",
                channel_key="test-group",
                status="sent",
                detail="ok",
            )
        )
        db.commit()
        return SimpleNamespace(
            trace_id=trace_id,
            status="answered",
            answer=run.answer,
            chat_inbox_id=1,
            agent_run_id=run.id,
            outbox_message_id=outbox.id,
            dispatch_status="sent",
            dispatch_detail="ok",
        )

    monkeypatch.setattr("app.services.hermes_20_question_runner.run_root_owner_production_turn", lambda *args, **kwargs: fake_turn(**kwargs))

    outcome = run_20_question_acceptance(
        db,
        current_user=db.get(User, 1),
        sender_external_id="dt-root-001",
        business_date=date(2026, 6, 27),
        limit=1,
        source_health={"energy_readonly": {"status": "disabled", "failure_reason": "source_not_configured"}},
    )

    assert outcome.summary.total == 20
    assert len(outcome.snapshots) == 1
    assert outcome.snapshots[0].question_id == 1
    assert outcome.snapshots[0].dispatch["log_status"] == "sent"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
python -m pytest -q tests/test_hermes_20_question_runner.py
```

Expected:

```text
ModuleNotFoundError: No module named 'app.services.hermes_20_question_runner'
```

- [ ] **Step 3: Create the runner service**

Create `backend/app/services/hermes_20_question_runner.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_communication import AgentRun, AgentOutboxMessage, ExternalMessageLog
from app.models.system import User
from app.services.hermes_20_question_acceptance import (
    AcceptanceSummary,
    AcceptanceTurnSnapshot,
    build_20_question_catalog,
    evaluate_acceptance_summary,
)
from app.services.hermes_root_owner_production_orchestrator import run_root_owner_production_turn


@dataclass(frozen=True, slots=True)
class Hermes20QuestionRunOutcome:
    snapshots: tuple[AcceptanceTurnSnapshot, ...]
    summary: AcceptanceSummary


def run_20_question_acceptance(
    db: Session,
    *,
    current_user: User,
    sender_external_id: str,
    business_date: date,
    source_health: dict[str, Any] | None = None,
    limit: int | None = None,
) -> Hermes20QuestionRunOutcome:
    questions = build_20_question_catalog()
    if limit is not None:
        questions = questions[: max(1, int(limit))]
    snapshots: list[AcceptanceTurnSnapshot] = []
    for question in questions:
        trace_id = f"hermes-20q-{business_date.isoformat()}-{question.question_id:02d}"
        result = run_root_owner_production_turn(
            db,
            text=question.question,
            current_user=current_user,
            sender_external_id=sender_external_id,
            trace_id=trace_id,
            source_payload={"source": "hermes_20_question_acceptance", "question_id": question.question_id},
            default_business_date=business_date,
        )
        snapshots.append(
            build_snapshot_from_turn(
                db,
                question_id=question.question_id,
                trace_id=result.trace_id,
                status=result.status,
                answer=result.answer,
                outbox_message_id=result.outbox_message_id,
                source_health=source_health or {},
            )
        )
    return Hermes20QuestionRunOutcome(
        snapshots=tuple(snapshots),
        summary=evaluate_acceptance_summary(snapshots),
    )


def build_snapshot_from_turn(
    db: Session,
    *,
    question_id: int,
    trace_id: str,
    status: str,
    answer: str,
    outbox_message_id: int | None,
    source_health: dict[str, Any],
) -> AcceptanceTurnSnapshot:
    run = (
        db.query(AgentRun)
        .filter(AgentRun.trace_id == trace_id)
        .order_by(AgentRun.id.desc())
        .first()
    )
    payload = run.result_payload if run is not None and isinstance(run.result_payload, dict) else {}
    dispatch = _dispatch_payload(db, outbox_message_id)
    return AcceptanceTurnSnapshot(
        question_id=question_id,
        trace_id=trace_id,
        status=status,
        answer=answer,
        recognition=dict(payload.get("recognition") or {}),
        evidence=dict(payload.get("evidence") or {}),
        dispatch=dispatch,
        source_health=source_health,
    )


def _dispatch_payload(db: Session, outbox_message_id: int | None) -> dict[str, Any]:
    if not outbox_message_id:
        return {"status": "missing", "detail": "outbox_message_missing"}
    message = db.get(AgentOutboxMessage, int(outbox_message_id))
    log = (
        db.query(ExternalMessageLog)
        .filter(ExternalMessageLog.outbox_message_id == int(outbox_message_id))
        .order_by(ExternalMessageLog.id.desc())
        .first()
    )
    return {
        "status": message.status if message is not None else "missing",
        "detail": (log.detail if log is not None else None) or (message.last_error if message is not None else None) or "",
        "outbox_message_id": outbox_message_id,
        "log_status": log.status if log is not None else "",
        "channel_type": log.channel_type if log is not None else "",
        "channel_key": log.channel_key if log is not None else "",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
cd backend
python -m pytest -q tests/test_hermes_20_question_runner.py
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/hermes_20_question_runner.py backend/tests/test_hermes_20_question_runner.py
git commit -m "feat: add hermes 20 question acceptance runner"
```

## Task 3: 钉钉真实送达门禁

**Files:**
- Modify: `backend/app/services/hermes_20_question_acceptance.py`
- Test: `backend/tests/test_hermes_real_dingtalk_delivery_gate.py`

- [ ] **Step 1: Write delivery classification tests**

Create `backend/tests/test_hermes_real_dingtalk_delivery_gate.py` with:

```python
from __future__ import annotations

from app.services.hermes_20_question_acceptance import AcceptanceTurnSnapshot, build_20_question_catalog, evaluate_question_snapshot


def _snapshot(dispatch: dict) -> AcceptanceTurnSnapshot:
    return AcceptanceTurnSnapshot(
        question_id=1,
        trace_id="trace-delivery",
        status="answered",
        answer="鑫泰铝业智能大脑回答。来源：钉钉群聊天内容。状态：confirmed。追踪编号：trace-delivery。",
        recognition={
            "domain": "production",
            "metric_keys": ["total_output_daily"],
            "business_date": "2026-06-27",
            "needs_clarification": False,
        },
        evidence={
            "primary_source": "dingtalk_group_chat",
            "candidate_sources": ["dingtalk_group_chat", "mes_readonly"],
            "missing_sources": [],
            "conflicts": [],
            "trace": {
                "source_order": ["dingtalk_group_chat", "mes_readonly"],
                "source_status": {"mes_readonly": {"status": "ok"}},
            },
        },
        dispatch=dispatch,
        source_health={},
    )


def test_delivery_gate_accepts_sent_external_log() -> None:
    result = evaluate_question_snapshot(
        build_20_question_catalog()[0],
        _snapshot({"status": "sent", "log_status": "sent", "detail": "ok"}),
    )

    assert result.delivery_passed is True


def test_delivery_gate_rejects_dry_run_for_real_acceptance() -> None:
    result = evaluate_question_snapshot(
        build_20_question_catalog()[0],
        _snapshot({"status": "dry_run", "log_status": "dry_run", "detail": "dry-run only, message not sent"}),
    )

    assert result.delivery_passed is False
    assert result.delivery_environment_failure is False


def test_delivery_gate_classifies_test_group_permission_as_environment_failure() -> None:
    result = evaluate_question_snapshot(
        build_20_question_catalog()[0],
        _snapshot({"status": "retrying", "log_status": "retrying", "detail": "test group permission denied"}),
    )

    assert result.delivery_passed is False
    assert result.delivery_environment_failure is True


def test_delivery_gate_classifies_code_exception_as_non_environment_failure() -> None:
    result = evaluate_question_snapshot(
        build_20_question_catalog()[0],
        _snapshot({"status": "retrying", "log_status": "retrying", "detail": "AttributeError: object has no attribute send"}),
    )

    assert result.delivery_passed is False
    assert result.delivery_environment_failure is False
```

- [ ] **Step 2: Run test to verify current behavior**

Run:

```powershell
cd backend
python -m pytest -q tests/test_hermes_real_dingtalk_delivery_gate.py
```

Expected:

```text
4 passed
```

If the dry-run or environment tests fail, edit only `_ENVIRONMENT_FAILURE_HINTS`, `_delivery_gate()`, and `_is_environment_delivery_failure()` in `backend/app/services/hermes_20_question_acceptance.py` until the four tests pass. Do not change `agent_communication_service.py`.

- [ ] **Step 3: Run combined acceptance tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_hermes_20_question_real_acceptance.py tests/test_hermes_real_dingtalk_delivery_gate.py
```

Expected:

```text
11 passed
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/hermes_20_question_acceptance.py backend/tests/test_hermes_real_dingtalk_delivery_gate.py
git commit -m "test: lock hermes real dingtalk delivery gate"
```

## Task 4: CLI for approved real acceptance runs

**Files:**
- Create: `backend/scripts/hermes_20_question_acceptance.py`
- Test: add CLI coverage to `backend/tests/test_hermes_20_question_runner.py`

- [ ] **Step 1: Add failing CLI test**

Append to `backend/tests/test_hermes_20_question_runner.py`:

```python
def test_acceptance_cli_requires_explicit_real_delivery_flag() -> None:
    from backend.scripts.hermes_20_question_acceptance import parse_args

    args = parse_args([
        "--business-date",
        "2026-06-27",
        "--sender-external-id",
        "dt-root-001",
        "--target",
        "test-group",
    ])

    assert args.real_delivery is False


def test_acceptance_cli_parses_real_delivery_targets() -> None:
    from backend.scripts.hermes_20_question_acceptance import parse_args

    args = parse_args([
        "--business-date",
        "2026-06-27",
        "--sender-external-id",
        "dt-root-001",
        "--target",
        "test-group",
        "--target",
        "dt-person-001",
        "--real-delivery",
    ])

    assert args.real_delivery is True
    assert args.target == ["test-group", "dt-person-001"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
python -m pytest -q tests/test_hermes_20_question_runner.py::test_acceptance_cli_requires_explicit_real_delivery_flag tests/test_hermes_20_question_runner.py::test_acceptance_cli_parses_real_delivery_targets
```

Expected:

```text
ModuleNotFoundError: No module named 'backend.scripts.hermes_20_question_acceptance'
```

- [ ] **Step 3: Create the CLI**

Create `backend/scripts/hermes_20_question_acceptance.py` with:

```python
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal
from app.models.system import User
from app.services.external_readonly_source_registry import build_external_readonly_sources, health_check_sources
from app.services.hermes_20_question_acceptance import render_acceptance_report
from app.services.hermes_20_question_runner import run_20_question_acceptance


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run 鑫泰铝业智能大脑 20 问真实验收")
    parser.add_argument("--business-date", required=True)
    parser.add_argument("--sender-external-id", required=True)
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--real-delivery", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--report-path", default="docs/superpowers/reports/2026-06-28-hermes-20-question-real-acceptance-report.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.real_delivery:
        print("refusing_real_acceptance_without_real_delivery_flag")
        return 2
    if not args.target:
        print("target_required")
        return 2
    business_date = date.fromisoformat(args.business_date)
    db = SessionLocal()
    try:
        current_user = db.get(User, int(args.user_id))
        if current_user is None:
            print("user_not_found")
            return 2
        source_health = health_check_sources(build_external_readonly_sources(), probe=lambda source: None)
        outcome = run_20_question_acceptance(
            db,
            current_user=current_user,
            sender_external_id=args.sender_external_id,
            business_date=business_date,
            source_health=source_health,
            limit=args.limit,
        )
        report = render_acceptance_report(outcome.summary)
        report_path = ROOT / args.report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        print(report)
        return 0 if outcome.summary.core_passed and outcome.summary.delivery_passed else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI parser tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_hermes_20_question_runner.py::test_acceptance_cli_requires_explicit_real_delivery_flag tests/test_hermes_20_question_runner.py::test_acceptance_cli_parses_real_delivery_targets
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/hermes_20_question_acceptance.py backend/tests/test_hermes_20_question_runner.py
git commit -m "feat: add hermes 20 question acceptance cli"
```

## Task 5: 数据中枢删除守卫

**Files:**
- Modify: `backend/app/services/hermes_datahub_diet_audit_service.py`
- Create: `backend/scripts/check_datahub_deletion_guard.py`
- Test: `backend/tests/test_datahub_deletion_guard.py`

- [ ] **Step 1: Write failing deletion guard tests**

Create `backend/tests/test_datahub_deletion_guard.py` with:

```python
from __future__ import annotations

from pathlib import Path

from app.services.hermes_datahub_diet_audit_service import check_candidate_delete_paths


def test_deletion_guard_blocks_protected_hermes_path(tmp_path: Path) -> None:
    path = tmp_path / "backend/app/services/hermes_root_owner_production_orchestrator.py"
    path.parent.mkdir(parents=True)
    path.write_text("print('protected')", encoding="utf-8")

    result = check_candidate_delete_paths(tmp_path, ["backend/app/services/hermes_root_owner_production_orchestrator.py"])

    assert result["passed"] is False
    assert result["items"][0]["status"] == "blocked"
    assert result["items"][0]["reason"] == "protected_marker"


def test_deletion_guard_blocks_referenced_candidate(tmp_path: Path) -> None:
    candidate = tmp_path / "backend/app/services/old_service.py"
    caller = tmp_path / "backend/app/routers/old_router.py"
    candidate.parent.mkdir(parents=True)
    caller.parent.mkdir(parents=True)
    candidate.write_text("def old_service():\n    return 1\n", encoding="utf-8")
    caller.write_text("from app.services.old_service import old_service\n", encoding="utf-8")

    result = check_candidate_delete_paths(tmp_path, ["backend/app/services/old_service.py"])

    assert result["passed"] is False
    assert result["items"][0]["status"] == "blocked"
    assert result["items"][0]["reason"] == "referenced_by_runtime_file"
    assert "backend/app/routers/old_router.py" in result["items"][0]["references"]


def test_deletion_guard_allows_unreferenced_review_file(tmp_path: Path) -> None:
    candidate = tmp_path / "frontend/src/views/review/UnusedPanel.vue"
    candidate.parent.mkdir(parents=True)
    candidate.write_text("<template><div /></template>\n", encoding="utf-8")

    result = check_candidate_delete_paths(tmp_path, ["frontend/src/views/review/UnusedPanel.vue"])

    assert result["passed"] is True
    assert result["items"][0]["status"] == "delete_allowed"


def test_deletion_guard_reports_missing_candidate(tmp_path: Path) -> None:
    result = check_candidate_delete_paths(tmp_path, ["backend/app/services/missing.py"])

    assert result["passed"] is False
    assert result["items"][0]["status"] == "blocked"
    assert result["items"][0]["reason"] == "candidate_missing"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
python -m pytest -q tests/test_datahub_deletion_guard.py
```

Expected:

```text
ImportError: cannot import name 'check_candidate_delete_paths'
```

- [ ] **Step 3: Extend the diet audit service**

Append to `backend/app/services/hermes_datahub_diet_audit_service.py`:

```python

RUNTIME_SCAN_PATTERNS = (
    "backend/app/**/*.py",
    "backend/scripts/**/*.py",
    "backend/tests/**/*.py",
    "frontend/src/**/*.js",
    "frontend/src/**/*.vue",
    "frontend/tests/**/*.js",
)


def check_candidate_delete_paths(repo_root: str | Path, paths: Iterable[str]) -> dict:
    root = Path(repo_root)
    items = [_check_single_delete_candidate(root, str(path).replace("\\", "/")) for path in paths]
    return {
        "passed": all(item["status"] == "delete_allowed" for item in items),
        "items": items,
    }


def _check_single_delete_candidate(root: Path, clean_path: str) -> dict:
    lowered = clean_path.lower()
    if any(marker in lowered for marker in PROTECT_MARKERS):
        return {
            "path": clean_path,
            "status": "blocked",
            "reason": "protected_marker",
            "references": [],
        }
    full_path = root / clean_path
    if not full_path.exists():
        return {
            "path": clean_path,
            "status": "blocked",
            "reason": "candidate_missing",
            "references": [],
        }
    references = _runtime_references(root, clean_path)
    if references:
        return {
            "path": clean_path,
            "status": "blocked",
            "reason": "referenced_by_runtime_file",
            "references": references,
        }
    return {
        "path": clean_path,
        "status": "delete_allowed",
        "reason": "no_runtime_references",
        "references": [],
    }


def _runtime_references(root: Path, clean_path: str) -> list[str]:
    candidate = root / clean_path
    tokens = _reference_tokens(clean_path)
    references: list[str] = []
    for pattern in RUNTIME_SCAN_PATTERNS:
        for file_path in root.glob(pattern):
            if not file_path.is_file() or file_path == candidate:
                continue
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(token and token in text for token in tokens):
                references.append(str(file_path.relative_to(root)).replace("\\", "/"))
    return sorted(set(references))


def _reference_tokens(clean_path: str) -> tuple[str, ...]:
    path = Path(clean_path)
    stem = path.stem
    slash_path = clean_path.replace("\\", "/")
    without_ext = slash_path.rsplit(".", 1)[0]
    import_path = without_ext.replace("/", ".")
    vue_name = path.name if path.suffix == ".vue" else ""
    return tuple(token for token in (slash_path, without_ext, import_path, stem, vue_name) if token)
```

- [ ] **Step 4: Create CLI wrapper**

Create `backend/scripts/check_datahub_deletion_guard.py` with:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.hermes_datahub_diet_audit_service import check_candidate_delete_paths


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check datahub candidate deletes")
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = check_candidate_delete_paths(ROOT, args.paths)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in result["items"]:
            print(f"{item['status']} {item['path']} {item['reason']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run deletion guard tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_datahub_deletion_guard.py
```

Expected:

```text
4 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/hermes_datahub_diet_audit_service.py backend/scripts/check_datahub_deletion_guard.py backend/tests/test_datahub_deletion_guard.py
git commit -m "feat: add datahub deletion guard"
```

## Task 6: 管理端来源可见性检查

**Files:**
- Inspect: `frontend/src/router/index.js`
- Inspect: `frontend/src/views/manage/admin/AgentManagementPage.vue`
- Inspect: `frontend/tests/agentManagementPage.test.js`
- Modify only if the current page cannot show outbox logs or trace state.

- [ ] **Step 1: Verify current AI/communication management page contract**

Run:

```powershell
cd frontend
npm run test -- --run tests/agentManagementPage.test.js tests/channelManagementPage.test.js tests/aiAssistantUiContract.test.js
```

Expected:

```text
passed
```

- [ ] **Step 2: Inspect whether trace and outbox logs are already visible**

Run:

```powershell
rg -n "trace_id|traceId|追踪|outbox|logs|external" frontend/src/views/manage/admin/AgentManagementPage.vue frontend/src/api/agent-management.js frontend/tests/agentManagementPage.test.js
```

Expected:

```text
The output includes outbox dispatch, outbox logs, or trace-related fields.
```

- [ ] **Step 3: If the expected strings are missing, add a narrow frontend test**

Append to `frontend/tests/agentManagementPage.test.js`:

```javascript
test('agent management page exposes outbox logs and trace lookup affordance', () => {
  assert.match(apiSrc, /\/agent-management\/outbox\/\$\{outboxMessageId\}\/logs/)
  assert.match(pageSrc, /trace/i)
  assert.match(pageSrc, /outbox/i)
})
```

- [ ] **Step 4: Run frontend test**

Run:

```powershell
cd frontend
npm run test -- --run tests/agentManagementPage.test.js
```

Expected:

```text
passed
```

- [ ] **Step 5: Commit only if a frontend change was required**

```bash
git add frontend/src/views/manage/admin/AgentManagementPage.vue frontend/tests/agentManagementPage.test.js
git commit -m "test: lock agent trace visibility in management page"
```

If Step 2 already proves visibility and Step 3 is not needed, do not create an empty commit.

## Task 7: Final real gate run and report

**Files:**
- Create: `docs/superpowers/reports/2026-06-28-hermes-20-question-real-acceptance-report.md`
- Modify: `docs/datahub-deprecation-register.md` if deletion candidates are checked or removed.

- [ ] **Step 1: Run backend focused gate**

Run:

```powershell
cd backend
python -m pytest -q tests/test_hermes_20_question_real_acceptance.py tests/test_hermes_20_question_runner.py tests/test_hermes_real_dingtalk_delivery_gate.py tests/test_datahub_deletion_guard.py tests/test_hermes_mes_read_service.py tests/test_hermes_root_owner_production_orchestrator.py tests/test_hermes_fact_priority_service.py tests/test_dingtalk_agent_inbound_route.py
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 2: Run approved real DingTalk acceptance**

Before running, confirm the approved test group and personal DingTalk target are configured in `communication_channels` with `dry_run=False`.

Run:

```powershell
cd backend
python scripts/hermes_20_question_acceptance.py --business-date 2026-06-27 --sender-external-id dt-root-001 --target test-group --target dt-person-001 --real-delivery
```

Expected:

```text
The command writes docs/superpowers/reports/2026-06-28-hermes-20-question-real-acceptance-report.md.
Exit code is 0 only when core chain is 20/20 and real delivery passes the 18/20 + environment-failure rule.
```

- [ ] **Step 3: Run deletion guard before deleting any candidate**

For each delete candidate, run:

```powershell
cd backend
python scripts/check_datahub_deletion_guard.py path/to/candidate.py --json
```

Expected for deletion:

```json
{
  "passed": true,
  "items": [
    {
      "status": "delete_allowed"
    }
  ]
}
```

If output is `blocked`, do not delete that file. Add the blocked result to the final report.

- [ ] **Step 4: Delete only allowed candidates**

Use `apply_patch` to delete each allowed file. After every delete, run:

```powershell
rg -n "DeletedFileStem|DeletedFileName" backend frontend docs
```

Expected:

```text
No runtime references remain outside archive docs or the final report.
```

- [ ] **Step 5: Update datahub deprecation register**

Add rows to `docs/datahub-deprecation-register.md` for every checked candidate:

```markdown
| `path/to/candidate.py` | candidate_delete | guard passed, deleted in 20-question acceptance round | 已删除 | `git revert <commit>` |
| `path/to/blocked.py` | freeze | guard blocked by runtime reference | 7 到 14 天 | 保留文件 |
```

Use the actual paths and actual guard result from Step 3.

- [ ] **Step 6: Final verification**

Run:

```powershell
cd backend
python -m pytest -q tests/test_hermes_20_question_real_acceptance.py tests/test_hermes_20_question_runner.py tests/test_hermes_real_dingtalk_delivery_gate.py tests/test_datahub_deletion_guard.py tests/test_hermes_mes_read_service.py tests/test_hermes_root_owner_production_orchestrator.py tests/test_hermes_fact_priority_service.py tests/test_dingtalk_agent_inbound_route.py
cd ../frontend
npm run typecheck
cd ..
git diff --check
```

Expected:

```text
Backend selected tests pass.
Frontend typecheck passes when frontend files changed.
git diff --check has no errors.
```

- [ ] **Step 7: Commit final report and deletions**

```bash
git add docs/superpowers/reports/2026-06-28-hermes-20-question-real-acceptance-report.md docs/datahub-deprecation-register.md
git add -u
git commit -m "feat: run hermes 20 question real acceptance gate"
```

Only include deletion files that passed the guard and any source changes from prior tasks.

## Self-Review

Spec coverage:

- 20 问完整覆盖：Task 1 catalog and summary gate.
- 核心链路 20/20：Task 1 scoring and Task 7 final command.
- 钉钉真实外发 18/20 + 环境失败：Task 3 and Task 7.
- 钉钉、MES/WMS、数据中枢投影、DailyFactBundle、历史日报、未来能耗库状态：Task 1, Task 2, Task 4 source health hook.
- 中文身份和 `追踪编号`：Task 1 answer gate.
- RAG 不能当实时数字：Task 1 source gate.
- 删除旧服务代码前必须证明无依赖：Task 5 guard and Task 7 deletion flow.
- 管理端来源/trace 可见：Task 6.

Placeholder scan:

- No unresolved placeholders.
- No deferred implementation markers.
- No undefined test file paths.
- No task says “write tests” without concrete test code.

Type consistency:

- `AcceptanceTurnSnapshot` fields match tests and runner.
- `evaluate_question_snapshot()` and `evaluate_acceptance_summary()` are used consistently.
- `check_candidate_delete_paths()` return shape is the same in tests and CLI.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-28-hermes-20-question-real-acceptance-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
