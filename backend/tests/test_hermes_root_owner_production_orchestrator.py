from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.agent_communication import (
    AgentEvent,
    AgentOutboxMessage,
    AgentRun,
    ChatInboxMessage,
    ExternalMessageLog,
)
from app.models.system import User
from app.services.hermes_root_owner_evidence_service import EvidenceCandidate, EvidenceDecision
from app.services.hermes_root_owner_message_service import understand_root_owner_message
from app.services.hermes_root_owner_production_orchestrator import (
    _build_natural_answer,
    _evidence_payload,
    run_root_owner_production_turn,
)


_FORBIDDEN_PUBLIC_IDENTITY_TERMS = ("Codex", "Factory Brain", "root_owner", "trace_id", "developer", "engineer")


def _db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def _new_session_from(bind) -> Session:
    return Session(bind)


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
        value={"total_output_daily": 118.0, "token": "primary-secret-token"},
        summary="负责人群里确认 118 吨",
        trace_ref={"trace_id": "trace-ding-001", "password": "primary-secret-password"},
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
        message = _db.get(AgentOutboxMessage, outbox_message_id)
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
        assert "鑫泰铝业智能大脑" in result.answer
        assert "全厂总产量：118 吨" in result.answer
        assert "事实追踪：trace-ding-001" in result.answer
        assert "钉钉" in result.answer
        assert "追踪编号" in result.answer
        for token in _FORBIDDEN_PUBLIC_IDENTITY_TERMS:
            assert token not in result.answer
        assert result.dispatch_status == "sent"
        assert sent == [result.outbox_message_id]

        inbox = db.query(ChatInboxMessage).one()
        assert inbox.channel == "dingtalk_private"

        bind = db.get_bind()
        db.close()
        reread_db = _new_session_from(bind)
        try:
            run = reread_db.query(AgentRun).one()
            payload = run.result_payload
            assert run.trace_id == "trace-root-turn-001"
            assert payload["source"]["source"] == "dingtalk_inbound"
            assert payload["source"]["root_owner_private_loop"] is True
            assert payload["source"]["recognition_reason"]
            assert payload["source"]["source_payload"]["source"] == "test"
            assert payload["evidence"]["primary_source"] == "dingtalk_group_chat"
            assert payload["evidence"]["primary"] == {
                "source_key": "dingtalk_group_chat",
                "source_type": "dingtalk_group_content",
                "status": "ok",
                "value": {"total_output_daily": 118.0},
                "trace_ref": {"trace_id": "trace-ding-001"},
            }
            assert "primary-secret-token" not in repr(payload)
            assert "primary-secret-password" not in repr(payload)
            assert payload["recognition"]["domain"] == "production"
            assert payload["dispatch"]["outbox_message_id"] == result.outbox_message_id
            assert payload["dispatch"]["status"] == "sent"
            assert payload["dispatch"]["detail"] == "sent"
        finally:
            reread_db.close()
    finally:
        db.close()


