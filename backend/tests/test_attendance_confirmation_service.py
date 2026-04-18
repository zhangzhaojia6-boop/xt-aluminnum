from datetime import date, time
from types import SimpleNamespace

from app.services import attendance_confirm_service


def test_build_draft_prefills_from_schedule_and_dingtalk(monkeypatch) -> None:
    shift = SimpleNamespace(
        id=3,
        code='D',
        name='白班',
        start_time=time(7, 0),
        end_time=time(15, 0),
        is_cross_day=False,
        business_day_offset=0,
    )
    employees = [
        SimpleNamespace(id=1, employee_no='E001', name='张三'),
        SimpleNamespace(id=2, employee_no='E002', name='李四'),
        SimpleNamespace(id=3, employee_no='E003', name='王五'),
    ]

    monkeypatch.setattr(
        'app.services.attendance_confirm_service._resolve_confirmation_context',
        lambda *_args, **_kwargs: {
            'workshop_id': 2,
            'workshop_name': '冷轧2050车间',
            'team_id': 10,
            'machine_id': 11,
            'machine_name': '1#',
            'shift': shift,
        },
    )
    monkeypatch.setattr('app.services.attendance_confirm_service._load_roster_employees', lambda *_args, **_kwargs: employees)
    monkeypatch.setattr(
        'app.services.attendance_confirm_service._load_dingtalk_clock_map',
        lambda *_args, **_kwargs: {
            1: {'clock_in': time(7, 2), 'clock_out': time(15, 1)},
            2: {'clock_in': None, 'clock_out': None},
            3: {'clock_in': time(7, 20), 'clock_out': time(15, 0)},
        },
    )
    monkeypatch.setattr('app.services.attendance_confirm_service._load_existing_confirmation', lambda *_args, **_kwargs: None)

    payload = attendance_confirm_service.build_draft(
        SimpleNamespace(),
        machine_id=11,
        shift_id=3,
        business_date=date(2026, 3, 27),
        current_user=SimpleNamespace(id=7, workshop_id=2, team_id=10, role='shift_leader'),
    )

    assert payload['machine_name'] == '1#'
    assert payload['headcount_expected'] == 3
    assert payload['status'] == 'draft'
    assert payload['items'][0]['employee_name'] == '张三'
    assert payload['items'][0]['auto_status'] == 'present'
    assert payload['items'][0]['leader_status'] == 'present'
    assert payload['items'][1]['auto_status'] == 'absent'
    assert payload['items'][1]['dingtalk_clock_in'] is None
    assert payload['items'][2]['auto_status'] == 'late'
    assert payload['items'][2]['late_minutes'] == 20


def test_detect_anomalies_flags_only_overrides() -> None:
    anomalies = attendance_confirm_service.detect_anomalies(
        [
            {
                'employee_id': 1,
                'employee_name': '张三',
                'auto_status': 'present',
                'leader_status': 'present',
                'override_reason': None,
            },
            {
                'employee_id': 2,
                'employee_name': '李四',
                'auto_status': 'absent',
                'leader_status': 'business_trip',
                'override_reason': '外出客户现场',
            },
        ]
    )

    assert len(anomalies) == 1
    assert anomalies[0]['employee_id'] == 2
    assert anomalies[0]['employee_name'] == '李四'
    assert anomalies[0]['auto_status'] == 'absent'
    assert anomalies[0]['leader_status'] == 'business_trip'
