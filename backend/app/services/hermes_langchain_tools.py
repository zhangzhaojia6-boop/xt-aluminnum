from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping


ToolCallable = Callable[..., object]


@dataclass(frozen=True, slots=True)
class HermesToolAdapters:
    hub_query: ToolCallable
    mes_wms_read: ToolCallable
    dingtalk_evidence: ToolCallable
    rag_route: ToolCallable
    history_report: ToolCallable
    output_skill_alignment: ToolCallable
    long_term_rules: ToolCallable
    codex_construction: ToolCallable


def build_tool_registry(adapters: HermesToolAdapters) -> dict[str, ToolCallable]:
    return {
        'hub_query': adapters.hub_query,
        'mes_wms_read': adapters.mes_wms_read,
        'dingtalk_evidence': adapters.dingtalk_evidence,
        'rag_route': adapters.rag_route,
        'history_report': adapters.history_report,
        'output_skill_alignment': adapters.output_skill_alignment,
        'long_term_rules': adapters.long_term_rules,
        'codex_construction': adapters.codex_construction,
    }


def require_tool(name: str, registry: Mapping[str, ToolCallable]) -> ToolCallable:
    if name not in registry:
        raise ValueError(f'unregistered_hermes_tool:{name}')
    return registry[name]
