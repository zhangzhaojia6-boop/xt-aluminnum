from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.hermes_artifact_engine import plan_artifacts
from app.services.hermes_dingtalk_card_service import build_progress_card, build_progress_sequence
from app.services.hermes_factory_brain_intent_service import classify_factory_brain_intent
from app.services.hermes_factory_evidence_service import collect_factory_evidence, describe_evidence_gap
from app.services.hermes_factory_normalization_service import normalize_factory_request
from app.services.hermes_factory_task_planner import plan_factory_task


_HERMES_PUBLIC_NAME = '鑫泰铝业智能大脑'
_METRIC_LABELS = {
    'daily_output': '日产量',
    'monthly_output': '月累计产量',
    'inventory': '库存',
    'contract_balance': '合同余量',
    'yield_rate': '成品率',
    'energy_cost': '能耗成本',
    'anomaly': '异常',
    'monthly_operation': '月度经营',
    'yearly_operation': '年度经营',
    'artifact_request': '成果物请求',
    'daily_report': '日报',
}
_SOURCE_LABELS = {
    'dingtalk_group_content': '钉钉群文件和聊天内容',
    'dingtalk_specialist': '钉钉群文件和聊天内容',
    'mes': 'MES 只读来源',
    'wms': 'WMS 只读来源',
    'datahub': '数据中枢投影',
    'historical_report': '历史日报',
    'rag': '口径知识库',
}


class FactoryBrainState(TypedDict, total=False):
    trace_id: str
    input_text: str
    actor_user_id: int | None
    channel: str
    status: str
    intent: dict[str, Any]
    normalized_request: dict[str, Any]
    tool_plan: list[dict[str, Any]]
    data_references: list[dict[str, Any]]
    evidence_gap: str | None
    artifact_requests: list[dict[str, Any]]
    progress_cards: list[dict[str, Any]]
    tool_trace: list[dict[str, Any]]
    state_trace: list[str]
    response_text: str


def initial_factory_brain_state(
    *,
    trace_id: str,
    text: str,
    actor_user_id: int | None,
    channel: str,
) -> FactoryBrainState:
    return {
        'trace_id': trace_id,
        'input_text': text,
        'actor_user_id': actor_user_id,
        'channel': channel,
        'status': 'received',
        'tool_trace': [],
        'state_trace': ['received'],
    }


def build_factory_brain_graph(*, checkpointer: object | None):
    builder = StateGraph(FactoryBrainState)
    builder.add_node('identify_actor', _identify_actor)
    builder.add_node('classify_intent', _classify_intent)
    builder.add_node('load_soul_rules_knowledge', _load_soul_rules_knowledge)
    builder.add_node('plan_task', _plan_task)
    builder.add_node('route_tools', _route_tools)
    builder.add_node('collect_evidence', _collect_evidence)
    builder.add_node('reason_about_conflicts', _reason_about_conflicts)
    builder.add_node('generate_response', _generate_response)
    builder.add_node('persist_memory_and_audit', _persist_memory_and_audit)
    builder.add_node('reply_to_dingtalk', _reply_to_dingtalk)
    builder.add_edge(START, 'identify_actor')
    builder.add_edge('identify_actor', 'classify_intent')
    builder.add_edge('classify_intent', 'load_soul_rules_knowledge')
    builder.add_edge('load_soul_rules_knowledge', 'plan_task')
    builder.add_edge('plan_task', 'route_tools')
    builder.add_edge('route_tools', 'collect_evidence')
    builder.add_edge('collect_evidence', 'reason_about_conflicts')
    builder.add_edge('reason_about_conflicts', 'generate_response')
    builder.add_edge('generate_response', 'persist_memory_and_audit')
    builder.add_edge('persist_memory_and_audit', 'reply_to_dingtalk')
    builder.add_edge('reply_to_dingtalk', END)
    return builder.compile(checkpointer=checkpointer)


def _advance(state: FactoryBrainState, node: str, **extra: Any) -> FactoryBrainState:
    return {
        **state,
        **extra,
        'state_trace': [*list(state.get('state_trace') or []), node],
    }


def _json_safe(value: Any) -> Any:
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _identify_actor(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'identify_actor', status='identified_actor')


def _classify_intent(state: FactoryBrainState) -> FactoryBrainState:
    intent = classify_factory_brain_intent(str(state.get('input_text') or ''), today=date.today())
    return _advance(state, 'classify_intent', intent=_json_safe(asdict(intent)), status='intent_classified')


def _load_soul_rules_knowledge(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'load_soul_rules_knowledge')


def _plan_task(state: FactoryBrainState) -> FactoryBrainState:
    intent = classify_factory_brain_intent(str(state.get('input_text') or ''), today=date.today())
    normalized = normalize_factory_request(str(state.get('input_text') or ''), intent)
    plan = plan_factory_task(normalized)
    cards = [
        build_progress_card(progress)
        for progress in build_progress_sequence(
            trace_id=str(state.get('trace_id') or ''),
            title=f"{_HERMES_PUBLIC_NAME}正在处理：{str(state.get('input_text') or '').strip()}",
        )
    ]
    return _advance(
        state,
        'plan_task',
        normalized_request=_json_safe(asdict(normalized)),
        tool_plan=[_json_safe(asdict(step)) for step in plan],
        progress_cards=cards,
    )


def _route_tools(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'route_tools', tool_trace=list(state.get('tool_plan') or []))


def _collect_evidence(state: FactoryBrainState) -> FactoryBrainState:
    intent = classify_factory_brain_intent(str(state.get('input_text') or ''), today=date.today())
    normalized = normalize_factory_request(str(state.get('input_text') or ''), intent)
    plan = plan_factory_task(normalized)
    references = collect_factory_evidence(normalized, plan)
    gap = describe_evidence_gap(normalized, references)
    artifacts = plan_artifacts(normalized, references) if normalized.needs_artifact else []
    return _advance(
        state,
        'collect_evidence',
        data_references=[_json_safe(asdict(reference)) for reference in references],
        evidence_gap=gap,
        artifact_requests=[_json_safe(asdict(artifact)) for artifact in artifacts],
    )


def _reason_about_conflicts(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'reason_about_conflicts')


def _generate_response(state: FactoryBrainState) -> FactoryBrainState:
    references = list(state.get('data_references') or [])
    gap = state.get('evidence_gap')
    if not references and gap:
        response = f'{_HERMES_PUBLIC_NAME}暂时还不能确认结果。{gap}'
    else:
        metrics = '、'.join(_metric_label(reference.get('metric')) for reference in references)
        sources = '、'.join(sorted({_source_label(reference.get('source')) for reference in references}))
        response = f'{_HERMES_PUBLIC_NAME}已按现场证据链处理。指标：{metrics}。来源：{sources}。'
        if gap:
            response = f'{response}\n{gap}'
    return _advance(state, 'generate_response', response_text=response)


def _metric_label(value: object) -> str:
    text = str(value or '').strip()
    return _METRIC_LABELS.get(text, text)


def _source_label(value: object) -> str:
    text = str(value or '').strip()
    return _SOURCE_LABELS.get(text, text)


def _persist_memory_and_audit(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'persist_memory_and_audit')


def _reply_to_dingtalk(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'reply_to_dingtalk', status='replied')
