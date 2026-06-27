from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
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

_DOMAIN_CLARIFICATION_QUESTION = "你想看生产、库存、能耗还是异常？"
_DATE_CLARIFICATION_QUESTION = "你想看哪一天？"

_DOMAIN_TERMS = {
    "production": ("产量", "生产", "投料", "日报"),
    "inventory": ("库存", "成品库", "入库", "在制", "余合同", "合同余量", "余量"),
    "energy": ("能耗", "电耗", "用电", "电这块", "用气", "气耗", "吨电耗", "电"),
    "anomaly": ("异常", "对不上", "为什么", "为啥", "不一致", "差异", "缺", "少"),
}

_DOMAIN_INTENT = {
    "production": ("production_summary", ("total_output_daily", "workshop_output_daily", "daily_input_weight")),
    "inventory": ("inventory_summary", ("finished_inbound_daily", "wip_total", "remaining_contract_weight")),
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
    base_business_date = default_business_date or resolve_production_business_date()
    normalized, typo_changed = _normalize_text(raw_text)
    if not normalized:
        return RootOwnerMessagePlan(
            raw_text=raw_text,
            normalized_text=normalized,
            business_date=base_business_date,
            domain="general",
            intent="clarify",
            metric_keys=(),
            confidence=0.0,
            needs_clarification=True,
            clarification_question=_DOMAIN_CLARIFICATION_QUESTION,
            recognition_reason="empty_message",
        )

    if _has_ambiguous_time_expression(normalized):
        domain, score = max(_score_domains(normalized).items(), key=lambda item: item[1])
        metric_keys = _DOMAIN_INTENT[domain][1] if score > 0 else ()
        return RootOwnerMessagePlan(
            raw_text=raw_text,
            normalized_text=normalized,
            business_date=base_business_date,
            domain=domain if score > 0 else "general",
            intent="clarify",
            metric_keys=metric_keys,
            confidence=0.2,
            needs_clarification=True,
            clarification_question=_DATE_CLARIFICATION_QUESTION,
            recognition_reason=_join_reasons("ambiguous_time_expression", typo_changed),
        )

    business_date, date_reason = _resolve_business_date(normalized, base_business_date)

    if _looks_like_follow_up(normalized) and previous_domain in {"production", "inventory", "energy", "anomaly"}:
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
            recognition_reason=_join_reasons("context_follow_up", "soft_semantic_match", date_reason, typo_changed),
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
            recognition_reason=_join_reasons("soft_semantic_match", domain, date_reason, typo_changed),
        )

    if _has_any(normalized, ("今天", "昨天", "前天", "咋样", "怎么样", "现在", "今日", "昨日")):
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
            recognition_reason=_join_reasons("soft_default_today", date_reason, typo_changed),
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
        clarification_question=_DOMAIN_CLARIFICATION_QUESTION,
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


def _resolve_business_date(text: str, default_business_date: date) -> tuple[date, str]:
    if _has_any(text, ("前天",)):
        return default_business_date - timedelta(days=2), "explicit_day_before_yesterday"
    if _has_any(text, ("昨天", "昨日")):
        return default_business_date - timedelta(days=1), "explicit_yesterday"
    if _has_any(text, ("今天", "今日")):
        return default_business_date, "explicit_today"
    return default_business_date, ""


def _has_ambiguous_time_expression(text: str) -> bool:
    return _has_any(text, ("最近", "这几天", "这两天", "前几天", "这些天", "这段时间", "那天", "某天"))


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
