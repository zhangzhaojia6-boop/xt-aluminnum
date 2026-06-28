import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, ChatInboxMessage, MultimodalEvidence
from app.services.hermes_langchain_model import FactoryBrainModelUnavailable, invoke_factory_brain_model
from app.services.hermes_langchain_tools import (
    HermesToolAdapters,
    build_production_tool_adapters,
    build_tool_registry,
    require_tool,
)


def _fake_tool(**kwargs: object) -> dict[str, object]:
    return {'status': 'ok', 'request': kwargs}


def _db() -> Session:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
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
    Base.metadata.create_all(bind=engine, tables=[ChatInboxMessage.__table__, MultimodalEvidence.__table__])
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
