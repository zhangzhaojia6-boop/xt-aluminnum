from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class WorkflowDispatchEnvelope:
    dispatch_key: str
    realtime_event_id: int | None
    realtime_event_type: str
    realtime_event: Mapping[str, Any]
    workflow_event: Mapping[str, Any]
    attempt: int = 1


@dataclass(frozen=True, slots=True)
class WorkflowPublishResult:
    publisher: str
    status: str
    detail: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class WorkflowPublisher(Protocol):
    name: str

    def supports(self, workflow_event: Mapping[str, Any]) -> bool: ...

    def publish(self, envelope: WorkflowDispatchEnvelope) -> WorkflowPublishResult: ...