def test_machine_turn_reads_direct_mes_and_explains_record_semantics(monkeypatch) -> None:
    db = _db_session()
    db.add(_root_owner())
    db.commit()

    class MesReader:
        def read_sources(self, *, business_date, query_keys):
            assert business_date == date(2026, 7, 21)
            assert query_keys == ['workshop_process_records']
            return {
                'records': {
                    'workshop_process_records': [
                        {
                            'source_id': 'mes-operation-2-20260721',
                            'event_time': '2026-07-21T12:30:00+08:00',
                            'metadata': {
                                'DeviceName': '2号机',
                                'WorkShopName': '热轧车间',
                                'ProcessName': '热轧',
                                'BeginDatetime': '2026-07-21T08:00:00+08:00',
                                'EndDatetime': '2026-07-21T12:30:00+08:00',
                                'WorkerName': '不得进入回答',
                            },
                        },
                    ],
                },
                'source_status': {
                    'mes': 'ok',
                    'sources': {'workshop_process_records': {'status': 'ok', 'count': 1}},
                },
                'source_errors': {},
            }

    monkeypatch.setattr(
        'app.services.hermes_root_owner_production_orchestrator.agent_communication_service.dispatch_outbox_message',
        lambda _db, outbox_message_id, *, sender=None: SimpleNamespace(
            status='sent',
            detail='sent',
            outbox_message_id=outbox_message_id,
        ),
    )

    try:
        result = run_root_owner_production_turn(
            db,
            text='7月21日2号机几点开、几点停？',
            current_user=db.get(User, 1),
            sender_external_id='dt-root-001',
            trace_id='trace-root-machine-operation',
            source_payload={'source': 'test'},
            default_business_date=date(2026, 7, 29),
            mes_reader=MesReader(),
        )

        assert result.status == 'answered'
        assert '2号机 08:00 至 12:30，历时 270 分钟' in result.answer
        assert '不等同于设备物理开关机或通断电' in result.answer
        assert 'MES 只读库' in result.answer
        assert '不得进入回答' not in result.answer
        assert db.query(AgentEvent).count() == 0
        run = db.query(AgentRun).one()
        assert run.result_payload['recognition']['domain'] == 'machine'
        assert run.result_payload['evidence']['primary_source'] == 'mes_readonly'
        assert '不得进入回答' not in repr(run.result_payload)
    finally:
        db.close()


def test_machine_turn_marks_incomplete_mes_times_partial_and_opens_recheck(monkeypatch) -> None:
    db = _db_session()
    db.add(_root_owner())
    db.commit()

    class PartialMesReader:
        def read_sources(self, *, business_date, query_keys):
            return {
                'records': {
                    'workshop_process_records': [
                        {
                            'source_id': 'mes-operation-partial-2-20260721',
                            'metadata': {
                                'DeviceName': '2号机',
                                'WorkShopName': '热轧车间',
                                'ProcessName': '热轧',
                                'EndDatetime': '2026-07-21T12:30:00+08:00',
                            },
                        },
                    ],
                },
                'source_status': {'mes': 'ok'},
                'source_errors': {},
            }

    monkeypatch.setattr(
        'app.services.hermes_root_owner_production_orchestrator.agent_communication_service.dispatch_outbox_message',
        lambda _db, outbox_message_id, *, sender=None: SimpleNamespace(
            status='sent',
            detail='sent',
            outbox_message_id=outbox_message_id,
        ),
    )

    try:
        result = run_root_owner_production_turn(
            db,
            text='7月21日2号机几点开、几点停？',
            current_user=db.get(User, 1),
            sender_external_id='dt-root-001',
            trace_id='trace-root-machine-operation-partial',
            source_payload={'source': 'test'},
            default_business_date=date(2026, 7, 29),
            mes_reader=PartialMesReader(),
        )

        assert '生产起止时间不完整' in result.answer
        assert '状态：partial' in result.answer
        assert '不等同于物理通断电' in result.answer
        event = db.query(AgentEvent).one()
        assert event.status == 'open'
        assert event.payload['fill_strategy'] == 'mes_source_recheck'
        run = db.query(AgentRun).one()
        assert run.result_payload['evidence']['primary_source'] is None
    finally:
        db.close()


def test_natural_answer_renders_confirmed_fact_value_unit_and_source_trace() -> None:
    plan = understand_root_owner_message(
        "今天高压总用电量是多少？",
        default_business_date=date(2026, 7, 21),
    )
    primary = EvidenceCandidate(
        source_key="data_hub_projection",
        source_type="data_hub",
        domain="energy",
        priority=40,
        status="ok",
        value={
            "total_electricity_kwh": {
                "value": 145000.0,
                "unit": "kWh",
                "source_type": "manual_workbook",
                "trace_id": "import-read:import_rows:44:total_electricity_kwh:921",
            }
        },
        summary="数据中枢投影已读取当前指标",
        trace_ref={"source": "daily_fact_bundle", "status": "ok"},
    )
    decision = EvidenceDecision(
        primary=primary,
        candidates=(primary,),
        conflicts=(),
        missing_sources=[],
        trace={"trace_id": "hermes-20q-2026-07-21-05"},
    )

    answer = _build_natural_answer(plan=plan, decision=decision)

    assert "145000" in answer
    assert "kWh" in answer
    assert "事实来源：导入原始工作簿" in answer
    assert "import-read:import_rows:44:total_electricity_kwh:921" in answer


