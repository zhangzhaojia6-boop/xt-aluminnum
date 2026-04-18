from datetime import datetime, timezone

from app.core.workflow_events import SUPPORTED_WORKFLOW_EVENTS, attach_workflow_event, build_workflow_event


def test_build_workflow_event_returns_standard_contract() -> None:
    payload = build_workflow_event(
        event_type='entry_submitted',
        actor_role='leader',
        actor_id=18,
        scope_type='machine',
        workshop_id=2,
        team_id=7,
        shift_id=3,
        entity_type='work_order_entry',
        entity_id=19,
        status='submitted',
        payload={'tracking_card_no': 'RA240001'},
        occurred_at=datetime(2026, 4, 4, 8, 30, tzinfo=timezone.utc),
    )

    assert payload == {
        'event_type': 'entry_submitted',
        'occurred_at': '2026-04-04T08:30:00+00:00',
        'actor_role': 'leader',
        'actor_id': 18,
        'scope_type': 'machine',
        'workshop_id': 2,
        'team_id': 7,
        'shift_id': 3,
        'entity_type': 'work_order_entry',
        'entity_id': 19,
        'status': 'submitted',
        'payload': {'tracking_card_no': 'RA240001'},
    }


def test_attach_workflow_event_preserves_existing_realtime_payload() -> None:
    realtime_payload = attach_workflow_event(
        {'tracking_card_no': 'RA240001', 'workshop_id': 2},
        build_workflow_event(
            event_type='attendance_confirmed',
            actor_role='leader',
            actor_id=5,
            scope_type='machine',
            workshop_id=2,
            team_id=None,
            shift_id=3,
            entity_type='attendance_confirmation',
            entity_id=12,
            status='confirmed',
            payload={'exception_count': 1},
        ),
    )

    assert realtime_payload['tracking_card_no'] == 'RA240001'
    assert realtime_payload['workshop_id'] == 2
    assert realtime_payload['workflow_event']['event_type'] == 'attendance_confirmed'
    assert realtime_payload['workflow_event']['payload'] == {'exception_count': 1}


def test_supported_workflow_events_are_stable_for_future_webhook_publishers() -> None:
    assert SUPPORTED_WORKFLOW_EVENTS == {
        'attendance_confirmed',
        'entry_saved',
        'entry_submitted',
        'report_published',
        'report_reviewed',
    }
