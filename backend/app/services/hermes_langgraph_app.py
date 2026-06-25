from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph


class FactoryBrainState(TypedDict, total=False):
    trace_id: str
    input_text: str
    actor_user_id: int | None
    channel: str
    status: str
    intent: dict[str, Any]
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


def _identify_actor(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'identify_actor', status='identified_actor')


def _classify_intent(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'classify_intent', intent={'intent_type': 'contextual_intent'})


def _load_soul_rules_knowledge(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'load_soul_rules_knowledge')


def _plan_task(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'plan_task')


def _route_tools(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'route_tools', tool_trace=[{'tool': 'hub_query', 'status': 'planned'}])


def _collect_evidence(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'collect_evidence')


def _reason_about_conflicts(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'reason_about_conflicts')


def _generate_response(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'generate_response', response_text='Hermes 已收到，我正在按工厂大脑链路处理。')


def _persist_memory_and_audit(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'persist_memory_and_audit')


def _reply_to_dingtalk(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'reply_to_dingtalk', status='replied')
