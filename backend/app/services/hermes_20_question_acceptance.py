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
    required_source_health: tuple[str, ...] = ()


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
_DINGTALK_FACT_SOURCES = (
    "dingtalk_group_content",
    "dingtalk_group_chat",
    "dingtalk_group_file",
)
_NON_LANGUAGE_TOKENS = (
    "鑫泰铝业智能大脑",
    "来源",
    "状态",
    "追踪编号",
    "confirmed",
    "candidate",
    "missing",
    "conflict",
    "answer",
    "readonly",
    "read only",
    "trace",
    "mes/wms",
    "mes",
    "wms",
    "rag",
    ":",
    "：",
    ".",
    "。",
    ";",
    "；",
    ",",
    "，",
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
    total = len(catalog)
    snapshot_question_ids = [snapshot.question_id for snapshot in snapshots]
    has_complete_coverage = len(snapshot_question_ids) == total and set(snapshot_question_ids) == set(catalog)
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
    return AcceptanceSummary(
        core_passed=has_complete_coverage and core_pass_count == total,
        delivery_passed=has_complete_coverage
        and core_pass_count == total
        and delivery_success_count + environment_failure_count >= total
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
    metric_keys = set(_list_value(recognition.get("metric_keys")))
    if not any(metric_key in metric_keys for metric_key in question.metric_keys):
        return LayerGateResult("understanding", False, "metric_not_recognized")
    if recognition.get("domain") != question.domain:
        return LayerGateResult("understanding", False, "domain_not_recognized")
    if recognition.get("needs_clarification") is True:
        if _is_unfamiliar_dingtalk_wording_gap(snapshot):
            return LayerGateResult("understanding", True, "ok")
        return LayerGateResult("understanding", False, "needs_clarification")
    return LayerGateResult("understanding", True, "ok")


def _source_gate(question: HermesAcceptanceQuestion, snapshot: AcceptanceTurnSnapshot) -> LayerGateResult:
    evidence = snapshot.evidence or {}
    trace_value = evidence.get("trace")
    trace = trace_value if isinstance(trace_value, Mapping) else {}
    source_order = _list_value(trace.get("source_order"))
    source_status_value = trace.get("source_status")
    source_status = source_status_value if isinstance(source_status_value, Mapping) else {}
    checked_sources = set(source_order) | {str(source_key) for source_key in source_status}
    primary_source = str(evidence.get("primary_source") or "")
    if primary_source == "rag" or source_order[:1] == ["rag"]:
        return LayerGateResult("source", False, "rag_used_as_current_fact_source")
    if question.requires_dingtalk and not checked_sources.intersection(_DINGTALK_FACT_SOURCES):
        return LayerGateResult("source", False, "dingtalk_source_not_checked")
    if question.requires_mes and "mes_readonly" not in checked_sources:
        return LayerGateResult("source", False, "mes_readonly_not_checked")
    if not source_order and not source_status:
        return LayerGateResult("source", False, "no_real_source_trace")
    required_source_health_gate = _required_source_health_gate(snapshot)
    if required_source_health_gate is not None:
        return required_source_health_gate
    return LayerGateResult("source", True, "ok")


def _answer_gate(snapshot: AcceptanceTurnSnapshot) -> LayerGateResult:
    answer = str(snapshot.answer or "")
    if "鑫泰铝业智能大脑" not in answer or "追踪编号" not in answer:
        return LayerGateResult("answer", False, "public_identity_or_language_failed")
    if not _contains_meaningful_chinese(answer):
        return LayerGateResult("answer", False, "public_identity_or_language_failed")
    answer_casefolded = answer.casefold()
    if any(term.casefold() in answer_casefolded for term in _FORBIDDEN_PUBLIC_TERMS):
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


def _required_source_health_gate(snapshot: AcceptanceTurnSnapshot) -> LayerGateResult | None:
    for item in snapshot.required_source_health or ():
        key = str(item or "").strip()
        if not key:
            continue
        payload_value = (snapshot.source_health or {}).get(key)
        payload = payload_value if isinstance(payload_value, Mapping) else {}
        if not payload:
            return LayerGateResult("source", False, f"{key}_required_but_missing")
        status = str(payload.get("status") or "").strip().lower()
        if status not in {"ok", "pass", "passed", "ready", "confirmed"}:
            return LayerGateResult("source", False, f"{key}_not_passed")
    return None


def _is_unfamiliar_dingtalk_wording_gap(snapshot: AcceptanceTurnSnapshot) -> bool:
    recognition_reason = str((snapshot.recognition or {}).get("recognition_reason") or "")
    if "unfamiliar_dingtalk_wording" not in recognition_reason:
        return False
    evidence = snapshot.evidence or {}
    for key in ("actions", "pending_actions", "follow_up_actions"):
        if _has_action_items(evidence.get(key)):
            return True
    gap_plan = evidence.get("gap_plan")
    if isinstance(gap_plan, Mapping) and _has_action_items(gap_plan.get("items")):
        return True
    return False


def _has_action_items(value: Any) -> bool:
    if isinstance(value, Mapping):
        value = [value]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return False
    for item in value:
        if isinstance(item, Mapping) and any(item.get(key) for key in ("next_step", "action", "reason", "type")):
            return True
        if isinstance(item, str) and item.strip():
            return True
    return False


def _contains_meaningful_chinese(answer: str) -> bool:
    normalized = str(answer or "").casefold()
    for token in _NON_LANGUAGE_TOKENS:
        normalized = normalized.replace(token, "")
    return any("\u4e00" <= char <= "\u9fff" for char in normalized)


def _gate_text(gate: LayerGateResult) -> str:
    return "过" if gate.passed else gate.reason
