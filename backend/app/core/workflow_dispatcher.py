from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import json
import logging
from threading import Lock
from typing import Any, Mapping

from app.adapters.workflow import WorkflowAdapterRegistry, WorkflowDispatchEnvelope, WorkflowPublishResult
from app.config import Settings, settings as runtime_settings
from app.core.workflow_events import SUPPORTED_WORKFLOW_EVENTS


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WorkflowRetryEntry:
    dispatch_key: str
    publisher: str
    attempt: int
    reason: str
    workflow_event: dict[str, Any]


@dataclass(frozen=True, slots=True)
class WorkflowDeadLetterEntry:
    dispatch_key: str
    publisher: str
    attempts: int
    reason: str
    workflow_event: dict[str, Any]


@dataclass(frozen=True, slots=True)
class WorkflowDispatchOutcome:
    dispatch_key: str
    event_type: str | None
    status: str
    publisher_results: tuple[WorkflowPublishResult, ...] = ()
    retry_entry: WorkflowRetryEntry | None = None
    dead_letter_entry: WorkflowDeadLetterEntry | None = None


class WorkflowDispatcher:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        registry: WorkflowAdapterRegistry | None = None,
        max_history: int = 200,
        dedupe_size: int = 1000,
        max_attempts: int = 3,
    ):
        self._settings = settings or runtime_settings
        self._registry = registry or WorkflowAdapterRegistry(settings=self._settings)
        self._history: deque[WorkflowDispatchOutcome] = deque(maxlen=max(10, int(max_history)))
        self._seen_keys: deque[str] = deque(maxlen=max(100, int(dedupe_size)))
        self._seen_index: set[str] = set()
        self._lock = Lock()
        self._max_attempts = max(1, int(max_attempts))

    def snapshot(self, *, limit: int | None = None) -> list[WorkflowDispatchOutcome]:
        items = list(self._history)
        if limit is None or limit <= 0:
            return items
        return items[-limit:]

    def dispatch_realtime_event(self, realtime_event: Mapping[str, Any]) -> WorkflowDispatchOutcome:
        workflow_event = self._extract_workflow_event(realtime_event)
        event_type = str(workflow_event.get('event_type') or '') if workflow_event else None
        dispatch_key = self._build_dispatch_key(realtime_event, workflow_event)

        if not workflow_event:
            outcome = WorkflowDispatchOutcome(dispatch_key=dispatch_key, event_type=None, status='ignored')
            self._record_outcome(outcome)
            return outcome

        if event_type not in SUPPORTED_WORKFLOW_EVENTS:
            outcome = WorkflowDispatchOutcome(dispatch_key=dispatch_key, event_type=event_type, status='ignored')
            self._record_outcome(outcome)
            return outcome

        if self._is_duplicate(dispatch_key):
            outcome = WorkflowDispatchOutcome(dispatch_key=dispatch_key, event_type=event_type, status='duplicate')
            self._record_outcome(outcome)
            return outcome

        if not self._settings.WORKFLOW_ENABLED:
            outcome = WorkflowDispatchOutcome(dispatch_key=dispatch_key, event_type=event_type, status='workflow_disabled')
            self._record_outcome(outcome)
            return outcome

        publishers = self._registry.resolve(workflow_event)
        if not publishers:
            outcome = WorkflowDispatchOutcome(dispatch_key=dispatch_key, event_type=event_type, status='no_publishers')
            self._record_outcome(outcome)
            return outcome

        envelope = WorkflowDispatchEnvelope(
            dispatch_key=dispatch_key,
            realtime_event_id=self._normalize_optional_int(realtime_event.get('id')),
            realtime_event_type=str(realtime_event.get('event_type') or event_type),
            realtime_event=dict(realtime_event),
            workflow_event=workflow_event,
            attempt=1,
        )
        publisher_results: list[WorkflowPublishResult] = []
        retry_entry = None
        dead_letter_entry = None
        failed = False

        for publisher in publishers:
            publisher_name = getattr(publisher, 'name', 'unknown')
            try:
                publisher_results.append(publisher.publish(envelope))
            except Exception as exc:  # noqa: BLE001
                failed = True
                logger.warning('Workflow publisher %s failed for %s', publisher_name, dispatch_key, exc_info=True)
                publisher_results.append(
                    WorkflowPublishResult(
                        publisher=publisher_name,
                        status='failed',
                        detail=str(exc),
                    )
                )
                if envelope.attempt < self._max_attempts:
                    retry_entry = self.enqueue_retry(
                        dispatch_key=dispatch_key,
                        publisher=publisher_name,
                        attempt=envelope.attempt + 1,
                        reason=str(exc),
                        workflow_event=workflow_event,
                    )
                else:
                    dead_letter_entry = self.send_to_dead_letter(
                        dispatch_key=dispatch_key,
                        publisher=publisher_name,
                        attempts=envelope.attempt,
                        reason=str(exc),
                        workflow_event=workflow_event,
                    )

        status = 'dispatched' if not failed else 'failed'
        outcome = WorkflowDispatchOutcome(
            dispatch_key=dispatch_key,
            event_type=event_type,
            status=status,
            publisher_results=tuple(publisher_results),
            retry_entry=retry_entry,
            dead_letter_entry=dead_letter_entry,
        )
        if status == 'dispatched':
            self._remember_dispatch_key(dispatch_key)
        self._record_outcome(outcome)
        return outcome

    def enqueue_retry(
        self,
        *,
        dispatch_key: str,
        publisher: str,
        attempt: int,
        reason: str,
        workflow_event: Mapping[str, Any],
    ) -> WorkflowRetryEntry:
        entry = WorkflowRetryEntry(
            dispatch_key=dispatch_key,
            publisher=publisher,
            attempt=attempt,
            reason=reason,
            workflow_event=dict(workflow_event),
        )
        logger.info('Workflow retry placeholder created for %s via %s attempt %s', dispatch_key, publisher, attempt)
        return entry

    def send_to_dead_letter(
        self,
        *,
        dispatch_key: str,
        publisher: str,
        attempts: int,
        reason: str,
        workflow_event: Mapping[str, Any],
    ) -> WorkflowDeadLetterEntry:
        entry = WorkflowDeadLetterEntry(
            dispatch_key=dispatch_key,
            publisher=publisher,
            attempts=attempts,
            reason=reason,
            workflow_event=dict(workflow_event),
        )
        logger.warning('Workflow dead-letter placeholder created for %s via %s', dispatch_key, publisher)
        return entry

    def _record_outcome(self, outcome: WorkflowDispatchOutcome) -> None:
        with self._lock:
            self._history.append(outcome)

    def _is_duplicate(self, dispatch_key: str) -> bool:
        with self._lock:
            return dispatch_key in self._seen_index

    def _remember_dispatch_key(self, dispatch_key: str) -> None:
        with self._lock:
            if dispatch_key in self._seen_index:
                return
            if len(self._seen_keys) == self._seen_keys.maxlen:
                oldest = self._seen_keys.popleft()
                self._seen_index.discard(oldest)
            self._seen_keys.append(dispatch_key)
            self._seen_index.add(dispatch_key)

    @staticmethod
    def _extract_workflow_event(realtime_event: Mapping[str, Any]) -> dict[str, Any] | None:
        payload = realtime_event.get('payload')
        if not isinstance(payload, Mapping):
            return None
        workflow_event = payload.get('workflow_event')
        if not isinstance(workflow_event, Mapping):
            return None
        return dict(workflow_event)

    @staticmethod
    def _build_dispatch_key(realtime_event: Mapping[str, Any], workflow_event: Mapping[str, Any] | None) -> str:
        realtime_event_id = WorkflowDispatcher._normalize_optional_int(realtime_event.get('id'))
        if realtime_event_id is not None:
            return f'realtime:{realtime_event_id}'
        canonical = json.dumps(dict(workflow_event or {}), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        return f'workflow:{digest}'

    @staticmethod
    def _normalize_optional_int(value: Any) -> int | None:
        if value in (None, ''):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


workflow_dispatcher = WorkflowDispatcher()
