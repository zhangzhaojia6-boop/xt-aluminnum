from __future__ import annotations

from dataclasses import asdict, dataclass, field as dataclass_field
from datetime import date, datetime
from typing import Any, Mapping, Sequence

from app.domain.metric_contracts import (
    DAILY_REPORT_METRIC_CONTRACTS,
    fact_source_failure_reason,
    metric_unit_failure_reason,
    metric_value_failure_reason,
)
from app.services.hermes_fact_source_map_service import find_fact_source


@dataclass(frozen=True, slots=True)
class HermesAcceptanceQuestion:
    question_id: int
    question: str
    metric_keys: tuple[str, ...]
    domain: str
    requires_mes: bool
    requires_dingtalk: bool
    status_hint: str = "confirmed"
    utterance: str | None = None
    follow_up_utterances: tuple[str, ...] = ()
    default_business_date_offset_days: int = 0

    @property
    def execution_utterances(self) -> tuple[str, ...]:
        return (self.utterance or self.question, *self.follow_up_utterances)


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
    fact_answer: list[dict[str, Any]] = dataclass_field(default_factory=list)


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
    "开发者",
    "研发",
    "工程师",
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
CRITICAL_FIELDS = frozenset(
    {
        "total_output_daily",
        "finished_inbound_daily",
        "wip_total",
        "total_electricity_kwh",
        "daily_yield_rate",
    }
)
_DINGTALK_SOURCE_SET = frozenset(_DINGTALK_FACT_SOURCES)
_DISALLOWED_SOURCE_MARKERS = (
    "rag",
    "output_skill",
    "official_daily_report",
    "historical",
    "history_report",
    "computed",
    "reference_only",
)
_SOURCE_FAILURE_STATUSES = frozenset(
    {"", "failed", "error", "missing", "empty", "disabled", "unavailable", "unknown"}
)
_SOURCE_HEALTHY_STATUSES = frozenset({"ok", "ready", "pass", "passed", "confirmed"})
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
        HermesAcceptanceQuestion(
            1,
            "今天全厂总产量是多少？",
            ("total_output_daily",),
            "production",
            True,
            True,
            utterance="昨天一共出了多少？",
            default_business_date_offset_days=1,
        ),
        HermesAcceptanceQuestion(2, "今天各车间产量分别是多少？", ("workshop_output_daily",), "production", True, False),
        HermesAcceptanceQuestion(3, "今天成品入库多少？", ("finished_inbound_daily",), "inventory", True, True, utterance="那入库呢？"),
        HermesAcceptanceQuestion(4, "今天投料量是多少？", ("daily_input_weight",), "production", True, False),
        HermesAcceptanceQuestion(5, "今天高压总用电量是多少？", ("total_electricity_kwh",), "energy", False, True, utterance="电用了多少度，和群文件对得上吗"),
        HermesAcceptanceQuestion(6, "今天全厂用气量是多少？", ("total_gas_m3",), "energy", False, True),
        HermesAcceptanceQuestion(7, "今天吨电耗是多少？分母是什么？", ("electricity_per_ton",), "energy", True, False),
        HermesAcceptanceQuestion(8, "今天成品率是多少？分子分母是什么？", ("daily_yield_rate",), "quality", True, False, "candidate", utterance="成品率咋这么高，帮我查下是不是口径错了"),
        HermesAcceptanceQuestion(9, "今天成本折算元/吨是多少？", ("cost_per_ton",), "cost", False, False),
        HermesAcceptanceQuestion(10, "今天在制料是多少？", ("wip_total",), "production", True, False, "candidate"),
        HermesAcceptanceQuestion(11, "现在总余合同量是多少？", ("remaining_contract_weight",), "operations", True, False, "candidate"),
        HermesAcceptanceQuestion(12, "本月累计产量是多少？", ("monthly_total_output",), "operation_period", False, False),
        HermesAcceptanceQuestion(13, "今年累计产量是多少？", ("annual_total_output",), "operation_period", False, False, "candidate"),
        HermesAcceptanceQuestion(14, "今天有哪些异常说明？", ("anomaly_explanation_daily",), "anomaly", False, True),
        HermesAcceptanceQuestion(15, "哪些数字来自专项责任人钉钉证据？", ("dingtalk_specialist_evidence",), "evidence", False, True),
        HermesAcceptanceQuestion(16, "今天哪个关键数字最不可信？", ("source_status",), "anomaly", False, True, "candidate"),
        HermesAcceptanceQuestion(17, "产量和入库为什么对不上？", ("total_output_daily", "finished_inbound_daily"), "anomaly", True, True, "conflict"),
        HermesAcceptanceQuestion(18, "电耗升高可能由什么造成？", ("electricity_per_ton", "anomaly_explanation_daily"), "energy", True, True, "candidate", follow_up_utterances=("接着上一个问题，把证据编号给我",)),
        HermesAcceptanceQuestion(19, "哪些指标缺少正式来源？", ("source_status",), "anomaly", False, True, "missing"),
        HermesAcceptanceQuestion(20, "今天日报能不能自动生成？还缺什么？", ("daily_report_readiness",), "factory_overview", True, True, "candidate"),
    )


