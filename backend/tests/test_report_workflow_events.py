from datetime import date
from types import SimpleNamespace

from app.services.report_service import publish_report, review_report


def test_review_report_publishes_workflow_event(monkeypatch) -> None:
    report = SimpleNamespace(
        id=5,
        report_date=date(2026, 4, 4),
        report_type='production',
        workshop_id=None,
        generated_scope='all',
        output_mode='both',
        status='draft',
        reviewed_by=None,
        reviewed_at=None,
    )
    published_events = []

    class DummyDB:
        def get(self, _model, report_id):
            assert report_id == 5
            return report

        def flush(self):
            return None

        def commit(self):
            return None

        def refresh(self, entity):
            assert entity is report

    monkeypatch.setattr('app.services.report_service.record_audit', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.report_service.event_bus.publish',
        lambda event_type, payload: published_events.append((event_type, payload)),
    )

    result = review_report(
        DummyDB(),
        report_id=5,
        operator=SimpleNamespace(id=8, role='reviewer'),
        note='ready for publish',
    )

    assert result is report
    assert report.status == 'reviewed'
    assert published_events[0][0] == 'report_reviewed'
    assert published_events[0][1]['workflow_event']['event_type'] == 'report_reviewed'
    assert published_events[0][1]['workflow_event']['actor_role'] == 'reviewer'
    assert published_events[0][1]['workflow_event']['entity_id'] == 5


def test_publish_report_publishes_workflow_event(monkeypatch) -> None:
    report = SimpleNamespace(
        id=6,
        report_date=date(2026, 4, 4),
        report_type='production',
        workshop_id=None,
        generated_scope='all',
        output_mode='both',
        status='reviewed',
        published_by=None,
        published_at=None,
        report_data={'yield_matrix_lane': {'quality_status': 'ready'}},
    )
    published_events = []

    class DummyDB:
        def get(self, _model, report_id):
            assert report_id == 6
            return report

        def flush(self):
            return None

        def commit(self):
            return None

        def refresh(self, entity):
            assert entity is report

    monkeypatch.setattr('app.services.report_service.record_audit', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.report_service.mark_shift_data_published', lambda *_args, **_kwargs: 3)
    monkeypatch.setattr(
        'app.services.report_service.resolve_report_delivery_payload',
        lambda *_args, **_kwargs: {
            'delivery_lane': 'yield_matrix_lane',
            'delivery_scope': 'workshop:cold_roll_1450',
            'delivery_target': 'workshop',
            'delivery_target_key': '10',
            'delivery_resolution_status': 'resolved',
            'resolved_targets': [{'logical_type': 'workshop-observer', 'channel_key': '10'}],
        },
    )
    monkeypatch.setattr(
        'app.services.report_service.event_bus.publish',
        lambda event_type, payload: published_events.append((event_type, payload)),
    )

    result = publish_report(
        DummyDB(),
        report_id=6,
        operator=SimpleNamespace(id=9, role='manager'),
        note='final release',
    )

    assert result is report
    assert report.status == 'published'
    assert published_events[0][0] == 'report_published'
    assert published_events[0][1]['published_shift_count'] == 3
    assert published_events[0][1]['workflow_event']['event_type'] == 'report_published'
    assert published_events[0][1]['workflow_event']['status'] == 'published'
    assert published_events[0][1]['workflow_event']['payload']['delivery_lane'] == 'yield_matrix_lane'
    assert published_events[0][1]['workflow_event']['payload']['delivery_target'] == 'workshop'
    assert published_events[0][1]['workflow_event']['payload']['delivery_target_key'] == '10'
