from typing import cast

import httpx
from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, ChatInboxMessage, MultimodalEvidence
from app.services.hermes_langchain_model import FactoryBrainModelUnavailable, invoke_factory_brain_model
from app.services.hermes_langchain_tools import (
    HermesToolAdapters,
    ToolResult,
    build_production_tool_adapters,
    build_tool_registry,
    require_tool,
)


_DINGTALK_TABLES: tuple[Table, Table] = (
    cast(Table, ChatInboxMessage.__table__),
    cast(Table, MultimodalEvidence.__table__),
)


def _fake_tool(**kwargs: object) -> ToolResult:
    return {'status': 'ok', 'request': kwargs}


def _db() -> Session:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    return Session(engine)


def _dingtalk_db() -> Session:
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine, tables=_DINGTALK_TABLES)
    return Session(engine)


def test_tool_registry_exposes_only_allowed_tools() -> None:
    adapters = HermesToolAdapters(
        hub_query=_fake_tool,
        mes_wms_read=_fake_tool,
        dingtalk_evidence=_fake_tool,
        rag_route=_fake_tool,
        history_report=_fake_tool,
        output_skill_alignment=_fake_tool,
        long_term_rules=_fake_tool,
        codex_construction=_fake_tool,
        source_map=_fake_tool,
    )
    registry = build_tool_registry(adapters)

    assert set(registry.keys()) == {
        'hub_query',
        'mes_wms_read',
        'dingtalk_evidence',
        'rag_route',
        'history_report',
        'output_skill_alignment',
        'long_term_rules',
        'codex_construction',
        'source_map',
    }
    assert require_tool('hub_query', registry)(business_date='2026-06-25')['status'] == 'ok'


def test_source_map_tool_explains_metric_source() -> None:
    registry = build_tool_registry(build_production_tool_adapters(_db()))

    result = registry['source_map'](metric_key='total_output_daily')

    assert result['status'] == 'ok'
    assert result['source'] == 'fact_source_map'
    assert result['facts']['metric_key'] == 'total_output_daily'
    assert '车间总产量' in result['facts']['summary']


def test_model_401_becomes_degraded_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={'error': {'message': 'Codex token refresh failed with status 401'}})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    try:
        invoke_factory_brain_model(
            messages=[{'role': 'user', 'content': '在干嘛'}],
            api_base='https://example.invalid',
            api_key='expired',
            model='codex-temp',
            client=client,
        )
    except FactoryBrainModelUnavailable as exc:
        assert exc.user_message == '模型服务暂不可用，Hermes 已降级为只读数据查询模式。'
    else:
        raise AssertionError('expected FactoryBrainModelUnavailable')


def test_hub_query_tool_returns_structured_payload() -> None:
    registry = build_tool_registry(build_production_tool_adapters(_db()))

    result = registry['hub_query'](business_date='2026-06-25', query_type='production')

    assert 'status' in result
    assert 'source' in result
    assert result['source'] == 'data_hub'
    assert 'request' in result
    assert 'facts' in result


def test_dingtalk_evidence_tool_returns_group_content_priority_first() -> None:
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine, tables=_DINGTALK_TABLES)
    db = Session(engine)
    try:
        db.add(
            ChatInboxMessage(
                channel='dingtalk_group',
                group_id='group-001',
                sender_external_id='dt-leader',
                text='负责人确认今天产量 118 吨',
                agent_code='factory_dispatch',
                trace_id='trace-dingtalk-chat',
                source_payload={'source': 'dingtalk'},
            )
        )
        db.add(
            MultimodalEvidence(
                evidence_type='file',
                recognized_text='群文件确认今天产量 118 吨',
                confirmation_status='confirmed',
                payload={'source': 'dingtalk', 'channel': 'dingtalk_group'},
            )
        )
        db.commit()

        tool = build_production_tool_adapters(db).dingtalk_evidence
        payload = tool(limit=10)

        assert payload['status'] == 'ok'
        assert payload['source'] == 'dingtalk_group_content'
        assert payload['facts'][0]['source_key'] in {'dingtalk_group_file', 'dingtalk_group_chat'}
        assert payload['facts'][0]['priority'] == 10
    finally:
        db.close()


