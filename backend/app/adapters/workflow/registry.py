from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Mapping

from app.adapters.workflow.base import WorkflowPublisher
from app.adapters.workflow.null_publisher import NullWorkflowPublisher
from app.config import Settings


class WorkflowAdapterRegistry:
    def __init__(self, *, publishers: Sequence[WorkflowPublisher] | None = None, settings: Settings | None = None):
        default_publishers: list[WorkflowPublisher]
        if publishers is None:
            from app.adapters.wecom.group_bot import WeComGroupBotPublisher

            default_publishers = [NullWorkflowPublisher(), WeComGroupBotPublisher(settings=settings)]
        else:
            default_publishers = list(publishers)
        self._publishers: list[WorkflowPublisher] = list(
            default_publishers
        )

    def register(self, publisher: WorkflowPublisher) -> None:
        if any(existing.name == publisher.name for existing in self._publishers):
            return
        self._publishers.append(publisher)

    def resolve(self, workflow_event: Mapping[str, Any]) -> list[WorkflowPublisher]:
        return [publisher for publisher in self._publishers if publisher.supports(workflow_event)]

    def publisher_names(self) -> list[str]:
        return [publisher.name for publisher in self._publishers]
