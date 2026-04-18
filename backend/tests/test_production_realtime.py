from datetime import date
from types import SimpleNamespace

from app.services.production_service import update_shift_data_status


def test_confirm_shift_data_publishes_attendance_event(monkeypatch) -> None:
    item = SimpleNamespace(
        id=15,
        business_date=date(2026, 3, 27),
        workshop_id=2,
        team_id=None,
        equipment_id=11,
        shift_config_id=3,
        data_status='reviewed',
        reviewed_by=None,
        reviewed_at=None,
        confirmed_by=None,
        confirmed_at=None,
        rejected_by=None,
        rejected_at=None,
        rejected_reason=None,
        voided_by=None,
        voided_at=None,
        voided_reason=None,
    )
    events = []

    class DummyDB:
        def get(self, *_args, **_kwargs):
            return item

        def flush(self):
            return None

        def commit(self):
            return None

        def refresh(self, _item):
            return None

    monkeypatch.setattr('app.services.production_service.assert_review_access', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.production_service.bulk_update_production_exception_status',
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr('app.services.production_service.sync_mobile_status_from_review', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.production_service.record_audit', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.production_service._count_open_attendance_exceptions_for_shift',
        lambda *_args, **_kwargs: 2,
    )
    monkeypatch.setattr(
        'app.services.production_service._build_attendance_confirmed_event',
        lambda *_args, **_kwargs: {
            'workshop_id': 2,
            'workshop': '冷轧2050车间',
            'machine': '1#',
            'shift': '白班',
            'exception_count': 2,
        },
    )
    monkeypatch.setattr(
        'app.services.production_service.event_bus.publish',
        lambda event_type, payload: events.append((event_type, payload)),
    )

    result = update_shift_data_status(
        DummyDB(),
        shift_data_id=15,
        action='confirm',
        reason='ok',
        operator=SimpleNamespace(id=8, role='statistician'),
    )

    assert result.data_status == 'confirmed'
    assert events == [
        (
            'attendance_confirmed',
            {
                'workshop_id': 2,
                'workshop': '冷轧2050车间',
                'machine': '1#',
                'shift': '白班',
                'exception_count': 2,
            },
        )
    ]