def answer_is_confirmed(answer: Mapping[str, Any]) -> bool:
    return _confirmed_failure_reason(answer) is None


def confirmed_fact_failure_reason(answer: Mapping[str, Any]) -> str | None:
    return _confirmed_failure_reason(answer)


def evaluate_answers(answers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return _evaluate_answers_for_questions(answers, build_20_question_catalog())


def _evaluate_answers_for_questions(
    answers: Sequence[Mapping[str, Any]],
    questions: Sequence[HermesAcceptanceQuestion],
) -> dict[str, Any]:
    expected = {question.question_id: question for question in questions}
    grouped: dict[int, list[Mapping[str, Any]]] = {}
    failures: list[dict[str, Any]] = []
    for answer in answers:
        if not isinstance(answer, Mapping):
            failures.append({"question_id": None, "field": None, "reason": "fact_answer_not_mapping"})
            continue
        question_id = _question_id(answer.get("question_id"))
        if question_id is None:
            failures.append({"question_id": None, "field": answer.get("field"), "reason": "question_id_invalid"})
            continue
        grouped.setdefault(question_id, []).append(answer)

    expected_ids = set(expected)
    coverage_passed = set(grouped) == expected_ids
    if not coverage_passed:
        failures.append(
            {
                "question_id": None,
                "field": None,
                "reason": "question_coverage_incomplete",
                "missing_question_ids": sorted(expected_ids - set(grouped)),
                "unexpected_question_ids": sorted(set(grouped) - expected_ids),
            }
        )

    critical_question_fields = {
        question.question_id: question.metric_keys[0]
        for question in questions
        if len(question.metric_keys) == 1 and question.metric_keys[0] in CRITICAL_FIELDS
    }
    required_critical_fields = set(critical_question_fields.values())
    critical_coverage = {field: False for field in sorted(required_critical_fields)}
    confirmed_count = 0
    for question_id, question in expected.items():
        records = grouped.get(question_id, [])
        expected_fields = set(question.metric_keys)
        actual_fields = {str(record.get("field") or "") for record in records}
        for field_name in sorted(expected_fields - actual_fields):
            failures.append(
                {"question_id": question_id, "field": field_name, "reason": "fact_field_missing"}
            )
        for field_name in question.metric_keys:
            matching = [record for record in records if record.get("field") == field_name]
            if len(matching) > 1:
                failures.append(
                    {"question_id": question_id, "field": field_name, "reason": "duplicate_fact_field"}
                )
            if not matching:
                continue
            record = matching[0]
            status = str(record.get("status") or "").strip().lower()
            if status == "confirmed":
                failure_reason = _confirmed_failure_reason(record)
                if failure_reason is None:
                    confirmed_count += 1
                    if critical_question_fields.get(question_id) == field_name:
                        critical_coverage[field_name] = True
                else:
                    failures.append(
                        {"question_id": question_id, "field": field_name, "reason": failure_reason}
                    )
                continue
            if critical_question_fields.get(question_id) == field_name:
                failures.append(
                    {
                        "question_id": question_id,
                        "field": field_name,
                        "reason": f"critical_field_not_confirmed:{status or 'missing'}",
                    }
                )
                continue
            contract = DAILY_REPORT_METRIC_CONTRACTS.get(field_name)
            if contract is None:
                failures.append(
                    {"question_id": question_id, "field": field_name, "reason": "metric_policy_missing"}
                )
                continue
            if status not in contract.allowed_non_confirmed_statuses:
                failures.append(
                    {
                        "question_id": question_id,
                        "field": field_name,
                        "reason": f"fact_status_not_allowed_by_metric_policy:{status or 'missing'}",
                    }
                )
                continue
            if contract.requires_non_confirmed_reason_action:
                for key in ("reason", "action"):
                    if not _specific_detail(record.get(key)):
                        failures.append(
                            {
                                "question_id": question_id,
                                "field": field_name,
                                "reason": f"{status}_{key}_missing_or_generic",
                            }
                        )

    return {
        "passed": coverage_passed and not failures and all(critical_coverage.values()),
        "confirmed_count": confirmed_count,
        "failures": failures,
        "critical_coverage": critical_coverage,
        "covered_question_count": len(expected_ids.intersection(grouped)),
        "expected_question_count": len(expected_ids),
    }


def _confirmed_failure_reason(answer: Mapping[str, Any]) -> str | None:
    if str(answer.get("status") or "").strip().lower() != "confirmed":
        return "status_not_confirmed"
    field_name = str(answer.get("field") or "").strip()
    contract = DAILY_REPORT_METRIC_CONTRACTS.get(field_name)
    if contract is None:
        return "metric_contract_missing"
    if not contract.confirmation_allowed:
        return contract.confirmed_failure_reason or "confirmed_not_allowed_by_metric_policy"
    value = answer.get("value")
    if _value_is_empty(value):
        return "value_missing"
    value_failure = metric_value_failure_reason(field_name, value)
    if value_failure is not None:
        return value_failure
    source_key = _normalized_source(answer.get("source_key"))
    if not source_key or _contains_disallowed_source_marker(source_key):
        return "source_key_missing_or_disallowed"
    source_type = _normalized_source(answer.get("source_type"))
    if _contains_disallowed_source_marker(source_type):
        return "source_type_missing_or_not_allowed"
    source_ref = answer.get("source_ref")
    if _value_is_empty(source_ref) or _contains_disallowed_source_marker(source_ref):
        return "source_ref_missing_or_disallowed"
    trace_id = str(answer.get("trace_id") or "").strip()
    if not trace_id:
        return "trace_id_missing"
    business_date = str(answer.get("business_date") or "").strip()
    business_window = str(answer.get("business_window") or "").strip()
    unit = str(answer.get("unit") or "").strip()
    metric_contract_version = str(answer.get("metric_contract_version") or "").strip()
    source_failure = fact_source_failure_reason(
        field_name,
        source_key=source_key,
        source_type=source_type,
        source_ref=source_ref,
        trace_id=trace_id,
        business_date=business_date,
        business_window=business_window,
        unit=unit,
        metric_contract_version=metric_contract_version,
    )
    if source_failure is not None:
        return source_failure
    if not business_date:
        return "business_date_missing"
    try:
        date.fromisoformat(business_date)
    except ValueError:
        return "business_date_invalid"
    if not business_window:
        return "business_window_missing"
    if not _business_window_matches_date(business_date, business_window):
        return "business_window_contract_mismatch"
    unit_failure = metric_unit_failure_reason(field_name, unit)
    if unit_failure is not None:
        return unit_failure
    if not metric_contract_version:
        return "metric_contract_version_missing"
    if metric_contract_version != contract.metric_contract_version:
        return "metric_contract_version_mismatch"
    return None


def _value_is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (str, bytes)):
        return not value.strip()
    if isinstance(value, (Mapping, Sequence, set, frozenset)):
        return len(value) == 0
    return False


