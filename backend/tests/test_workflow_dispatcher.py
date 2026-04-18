from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.adapters.workflow import WorkflowAdapterRegistry
from app.adapters.workflow.base import WorkflowDispatchEnvelope
from app.config import Settings
from app.core.event_bus import InMemoryEventBus
from app.core.workflow_dispatcher import WorkflowDispatcher
from app.core.workflow_events import build_workflow_event


def build_settings(**overrides) -> Settings:
    values = {
        'APP_ENV': 'development',
        'DATABASE_URL': 'postgresql+psycopg2://user:pass@localhost:5432/test',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        'WORKFLOW_ENABLED': True,
    }
    values.update(overrides)
    return Settings(**values)


def build_realtime_event(event_type: str, *, event_id: int = 1) -> dict:
    workflow_event = build_workflow_event(
        event_type=event_type,
        actor_role='leader',
        actor_id=18,
        scope_type='machine',
        workshop_id=2,
        team_id=7,
        shift_id=3,
        entity_type='workflow_entity',
        entity_id=19,
        status='submitted',
        payload={'tracking_card_no': 'RA240001'},
        occurred_at=datetime(2026, 4, 4, 8, 30, tzinfo=timezone.utc),
    )
    return {
        'id': event_id,
        'event_type': event_type,
        'payload': {
            'tracking_card_no': 'RA240001',
            'workshop_id': 2,
            'workflow_event': workflow_event,
        },
        'workshop_id': 2,
        'created_at': '2026-04-04T08:30:00+00:00',
    }


@pytest.mark.parametrize(
    'event_type',
    [
        'entry_saved',
        'entry_submitted',
        'attendance_confirmed',
        'report_reviewed',
        'report_published',
    ],
)
def test_dispatcher_routes_supported_workflow_events_to_null_publisher(event_type: str) -> None:
    dispatcher = WorkflowDispatcher(settings=build_settings(WORKFLOW_ENABLED=True))

    outcome = dispatcher.dispatch_realtime_event(build_realtime_event(event_type))

    assert outcome.status == 'dispatched'
    assert outcome.event_type == event_type
    assert outcome.publisher_results[0].publisher == 'null'
    assert outcome.publisher_results[0].status == 'accepted'
    assert dispatcher.snapshot(limit=1)[0].dispatch_key == 'realtime:1'


def test_dispatcher_marks_successful_dispatches_as_duplicates_on_repeat() -> None:
    dispatcher = WorkflowDispatcher(settings=build_settings(WORKFLOW_ENABLED=True))
    realtime_event = build_realtime_event('entry_saved', event_id=9)

    first = dispatcher.dispatch_realtime_event(realtime_event)
    duplicate = dispatcher.dispatch_realtime_event(realtime_event)

    assert first.status == 'dispatched'
    assert duplicate.status == 'duplicate'
    assert duplicate.publisher_results == ()


def test_dispatcher_creates_retry_placeholder_when_publisher_fails() -> None:
    class BrokenPublisher:
        name = 'broken'

        def supports(self, workflow_event):
            return workflow_event.get('event_type') == 'report_reviewed'

        def publish(self, envelope: WorkflowDispatchEnvelope):
            raise RuntimeError(f'boom:{envelope.dispatch_key}')

    dispatcher = WorkflowDispatcher(
        settings=build_settings(WORKFLOW_ENABLED=True),
        registry=WorkflowAdapterRegistry(publishers=[BrokenPublisher()]),
        max_attempts=2,
    )

    outcome = dispatcher.dispatch_realtime_event(build_realtime_event('report_reviewed', event_id=11))

    assert outcome.status == 'failed'
    assert outcome.publisher_results[0].publisher == 'broken'
    assert outcome.publisher_results[0].status == 'failed'
    assert outcome.retry_entry is not None
    assert outcome.retry_entry.publisher == 'broken'
    assert outcome.dead_letter_entry is None


def test_dispatcher_creates_dead_letter_placeholder_when_max_attempts_are_exhausted() -> None:
    class BrokenPublisher:
        name = 'broken'

        def supports(self, workflow_event):
            return True

        def publish(self, _envelope: WorkflowDispatchEnvelope):
            raise RuntimeError('still broken')

    dispatcher = WorkflowDispatcher(
        settings=build_settings(WORKFLOW_ENABLED=True),
        registry=WorkflowAdapterRegistry(publishers=[BrokenPublisher()]),
        max_attempts=1,
    )

    outcome = dispatcher.dispatch_realtime_event(build_realtime_event('report_published', event_id=12))

    assert outcome.status == 'failed'
    assert outcome.retry_entry is None
    assert outcome.dead_letter_entry is not None
    assert outcome.dead_letter_entry.publisher == 'broken'


def test_event_bus_publish_hands_workflow_events_to_dispatcher(monkeypatch) -> None:
    bus = InMemoryEventBus()
    dispatched = []

    monkeypatch.setattr(
        'app.core.workflow_dispatcher.workflow_dispatcher.dispatch_realtime_event',
        lambda realtime_event: dispatched.append(realtime_event),
    )

    bus.publish(
        'entry_submitted',
        {
            'tracking_card_no': 'RA240001',
            'workshop_id': 2,
            'workflow_event': build_realtime_event('entry_submitted')['payload']['workflow_event'],
        },
    )

    assert dispatched[0]['event_type'] == 'entry_submitted'
    assert dispatched[0]['payload']['workflow_event']['event_type'] == 'entry_submitted'
