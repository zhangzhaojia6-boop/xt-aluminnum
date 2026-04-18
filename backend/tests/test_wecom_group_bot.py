from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest

from app.config import Settings
from app.core.workflow_dispatcher import WorkflowDispatcher
from app.core.workflow_events import build_workflow_event


def build_settings(**overrides) -> Settings:
    values = {
        'APP_ENV': 'development',
        'DATABASE_URL': 'postgresql+psycopg2://user:pass@localhost:5432/test',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        'WORKFLOW_ENABLED': True,
        'WECOM_BOT_ENABLED': True,
        'WECOM_BOT_DRY_RUN': True,
        'WECOM_BOT_MANAGEMENT_WEBHOOK_URL': 'https://example.invalid/management',
        'WECOM_BOT_WORKSHOP_WEBHOOK_MAP': '{"2":"https://example.invalid/workshop-2"}',
        'WECOM_BOT_TEAM_WEBHOOK_MAP': '{"7":"https://example.invalid/team-7"}',
    }
    values.update(overrides)
    return Settings(**values)


def build_envelope(
    event_type: str,
    *,
    scope_type: str = 'workshop',
    workshop_id: int | None = 2,
    team_id: int | None = None,
    payload: dict | None = None,
) -> dict:
    workflow_event = build_workflow_event(
        event_type=event_type,
        actor_role='leader',
        actor_id=18,
        scope_type=scope_type,
        workshop_id=workshop_id,
        team_id=team_id,
        shift_id=3,
        entity_type='daily_report' if event_type.startswith('report_') else 'attendance_confirmation',
        entity_id=19,
        status='published' if event_type == 'report_published' else 'confirmed',
        payload=payload or {'report_date': '2026-04-04', 'report_type': 'production'},
        occurred_at=datetime(2026, 4, 4, 8, 30, tzinfo=timezone.utc),
    )
    realtime_payload = {
        'workflow_event': workflow_event,
        'workshop_id': workshop_id,
        'workshop': '熔铸一车间' if workshop_id else None,
        'team_id': team_id,
        'team': '甲班' if team_id else None,
        'shift': '白班',
    }
    return {
        'id': 9,
        'event_type': event_type,
        'payload': realtime_payload,
        'workshop_id': workshop_id,
        'created_at': '2026-04-04T08:30:00+00:00',
    }


@pytest.mark.parametrize(
    ('event_type', 'workflow_overrides', 'expected_target', 'expected_kind'),
    [
        ('attendance_confirmed', {'team_id': 7}, 'team', 'review_completed'),
        ('attendance_confirmed', {}, 'workshop', 'review_completed'),
        ('report_published', {'scope_type': 'factory', 'workshop_id': None}, 'management', 'daily_report_published'),
    ],
)
def test_wecom_group_bot_dry_run_routes_targets_without_network(
    event_type: str,
    workflow_overrides: dict,
    expected_target: str,
    expected_kind: str,
) -> None:
    from app.adapters.wecom.group_bot import WeComGroupBotPublisher

    calls = []
    publisher = WeComGroupBotPublisher(
        settings=build_settings(),
        sender=lambda **kwargs: calls.append(kwargs),
    )

    envelope = build_envelope(event_type, **workflow_overrides)
    result = publisher.publish(publisher.build_dispatch_envelope(envelope))

    assert result.publisher == 'wecom_group_bot'
    assert result.status == 'dry_run'
    assert result.metadata['target_type'] == expected_target
    assert result.metadata['message_kind'] == expected_kind
    assert calls == []


def test_wecom_group_bot_raises_on_timeout() -> None:
    from app.adapters.wecom.group_bot import WeComGroupBotPublisher

    publisher = WeComGroupBotPublisher(
        settings=build_settings(WECOM_BOT_DRY_RUN=False),
        sender=lambda **_kwargs: (_ for _ in ()).throw(httpx.TimeoutException('timed out')),
    )

    with pytest.raises(RuntimeError) as exc_info:
        publisher.publish(publisher.build_dispatch_envelope(build_envelope('report_published', scope_type='factory', workshop_id=None)))

    assert 'timed out' in str(exc_info.value)


def test_wecom_group_bot_raises_on_non_2xx_response() -> None:
    from app.adapters.wecom.group_bot import WeComGroupBotPublisher

    publisher = WeComGroupBotPublisher(
        settings=build_settings(WECOM_BOT_DRY_RUN=False),
        sender=lambda **_kwargs: SimpleNamespace(status_code=502, text='bad gateway', json=lambda: {'errmsg': 'bad gateway'}),
    )

    with pytest.raises(RuntimeError) as exc_info:
        publisher.publish(publisher.build_dispatch_envelope(build_envelope('report_published', scope_type='factory', workshop_id=None)))

    assert 'non-2xx response' in str(exc_info.value)


def test_wecom_group_bot_raises_on_wecom_business_error() -> None:
    from app.adapters.wecom.group_bot import WeComGroupBotPublisher

    publisher = WeComGroupBotPublisher(
        settings=build_settings(WECOM_BOT_DRY_RUN=False),
        sender=lambda **_kwargs: SimpleNamespace(status_code=200, text='ok', json=lambda: {'errcode': 93000, 'errmsg': 'invalid webhook'}),
    )

    with pytest.raises(RuntimeError) as exc_info:
        publisher.publish(publisher.build_dispatch_envelope(build_envelope('report_reviewed', scope_type='factory', workshop_id=None)))

    assert 'invalid webhook' in str(exc_info.value)


def test_dispatcher_uses_wecom_group_bot_in_dry_run_mode() -> None:
    dispatcher = WorkflowDispatcher(settings=build_settings())

    outcome = dispatcher.dispatch_realtime_event(build_envelope('report_published', scope_type='factory', workshop_id=None))

    assert outcome.status == 'dispatched'
    assert [item.publisher for item in outcome.publisher_results] == ['null', 'wecom_group_bot']
    assert outcome.publisher_results[1].status == 'dry_run'


def test_dispatcher_keeps_behavior_unchanged_when_wecom_bot_is_disabled() -> None:
    dispatcher = WorkflowDispatcher(settings=build_settings(WECOM_BOT_ENABLED=False))

    outcome = dispatcher.dispatch_realtime_event(build_envelope('report_published', scope_type='factory', workshop_id=None))

    assert outcome.status == 'dispatched'
    assert [item.publisher for item in outcome.publisher_results] == ['null']


def test_wecom_group_bot_uses_delivery_target_key_for_workshop_report_without_entity_workshop_id() -> None:
    from app.adapters.wecom.group_bot import WeComGroupBotPublisher

    publisher = WeComGroupBotPublisher(
        settings=build_settings(),
        sender=lambda **kwargs: kwargs,
    )
    envelope = build_envelope(
        'report_published',
        scope_type='factory',
        workshop_id=None,
        payload={
            'report_date': '2026-04-04',
            'report_type': 'production',
            'delivery_target': 'workshop',
            'delivery_target_key': '2',
            'delivery_scope': 'workshop:cold_roll_1650_2050',
        },
    )

    result = publisher.publish(publisher.build_dispatch_envelope(envelope))

    assert result.status == 'dry_run'
    assert result.metadata['target_type'] == 'workshop'
    assert result.metadata['target_key'] == '2'