def test_private_evidence_follow_up_recovers_previous_production_fact_context(monkeypatch) -> None:
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
        summary="群里确认生产口径 118 吨",
        trace_ref={"trace_id": "trace-ding-follow-up"},
    )
    decision = EvidenceDecision(
        primary=primary,
        candidates=(primary,),
        conflicts=(),
        missing_sources=[],
        trace={"source_order": ["dingtalk_group_chat"]},
    )
    seen_plans = []

    def fake_collect(_db, *, message_plan, trace_id, mes_reader=None):
        seen_plans.append(
            (
                trace_id,
                message_plan.raw_text,
                message_plan.domain,
                message_plan.metric_keys,
                message_plan.intent,
                message_plan.business_date,
            )
        )
        return decision

    monkeypatch.setattr(
        "app.services.hermes_root_owner_production_orchestrator.collect_root_owner_evidence",
        fake_collect,
    )
    monkeypatch.setattr(
        "app.services.hermes_root_owner_production_orchestrator.agent_communication_service.dispatch_outbox_message",
        lambda _db, outbox_message_id, *, sender=None: SimpleNamespace(
            status="sent",
            detail="sent",
            outbox_message_id=outbox_message_id,
        ),
    )

    try:
        stale = run_root_owner_production_turn(
            db,
            text="昨天一共出了多少？",
            current_user=db.get(User, 1),
            sender_external_id="dt-root-001",
            trace_id="trace-root-turn-first",
            source_payload={},
            default_business_date=date(2026, 6, 27),
            context_scope_id="acceptance-run-stale",
        )
        first = run_root_owner_production_turn(
            db,
            text="今天一共出了多少？",
            current_user=db.get(User, 1),
            sender_external_id="dt-root-001",
            trace_id="trace-root-turn-current",
            source_payload={},
            default_business_date=date(2026, 6, 27),
            context_scope_id="acceptance-run-current",
        )
        second = run_root_owner_production_turn(
            db,
            text="接着上一个问题，把证据编号给我",
            current_user=db.get(User, 1),
            sender_external_id="dt-root-001",
            trace_id="trace-root-turn-follow-up",
            source_payload={},
            default_business_date=date(2026, 6, 27),
            context_scope_id="acceptance-run-current",
        )

        assert stale.status == "answered"
        assert first.status == "answered"
        assert second.status == "answered"
        assert seen_plans == [
            (
                "trace-root-turn-first",
                "昨天一共出了多少？",
                "production",
                ("total_output_daily",),
                "production_summary",
                date(2026, 6, 26),
            ),
            (
                "trace-root-turn-current",
                "今天一共出了多少？",
                "production",
                ("total_output_daily",),
                "production_summary",
                date(2026, 6, 27),
            ),
            (
                "trace-root-turn-follow-up",
                "接着上一个问题，把证据编号给我",
                "production",
                ("total_output_daily",),
                "evidence_follow_up",
                date(2026, 6, 27),
            ),
        ]

        follow_up_run = (
            db.query(AgentRun)
            .filter(AgentRun.trace_id == "trace-root-turn-follow-up")
            .one()
        )
        recognition = follow_up_run.result_payload["recognition"]
        assert recognition["domain"] == "production"
        assert recognition["metric_keys"] == ["total_output_daily"]
        assert recognition["business_date"] == "2026-06-27"
        assert recognition["intent"] == "evidence_follow_up"
        assert recognition["needs_clarification"] is False
        assert "context_follow_up" in recognition["recognition_reason"]
        assert follow_up_run.result_payload["evidence"]["primary_source"] == "dingtalk_group_chat"
    finally:
        db.close()