def test_dingtalk_evidence_tool_filters_non_dingtalk_multimodal_rows() -> None:
    db = _dingtalk_db()
    try:
        db.add_all(
            [
                MultimodalEvidence(
                    evidence_type='file',
                    recognized_text='邮件附件不应该进入钉钉证据',
                    payload={'source': 'email', 'channel': 'mailbox'},
                ),
                MultimodalEvidence(
                    evidence_type='attachment',
                    recognized_text='群附件确认今天产量 118 吨',
                    file_uri='dingtalk://media/file-001',
                    payload={'source': 'dingtalk', 'channel': 'dingtalk_group'},
                ),
            ]
        )
        db.commit()

        payload = build_production_tool_adapters(db).dingtalk_evidence(limit=10)

        assert [fact['recognized_text'] for fact in payload['facts']] == ['群附件确认今天产量 118 吨']
        assert payload['facts'][0]['evidence_type'] == 'attachment'
    finally:
        db.close()


def test_dingtalk_evidence_tool_returns_dingtalk_file_evidence_type() -> None:
    db = _dingtalk_db()
    try:
        db.add(
            MultimodalEvidence(
                evidence_type='dingtalk_file',
                recognized_text='钉钉文件确认天然气 50578m3',
                file_uri='dingtalk://gas/2026-06-19.xlsx',
                payload={'business_date': '2026-06-19'},
            )
        )
        db.commit()

        payload = build_production_tool_adapters(db).dingtalk_evidence(limit=10)

        assert len(payload['facts']) == 1
        assert payload['facts'][0]['source_key'] == 'dingtalk_group_file'
        assert payload['facts'][0]['evidence_type'] == 'dingtalk_file'
    finally:
        db.close()


def test_dingtalk_evidence_tool_maps_dingtalk_text_to_group_chat_source() -> None:
    db = _dingtalk_db()
    try:
        db.add(
            MultimodalEvidence(
                evidence_type='dingtalk_text',
                recognized_text='钉钉文字确认今天产量 118 吨',
                payload={'business_date': '2026-06-19'},
            )
        )
        db.commit()

        payload = build_production_tool_adapters(db).dingtalk_evidence(limit=10)

        assert len(payload['facts']) == 1
        assert payload['facts'][0]['source_key'] == 'dingtalk_group_chat'
        assert payload['facts'][0]['recognized_text'] == '钉钉文字确认今天产量 118 吨'
    finally:
        db.close()


def test_dingtalk_evidence_tool_limit_prefers_group_chat_before_file() -> None:
    db = _dingtalk_db()
    try:
        db.add(
            ChatInboxMessage(
                channel='dingtalk_group',
                group_id='group-001',
                sender_external_id='dt-leader',
                text='群聊文字确认今天产量 118 吨',
                agent_code='factory_dispatch',
                trace_id='trace-dingtalk-chat',
                source_payload={'source': 'dingtalk'},
            )
        )
        db.add(
            MultimodalEvidence(
                evidence_type='file',
                recognized_text='群文件确认今天产量 118 吨',
                confirmation_status='confirmed',
                payload={'source': 'dingtalk', 'channel': 'dingtalk_group'},
            )
        )
        db.commit()

        payload = build_production_tool_adapters(db).dingtalk_evidence(limit=1)

        assert len(payload['facts']) == 1
        assert payload['facts'][0]['source_key'] == 'dingtalk_group_chat'
        assert payload['facts'][0]['text'] == '群聊文字确认今天产量 118 吨'
    finally:
        db.close()


def test_dingtalk_evidence_tool_limit_sorts_image_after_text_and_file() -> None:
    db = _dingtalk_db()
    try:
        db.add_all(
            [
                MultimodalEvidence(
                    evidence_type='image',
                    recognized_text='截图里的产量 118 吨',
                    file_uri='dingtalk://image/newest',
                    payload={'source': 'dingtalk'},
                ),
                MultimodalEvidence(
                    evidence_type='file',
                    recognized_text='群文件确认今天产量 118 吨',
                    file_uri='dingtalk://file/middle',
                    payload={'source': 'dingtalk'},
                ),
                MultimodalEvidence(
                    evidence_type='dingtalk_text',
                    recognized_text='钉钉文字确认今天产量 118 吨',
                    payload={'business_date': '2026-06-19'},
                ),
            ]
        )
        db.commit()

        payload = build_production_tool_adapters(db).dingtalk_evidence(limit=2)

        assert [fact['recognized_text'] for fact in payload['facts']] == [
            '钉钉文字确认今天产量 118 吨',
            '群文件确认今天产量 118 吨',
        ]
    finally:
        db.close()
