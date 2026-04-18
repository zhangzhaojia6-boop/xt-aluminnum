from types import SimpleNamespace

from app.services import realtime_service


def test_aggregate_live_payload_groups_workshops_machines_and_shifts() -> None:
    workshops = [
        SimpleNamespace(id=2, name='冷轧2050车间'),
    ]
    machines = [
        SimpleNamespace(id=11, workshop_id=2, name='1#'),
        SimpleNamespace(id=12, workshop_id=2, name='2#'),
    ]
    shifts = [
        SimpleNamespace(id=1, name='大夜', sort_order=1),
        SimpleNamespace(id=2, name='白班', sort_order=2),
    ]
    entries = [
        {
            'id': 101,
            'tracking_card_no': 'RA240001',
            'work_order_id': 1,
            'workshop_id': 2,
            'machine_id': 11,
            'shift_id': 1,
            'business_date': '2026-03-27',
            'input_weight': 10.0,
            'output_weight': 9.7,
            'scrap_weight': 0.3,
            'yield_rate': 97.0,
            'entry_status': 'submitted',
            'entry_type': 'completed',
            'tracking_card_status': 'in_progress',
        },
        {
            'id': 102,
            'tracking_card_no': 'RA240002',
            'work_order_id': 2,
            'workshop_id': 2,
            'machine_id': 11,
            'shift_id': 2,
            'business_date': '2026-03-27',
            'input_weight': 8.0,
            'output_weight': 7.7,
            'scrap_weight': 0.3,
            'yield_rate': 96.25,
            'entry_status': 'draft',
            'entry_type': 'in_progress',
            'tracking_card_status': 'in_progress',
        },
    ]
    attendance = {
        (2, 1): {'status': 'confirmed', 'exception_count': 0},
        (2, 2): {'status': 'pending', 'exception_count': 2},
    }
    expected_counts = {
        (2, 11, 1): 8,
        (2, 11, 2): 6,
    }

    payload = realtime_service.aggregate_live_payload(
        workshops=workshops,
        machines=machines,
        shifts=shifts,
        entries=entries,
        attendance=attendance,
        expected_counts=expected_counts,
    )

    assert payload['overall_progress'] == {'submitted_cells': 1, 'total_cells': 4}
    assert payload['factory_total']['output'] == 17.4
    assert payload['workshops'][0]['workshop_name'] == '冷轧2050车间'
    assert payload['workshops'][0]['workshop_total']['yield_rate'] == 96.67
    assert payload['workshops'][0]['machines'][0]['machine_name'] == '1#'
    assert payload['workshops'][0]['machines'][0]['shifts'][0]['submitted_count'] == 1
    assert payload['workshops'][0]['machines'][0]['shifts'][0]['total_expected'] == 8
    assert payload['workshops'][0]['machines'][0]['shifts'][0]['attendance_status'] == 'confirmed'
    assert payload['workshops'][0]['machines'][0]['shifts'][1]['submission_status'] == 'in_progress'
    assert payload['workshops'][0]['machines'][1]['shifts'][0]['submission_status'] == 'not_started'


def test_aggregate_live_payload_marks_unassigned_machine_shifts_not_applicable() -> None:
    workshops = [
        SimpleNamespace(id=4, name='热轧车间'),
    ]
    machines = [
        SimpleNamespace(id=21, workshop_id=4, name='铣床', assigned_shift_ids=[1, 2], sort_order=1),
    ]
    shifts = [
        SimpleNamespace(id=1, name='白班', sort_order=1),
        SimpleNamespace(id=2, name='小夜', sort_order=2),
        SimpleNamespace(id=3, name='大夜', sort_order=3),
    ]

    payload = realtime_service.aggregate_live_payload(
        workshops=workshops,
        machines=machines,
        shifts=shifts,
        entries=[],
        attendance={},
        expected_counts={},
    )

    machine = payload['workshops'][0]['machines'][0]
    assert payload['overall_progress'] == {'submitted_cells': 0, 'total_cells': 2}
    assert len(machine['shifts']) == 3
    assert machine['shifts'][2]['is_applicable'] is False
    assert machine['shifts'][2]['submission_status'] == 'not_applicable'
    assert machine['shifts'][2]['attendance_status'] == 'not_applicable'


def test_apply_yield_matrix_authority_overrides_factory_and_workshop_totals() -> None:
    workshops = [
        SimpleNamespace(id=2, code='LZ2050', name='冷轧2050车间'),
    ]
    payload = {
        'overall_progress': {'submitted_cells': 1, 'total_cells': 2},
        'workshops': [
            {
                'workshop_id': 2,
                'workshop_name': '冷轧2050车间',
                'machines': [],
                'shift_totals': [],
                'workshop_total': {'input': 100.0, 'output': 97.0, 'scrap': 3.0, 'yield_rate': 97.0},
            }
        ],
        'factory_total': {'input': 100.0, 'output': 97.0, 'scrap': 3.0, 'yield_rate': 97.0},
    }
    yield_matrix_lane = {
        'quality_status': 'ready',
        'company_total_yield': 96.0,
        'workshop_yields': {'cold_roll_1650_2050': 95.8},
    }

    updated = realtime_service._apply_yield_matrix_authority(payload, workshops, yield_matrix_lane)

    assert updated['factory_total']['yield_rate'] == 96.0
    assert updated['factory_total']['yield_rate_source'] == 'yield_matrix_lane'
    assert updated['workshops'][0]['workshop_total']['yield_rate'] == 95.8
    assert updated['workshops'][0]['workshop_total']['yield_rate_source'] == 'yield_matrix_lane'
    assert updated['yield_matrix_lane']['quality_status'] == 'ready'