def test_evidence_payload_keeps_ordered_sanitized_candidate_facts() -> None:
    first = EvidenceCandidate(
        source_key="dingtalk_group_chat",
        source_type="dingtalk_group_content",
        domain="production",
        priority=10,
        status="ok",
        value={"daily_input_weight": 560.0, "api_token": "must-not-persist"},
        summary="钉钉投料事实",
        trace_ref={"trace_id": "ding-71"},
    )
    second = EvidenceCandidate(
        source_key="data_hub_projection",
        source_type="mes_packaging_output",
        domain="production",
        priority=40,
        status="ok",
        value={"total_output_daily": 286.0},
        summary="MES 投影产量事实",
        trace_ref={"trace_id": "projection-118"},
    )

    payload = _evidence_payload(
        EvidenceDecision(
            primary=first,
            candidates=(first, second),
            conflicts=(),
            missing_sources=[],
            trace={},
        )
    )

    assert [candidate["source_key"] for candidate in payload["candidate_facts"]] == [
        "dingtalk_group_chat",
        "data_hub_projection",
    ]
    assert payload["candidate_facts"][0]["value"]["daily_input_weight"] == 560.0
    assert "api_token" not in repr(payload)


def test_turn_asks_short_clarification_for_unclear_message(monkeypatch) -> None:
    db = _db_session()
    db.add(_root_owner())
    db.commit()
    monkeypatch.setattr(
        "app.services.hermes_root_owner_production_orchestrator.agent_communication_service.dispatch_outbox_message",
        lambda _db, outbox_message_id, *, sender=None: SimpleNamespace(
            status="sent",
            detail="sent",
            outbox_message_id=outbox_message_id,
        ),
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
        assert result.answer == "鑫泰铝业智能大脑需要先确认：你想看生产、库存、能耗还是异常？"
        for token in _FORBIDDEN_PUBLIC_IDENTITY_TERMS:
            assert token not in result.answer
        bind = db.get_bind()
        db.close()
        reread_db = _new_session_from(bind)
        try:
            run = reread_db.query(AgentRun).one()
            payload = run.result_payload
            assert payload["source"]["source"] == "dingtalk_inbound"
            assert payload["source"]["root_owner_private_loop"] is True
            assert payload["recognition"]["needs_clarification"] is True
            assert payload["evidence"]["primary_source"] is None
            assert payload["dispatch"]["outbox_message_id"] == result.outbox_message_id
            assert payload["dispatch"]["status"] == "sent"
            assert payload["dispatch"]["detail"] == "sent"
        finally:
            reread_db.close()
    finally:
        db.close()


def test_turn_reuses_precommitted_ingress_inbox(monkeypatch) -> None:
    db = _db_session()
    db.add(_root_owner())
    inbox = ChatInboxMessage(
        channel='dingtalk_private',
        group_id=None,
        sender_external_id='dt-root-001',
        text='给我讲个轻松笑话',
        agent_code='factory_dispatch',
        trace_id='trace-root-ingress-reuse',
        source_payload={'source': 'dingtalk_inbound'},
    )
    db.add(inbox)
    db.commit()
    monkeypatch.setattr(
        'app.services.hermes_root_owner_production_orchestrator.agent_communication_service.dispatch_outbox_message',
        lambda _db, outbox_message_id, *, sender=None: SimpleNamespace(
            status='sent',
            detail='sent',
            outbox_message_id=outbox_message_id,
        ),
    )

    try:
        result = run_root_owner_production_turn(
            db,
            text='给我讲个轻松笑话',
            current_user=db.get(User, 1),
            sender_external_id='dt-root-001',
            trace_id='trace-root-ingress-reuse',
            source_payload={'messageId': 'msg-root-ingress'},
            default_business_date=date(2026, 6, 27),
            chat_inbox=inbox,
        )

        assert result.chat_inbox_id == inbox.id
        assert db.query(ChatInboxMessage).count() == 1
        db.refresh(inbox)
        assert inbox.source_payload['root_owner_private_loop'] is True
        assert inbox.source_payload['recognition_reason']
    finally:
        db.close()
