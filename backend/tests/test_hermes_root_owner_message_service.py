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


def test_resolves_yesterday_for_colloquial_factory_overview() -> None:
    plan = understand_root_owner_message(
        "昨天咋样",
        default_business_date=date(2026, 6, 27),
    )

    assert plan.business_date == date(2026, 6, 26)
    assert plan.domain == "factory_overview"
    assert plan.needs_clarification is False
    assert "explicit_yesterday" in plan.recognition_reason


def test_resolves_day_before_yesterday_for_business_question() -> None:
    plan = understand_root_owner_message(
        "前天生产咋样",
        default_business_date=date(2026, 6, 27),
    )

    assert plan.business_date == date(2026, 6, 25)
    assert plan.domain == "production"
    assert plan.needs_clarification is False
    assert "explicit_day_before_yesterday" in plan.recognition_reason


def test_asks_short_date_clarification_for_ambiguous_time_expression() -> None:
    plan = understand_root_owner_message(
        "最近咋样",
        default_business_date=date(2026, 6, 27),
    )

    assert plan.business_date == date(2026, 6, 27)
    assert plan.needs_clarification is True
    assert plan.clarification_question == "你想看哪一天？"
    assert "ambiguous_time_expression" in plan.recognition_reason


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


def test_routes_inventory_question_separately_from_production() -> None:
    plan = understand_root_owner_message(
        "今天库存咋样",
        default_business_date=date(2026, 6, 27),
    )

    assert plan.business_date == date(2026, 6, 27)
    assert plan.domain == "inventory"
    assert plan.intent == "inventory_summary"
    assert "wip_total" in plan.metric_keys
    assert "remaining_contract_weight" in plan.metric_keys
    assert plan.needs_clarification is False


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
