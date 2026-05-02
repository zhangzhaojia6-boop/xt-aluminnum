from types import SimpleNamespace

from app.services.realtime_service import aggregate_live_payload


def _workshop(id, name, sort_order=1):
    return SimpleNamespace(id=id, name=name, sort_order=sort_order)


def _machine(id, name, workshop_id, assigned_shift_ids=None, sort_order=1):
    return SimpleNamespace(
        id=id,
        name=name,
        workshop_id=workshop_id,
        assigned_shift_ids=assigned_shift_ids,
        sort_order=sort_order,
    )


def _shift(id, name, sort_order=1):
    return SimpleNamespace(id=id, name=name, sort_order=sort_order)


def test_live_aggregation_contract_counts_missing_and_attention_cells():
    payload = aggregate_live_payload(
        workshops=[_workshop(1, '冷轧一车间')],
        machines=[
            _machine(10, '1#轧机', 1, assigned_shift_ids=[1, 2, 3], sort_order=1),
            _machine(11, '2#轧机', 1, assigned_shift_ids=[1, 2], sort_order=2),
        ],
        shifts=[
            _shift(1, '白班', 1),
            _shift(2, '中班', 2),
            _shift(3, '夜班', 3),
        ],
        entries=[
            {
                'workshop_id': 1,
                'machine_id': 10,
                'shift_id': 1,
                'entry_status': 'submitted',
                'input_weight': 100,
                'output_weight': 96,
                'scrap_weight': 4,
            },
            {
                'workshop_id': 1,
                'machine_id': 10,
                'shift_id': 2,
                'entry_status': 'draft',
                'input_weight': 80,
                'output_weight': 0,
                'scrap_weight': 0,
            },
            {
                'workshop_id': 1,
                'machine_id': 11,
                'shift_id': 1,
                'entry_status': 'submitted',
                'input_weight': 120,
                'output_weight': 118,
                'scrap_weight': 2,
            },
        ],
        attendance={
            (1, 1): {'status': 'confirmed', 'exception_count': 1},
            (1, 2): {'status': 'pending', 'exception_count': 0},
        },
        expected_counts={
            (1, 10, 1): 1,
            (1, 10, 2): 1,
            (1, 11, 1): 1,
        },
    )

    assert payload['overall_progress'] == {
        'submitted_cells': 2,
        'total_cells': 5,
        'missing_cell_count': 2,
        'attention_cell_count': 4,
        'completion_rate': 40.0,
    }

    machine_one = payload['workshops'][0]['machines'][0]
    machine_two = payload['workshops'][0]['machines'][1]

    assert machine_one['shifts'][0]['submission_status'] == 'all_submitted'
    assert machine_one['shifts'][0]['status_tone'] == 'success'
    assert machine_one['shifts'][0]['status_text'] == '已填'

    assert machine_one['shifts'][1]['submission_status'] == 'in_progress'
    assert machine_one['shifts'][1]['status_tone'] == 'warning'
    assert machine_one['shifts'][1]['status_text'] == '进行中'

    assert machine_one['shifts'][2]['submission_status'] == 'not_started'
    assert machine_one['shifts'][2]['status_tone'] == 'danger'
    assert machine_one['shifts'][2]['status_text'] == '缺报'

    assert machine_two['shifts'][0]['submission_status'] == 'all_submitted'
    assert machine_two['shifts'][0]['status_tone'] == 'danger'
    assert machine_two['shifts'][0]['status_text'] == '考勤异常'

    assert machine_two['shifts'][2]['submission_status'] == 'not_applicable'
    assert machine_two['shifts'][2]['status_tone'] == 'muted'
    assert machine_two['shifts'][2]['status_text'] == '不适用'
