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


def test_does_not_route_ordinary_messages_from_single_character_terms() -> None:
    for message in ("电影咋样", "少说两句"):
        plan = understand_root_owner_message(
            message,
            default_business_date=date(2026, 6, 27),
        )

        assert plan.domain == "general"
        assert plan.needs_clarification is True
        assert plan.clarification_question == "你想看生产、库存、能耗还是异常？"


def test_does_not_route_ordinary_missing_character_messages_to_anomaly() -> None:
    for message in ("缺觉了", "缺个人", "怎么还缺你"):
        plan = understand_root_owner_message(
            message,
            default_business_date=date(2026, 6, 27),
        )

        assert plan.domain == "general"
        assert plan.needs_clarification is True
        assert plan.clarification_question == "你想看生产、库存、能耗还是异常？"


def test_does_not_route_bare_why_messages_to_anomaly() -> None:
    for message in ("为什么还没下班", "为啥这样"):
        plan = understand_root_owner_message(
            message,
            default_business_date=date(2026, 6, 27),
        )

        assert plan.domain == "general"
        assert plan.needs_clarification is True
        assert plan.clarification_question == "你想看生产、库存、能耗还是异常？"


def test_date_words_without_business_intent_need_clarification() -> None:
    for message in ("今天吃啥", "昨天辛苦了", "现在方便吗"):
        plan = understand_root_owner_message(
            message,
            default_business_date=date(2026, 6, 27),
        )

        assert plan.domain == "general"
        assert plan.needs_clarification is True
        assert plan.clarification_question == "你想看生产、库存、能耗还是异常？"


def test_routes_business_missing_data_message_to_anomaly() -> None:
    plan = understand_root_owner_message(
        "今天日报缺数据吗",
        default_business_date=date(2026, 6, 27),
    )

    assert plan.domain == "anomaly"
    assert plan.intent == "anomaly_summary"
    assert "anomaly_explanation_daily" in plan.metric_keys
    assert plan.needs_clarification is False


def test_business_anchored_why_can_request_conflict_explanation() -> None:
    plan = understand_root_owner_message(
        "产量为什么对不上",
        default_business_date=date(2026, 6, 27),
    )

    assert plan.intent == "conflict_explanation"
    assert plan.needs_clarification is False


def test_understands_20_question_metric_phrases_without_hard_exact_sentence() -> None:
    cases = (
        ("今天成品率是多少？分子分母是什么？", "quality", ("daily_yield_rate",)),
        ("今天成本折算元/吨是多少？", "cost", ("cost_per_ton",)),
        ("今天在制料是多少？", "production", ("wip_total",)),
        ("现在总余合同量是多少？", "operations", ("remaining_contract_weight",)),
        ("本月累计产量是多少？", "operation_period", ("monthly_total_output",)),
        ("今年累计产量是多少？", "operation_period", ("annual_total_output",)),
        ("哪些数字来自专项责任人钉钉证据？", "evidence", ("dingtalk_specialist_evidence",)),
        ("今天哪个关键数字最不可信？", "anomaly", ("source_status",)),
        ("哪些指标缺少正式来源？", "anomaly", ("source_status",)),
        ("今天日报能不能自动生成？还缺什么？", "factory_overview", ("daily_report_readiness",)),
    )

    for message, expected_domain, expected_metrics in cases:
        plan = understand_root_owner_message(
            message,
            default_business_date=date(2026, 6, 27),
        )

        assert plan.domain == expected_domain, message
        assert plan.metric_keys == expected_metrics, message
        assert plan.needs_clarification is False, message
        assert "metric_phrase_match" in plan.recognition_reason


def test_output_inbound_conflict_is_anomaly_question() -> None:
    plan = understand_root_owner_message(
        "产量和入库为什么对不上？",
        default_business_date=date(2026, 6, 27),
    )

    assert plan.domain == "anomaly"
    assert plan.intent == "conflict_explanation"
    assert plan.metric_keys == ("total_output_daily", "finished_inbound_daily")


def test_explicit_metric_question_wins_over_previous_domain() -> None:
    plan = understand_root_owner_message(
        "产量和入库为什么对不上？",
        default_business_date=date(2026, 6, 27),
        previous_domain="energy",
    )

    assert plan.domain == "anomaly"
    assert plan.intent == "conflict_explanation"
    assert plan.metric_keys == ("total_output_daily", "finished_inbound_daily")
    assert "metric_phrase_match" in plan.recognition_reason


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


def test_date_only_follow_up_keeps_previous_domain_and_updates_date() -> None:
    cases = (
        ("今天呢", date(2026, 6, 27), "explicit_today"),
        ("昨天呢", date(2026, 6, 26), "explicit_yesterday"),
        ("前天呢", date(2026, 6, 25), "explicit_day_before_yesterday"),
    )

    for message, expected_date, expected_reason in cases:
        plan = understand_root_owner_message(
            message,
            default_business_date=date(2026, 6, 27),
            previous_domain="production",
        )

        assert plan.business_date == expected_date
        assert plan.domain == "production"
        assert plan.intent == "follow_up"
        assert plan.needs_clarification is False
        assert "context_follow_up" in plan.recognition_reason
        assert expected_reason in plan.recognition_reason


def test_previous_domain_does_not_make_broad_followups_business_questions() -> None:
    for message in ("为啥这样", "这个真不错", "那个先别发了", "刚才说啥"):
        plan = understand_root_owner_message(
            message,
            default_business_date=date(2026, 6, 27),
            previous_domain="production",
        )

        assert plan.domain == "general"
        assert plan.needs_clarification is True
        assert plan.clarification_question == "你想看生产、库存、能耗还是异常？"


def test_date_only_messages_without_previous_domain_need_clarification() -> None:
    for message in ("今天呢", "昨天呢", "前天呢"):
        plan = understand_root_owner_message(
            message,
            default_business_date=date(2026, 6, 27),
        )

        assert plan.domain == "general"
        assert plan.needs_clarification is True
        assert plan.clarification_question == "你想看生产、库存、能耗还是异常？"


def test_asks_short_clarification_when_message_is_not_business_question() -> None:
    plan = understand_root_owner_message(
        "给我讲个轻松笑话",
        default_business_date=date(2026, 6, 27),
    )

    assert plan.domain == "general"
    assert plan.needs_clarification is True
    assert plan.clarification_question == "你想看生产、库存、能耗还是异常？"
