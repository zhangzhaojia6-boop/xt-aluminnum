from __future__ import annotations

import logging
from typing import Any, Mapping

from app.adapters.workflow.base import WorkflowDispatchEnvelope, WorkflowPublishResult


logger = logging.getLogger(__name__)


class NullWorkflowPublisher:
    name = 'null'

    def supports(self, workflow_event: Mapping[str, Any]) -> bool:
        return bool(workflow_event.get('event_type'))

    def publish(self, envelope: WorkflowDispatchEnvelope) -> WorkflowPublishResult:
        event_type = str(envelope.workflow_event.get('event_type') or envelope.realtime_event_type)
        logger.info('Workflow null publisher accepted %s via %s', event_type, envelope.dispatch_key)
        return WorkflowPublishResult(
            publisher=self.name,
            status='accepted',
            detail='captured by null publisher',
            metadata={
                'dispatch_key': envelope.dispatch_key,
                'event_type': event_type,
            },
        )