def _contains_disallowed_source_marker(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return any(marker in normalized for marker in _DISALLOWED_SOURCE_MARKERS)


def _business_window_matches_date(business_date: str, business_window: str) -> bool:
    try:
        expected_date = date.fromisoformat(business_date)
        start_text, end_text = business_window.split("/", 1)
        start_at = datetime.fromisoformat(start_text)
        end_at = datetime.fromisoformat(end_text)
    except (TypeError, ValueError):
        return False
    return bool(
        start_at.tzinfo is not None
        and end_at.tzinfo is not None
        and end_at > start_at
        and start_at.date() == expected_date
    )


def _normalized_source(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    for char in (" ", "-", "/"):
        normalized = normalized.replace(char, "_")
    return normalized


def _unit_matches_field(field_name: str, unit: str) -> bool:
    return metric_unit_failure_reason(field_name, unit) is None


def _question_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    text = str(value or "").strip().lower()
    if text.startswith("q-"):
        text = text[2:]
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _specific_detail(value: Any) -> bool:
    text = str(value or "").strip()
    if len(text) < 6:
        return False
    return text.lower() not in {"missing", "conflict", "待处理", "请处理", "暂无数据", "缺少来源"}


def evaluate_question_snapshot(
    question: HermesAcceptanceQuestion,
    snapshot: AcceptanceTurnSnapshot,
) -> AcceptanceQuestionResult:
    gates = (
        _understanding_gate(question, snapshot),
        _source_gate(question, snapshot),
        _fact_gate(question, snapshot),
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
        and delivery_success_count == total
        and environment_failure_count == 0,
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
        "| 问题 | 理解 | 来源 | 事实 | 回答 | 钉钉 | 状态 |",
        "|---|---|---|---|---|---|---|",
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
                    _gate_text(gates["fact"]),
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
    candidate_sources = set(_list_value(evidence.get("candidate_sources")))
    if (
        _is_rag_like_source(primary_source)
        or (source_order and _is_rag_like_source(source_order[0]))
        or _only_rag_sources(checked_sources)
    ):
        return LayerGateResult("source", False, "rag_used_as_current_fact_source")
    if question.requires_dingtalk and not _required_source_is_usable(
        source_status,
        required_source="dingtalk_group_content",
        source_aliases=_DINGTALK_SOURCE_SET,
        primary_source=primary_source,
        candidate_sources=candidate_sources,
        supporting_evidence=trace.get("supporting_evidence"),
    ):
        return LayerGateResult("source", False, "dingtalk_source_not_usable")
    if question.requires_mes:
        mes_current_fact_is_usable = _required_source_is_usable(
            source_status,
            required_source="mes_readonly",
            source_aliases=frozenset({"mes_readonly"}),
            primary_source=primary_source,
            candidate_sources=candidate_sources,
            supporting_evidence=trace.get("supporting_evidence"),
        )
        priority_dingtalk_fact_is_usable = (
            _mes_was_checked_without_current_fact(source_status)
            and _healthy_dingtalk_source_was_checked(source_status)
            and _has_confirmed_priority_dingtalk_fact(question, snapshot)
        )
        verified_direct_mes_read_is_usable = _verified_nonempty_mes_read(source_status)
        if (
            not mes_current_fact_is_usable
            and not priority_dingtalk_fact_is_usable
            and not verified_direct_mes_read_is_usable
        ):
            return LayerGateResult("source", False, "mes_readonly_source_not_usable")
    if not source_order and not source_status:
        return LayerGateResult("source", False, "no_real_source_trace")
    required_source_health_gate = _required_source_health_gate(snapshot)
    if required_source_health_gate is not None:
        return required_source_health_gate
    return LayerGateResult("source", True, "ok")


def _fact_gate(question: HermesAcceptanceQuestion, snapshot: AcceptanceTurnSnapshot) -> LayerGateResult:
    recognition_business_date = str(
        (snapshot.recognition or {}).get("business_date") or ""
    ).strip()
    if recognition_business_date and any(
        isinstance(answer, Mapping)
        and str(answer.get("field") or "") in question.metric_keys
        and str(answer.get("status") or "").strip().lower() == "confirmed"
        and str(answer.get("business_date") or "").strip() != recognition_business_date
        for answer in snapshot.fact_answer or []
    ):
        return LayerGateResult("fact", False, "fact_business_date_mismatch")
    result = _evaluate_answers_for_questions(snapshot.fact_answer or [], (question,))
    if result["passed"]:
        return LayerGateResult("fact", True, "ok")
    reasons = list(dict.fromkeys(str(item.get("reason") or "fact_gate_failed") for item in result["failures"]))
    return LayerGateResult("fact", False, ";".join(reasons))


def _required_source_is_usable(
    source_status: Mapping[str, Any],
    *,
    required_source: str,
    source_aliases: frozenset[str],
    primary_source: str,
    candidate_sources: set[str],
    supporting_evidence: Any,
) -> bool:
    status_value = source_status.get(required_source)
    status_payload = status_value if isinstance(status_value, Mapping) else {}
    status = str(status_payload.get("status") or "").strip().lower()
    if status in _SOURCE_FAILURE_STATUSES:
        return False
    normalized_primary = _normalized_source(primary_source)
    normalized_candidates = {_normalized_source(item) for item in candidate_sources}
    has_candidate = normalized_primary in source_aliases or bool(normalized_candidates.intersection(source_aliases))
    if has_candidate:
        return True
    if isinstance(supporting_evidence, Mapping):
        supporting_evidence = [supporting_evidence]
    if not isinstance(supporting_evidence, Sequence) or isinstance(supporting_evidence, (str, bytes)):
        return False
    return any(
        isinstance(item, Mapping)
        and _normalized_source(item.get("source_key")) in source_aliases
        and str(item.get("status") or "").strip().lower() not in _SOURCE_FAILURE_STATUSES
        for item in supporting_evidence
    )


def _healthy_source_was_checked(source_status: Mapping[str, Any], source_key: str) -> bool:
    payload = source_status.get(source_key)
    if not isinstance(payload, Mapping):
        return False
    status = str(payload.get("status") or "").strip().lower()
    return status in _SOURCE_HEALTHY_STATUSES


def _mes_was_checked_without_current_fact(source_status: Mapping[str, Any]) -> bool:
    payload = source_status.get("mes_readonly")
    if not isinstance(payload, Mapping):
        return False
    status = str(payload.get("status") or "").strip().lower()
    reason = str(payload.get("reason") or "").strip().lower()
    return status == "ok" and reason == "no_current_metric_fact"


def _verified_nonempty_mes_read(source_status: Mapping[str, Any]) -> bool:
    payload = source_status.get("mes_readonly")
    if not isinstance(payload, Mapping):
        return False
    if str(payload.get("status") or "").strip().lower() in _SOURCE_FAILURE_STATUSES:
        return False
    source_errors = payload.get("source_errors")
    if isinstance(source_errors, Mapping) and source_errors:
        return False
    upstream = payload.get("source_status")
    if not isinstance(upstream, Mapping):
        return False
    if str(upstream.get("mes") or "").strip().lower() not in _SOURCE_HEALTHY_STATUSES:
        return False
    query_keys = _list_value(payload.get("query_keys"))
    sources = upstream.get("sources")
    if not query_keys or not isinstance(sources, Mapping):
        return False
    for query_key in query_keys:
        query_status = sources.get(query_key)
        if not isinstance(query_status, Mapping):
            return False
        if str(query_status.get("status") or "").strip().lower() not in _SOURCE_HEALTHY_STATUSES:
            return False
        try:
            record_count = int(query_status.get("count"))
        except (TypeError, ValueError):
            return False
        if record_count <= 0:
            return False
    return True


def _healthy_dingtalk_source_was_checked(source_status: Mapping[str, Any]) -> bool:
    return any(
        _healthy_source_was_checked(source_status, source_key)
        for source_key in _DINGTALK_FACT_SOURCES
    )


def _has_confirmed_priority_dingtalk_fact(
    question: HermesAcceptanceQuestion,
    snapshot: AcceptanceTurnSnapshot,
) -> bool:
    confirmed_answers = [
        answer
        for answer in snapshot.fact_answer or []
        if isinstance(answer, Mapping)
        and str(answer.get("field") or "") in question.metric_keys
        and _confirmed_failure_reason(answer) is None
    ]
    if not confirmed_answers:
        return False
    for answer in confirmed_answers:
        field_name = str(answer.get("field") or "")
        try:
            priority_sources = find_fact_source(field_name)["priority_sources"]
        except KeyError:
            return False
        if (
            not priority_sources
            or _normalized_source(priority_sources[0]) != "dingtalk_group_content"
            or _normalized_source(answer.get("source_key") or answer.get("source"))
            not in _DINGTALK_SOURCE_SET
        ):
            return False
    return True


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


def _only_rag_sources(sources: set[str]) -> bool:
    return bool(sources) and all(_is_rag_like_source(source) for source in sources)


def _is_rag_like_source(source: Any) -> bool:
    normalized = str(source or "").strip().lower()
    for char in (" ", "-", "/"):
        normalized = normalized.replace(char, "_")
    return normalized == "rag" or normalized.startswith("rag_") or normalized.endswith("_rag")


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
        if key == "daily_report_gate":
            fact_closure_value = payload.get("fact_closure")
            fact_closure = fact_closure_value if isinstance(fact_closure_value, Mapping) else {}
            alignment_value = payload.get("output_skill_alignment")
            alignment = alignment_value if isinstance(alignment_value, Mapping) else {}
            if str(fact_closure.get("status") or "").strip().lower() != "pass":
                return LayerGateResult("source", False, "daily_report_gate_fact_closure_not_passed")
            reference_mode = str(
                alignment.get("reference_mode") or payload.get("reference_mode") or ""
            ).strip().lower()
            reference_only = bool(alignment.get("reference_only") or payload.get("reference_only"))
            if reference_mode != "compare" or reference_only:
                return LayerGateResult("source", False, "daily_report_gate_not_compare_only")
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
        if isinstance(item, Mapping) and any(str(item.get(key) or "").strip() for key in ("next_step", "action")):
            return True
    return False


def _contains_meaningful_chinese(answer: str) -> bool:
    normalized = str(answer or "").casefold()
    for token in _NON_LANGUAGE_TOKENS:
        normalized = normalized.replace(token, "")
    return any("\u4e00" <= char <= "\u9fff" for char in normalized)


def _gate_text(gate: LayerGateResult) -> str:
    return "过" if gate.passed else gate.reason
