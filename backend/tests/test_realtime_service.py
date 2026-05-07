from datetime import date, datetime, time
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Equipment, MasterCodeAlias, Team, Workshop
from app.models.mes import MesCoilSnapshot
from app.models.production import ShiftProductionData, WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import realtime_service


def build_realtime_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'realtime-detail.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Team.__table__,
            User.__table__,
            Equipment.__table__,
            MasterCodeAlias.__table__,
            ShiftConfig.__table__,
            ShiftProductionData.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            MesCoilSnapshot.__table__,
        ],
    )
    return sessionmaker(bind=engine, autoflush=False, future=True)()


def admin_user() -> User:
    return User(id=7, username='admin', password_hash='x', name='Admin', role='admin')


def seed_pending_assignment_entry(
    db,
    *,
    entry_id: int,
    tracking_card_no: str,
    workshop_id: int,
    shift_id: int | None,
    machine_id: int | None,
    output_weight: float = 96_000.0,
) -> None:
    db.add(
        WorkOrder(
            id=entry_id,
            tracking_card_no=tracking_card_no,
            process_route_code='cold-roll',
            overall_status='in_progress',
        )
    )
    db.add(
        WorkOrderEntry(
            id=entry_id,
            work_order_id=entry_id,
            workshop_id=workshop_id,
            machine_id=machine_id,
            shift_id=shift_id,
            business_date=date(2026, 5, 6),
            input_weight=100_000.0,
            output_weight=output_weight,
            scrap_weight=4_000.0,
            entry_status='draft',
            entry_type='mobile_coil',
            created_by_user_id=9,
        )
    )


def test_resolve_live_business_date_prefers_latest_recent_upload_business_day(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            WorkOrder(id=501, tracking_card_no='RA260506501', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=501,
                work_order_id=501,
                workshop_id=2,
                machine_id=None,
                shift_id=3,
                business_date=date(2026, 5, 6),
                input_weight=100_000.0,
                output_weight=96_000.0,
                scrap_weight=4_000.0,
                entry_status='draft',
                entry_type='mobile_coil',
                created_at=datetime(2026, 5, 7, 8, 10),
            ),
        ]
    )
    db.commit()

    payload = realtime_service.resolve_live_business_date(
        db,
        today=date(2026, 5, 7),
        now=datetime(2026, 5, 7, 9, 30),
    )

    assert payload == {
        'business_date': '2026-05-06',
        'source': 'recent_upload',
        'recent_entry_count': 1,
    }


def test_build_live_aggregation_blends_mes_projection_with_bound_fill_entries(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050# 主操', workshop_id=2, is_active=True),
            WorkOrder(id=601, tracking_card_no='RA260506601', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=601,
                work_order_id=601,
                workshop_id=2,
                machine_id=11,
                shift_id=3,
                business_date=date(2026, 5, 6),
                input_weight=10_000.0,
                output_weight=9_700.0,
                scrap_weight=300.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_by_user_id=85,
            ),
            MesCoilSnapshot(
                id=701,
                coil_id='MES-701',
                tracking_card_no='MES-RA260506701',
                workshop_code='LZ2050',
                machine_code='LZ2050-1',
                shift_code='N',
                status='synced',
                business_date=date(2026, 5, 6),
                source_payload={'input_weight': 6.0, 'output_weight': 5.2, 'scrap_weight': 0.8},
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(realtime_service, '_build_attendance_summary', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, '_build_expected_count_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, 'build_yield_matrix_projection', lambda *_args, **_kwargs: {})

    payload = realtime_service.build_live_aggregation(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=admin_user(),
    )

    assert payload['data_source'] == 'mixed'
    assert payload['overall_progress']['formal_entry_count'] == 2
    assert payload['factory_total']['output'] == 14.9
    machine = payload['workshops'][0]['machines'][0]
    assert machine['machine_binding_status'] == 'bound'
    assert machine['day_total']['output'] == 14.9
    assert machine['shifts'][0]['submitted_count'] == 2


def test_build_live_aggregation_resolves_mes_workshop_aliases(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050轧机', workshop_id=2, is_active=True),
            MasterCodeAlias(
                entity_type='workshop',
                canonical_code='LZ2050',
                alias_code='2050车间',
                alias_name='2050车间',
                source_type='mes_mvc',
                is_active=True,
            ),
            MesCoilSnapshot(
                id=702,
                coil_id='MES-702',
                tracking_card_no='MES-RA260506702',
                workshop_code='2050车间',
                machine_code='LZ2050-1',
                shift_code='N',
                status='synced',
                business_date=date(2026, 5, 6),
                source_payload={'input_weight': 6.0, 'output_weight': 5.2, 'scrap_weight': 0.8},
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(realtime_service, '_build_attendance_summary', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, '_build_expected_count_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, 'build_yield_matrix_projection', lambda *_args, **_kwargs: {})

    payload = realtime_service.build_live_aggregation(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=admin_user(),
    )

    assert payload['data_source'] == 'mes_projection'
    assert payload['factory_total']['output'] == 5.2
    machine = payload['workshops'][0]['machines'][0]
    assert machine['machine_id'] == 11
    assert machine['day_total']['output'] == 5.2
    assert machine['shifts'][0]['submitted_count'] == 1


def test_build_live_aggregation_pairs_fill_uploads_with_mes_machine_binding(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050轧机', workshop_id=2, is_active=True),
            WorkOrder(id=703, tracking_card_no='RA260506703', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=703,
                work_order_id=703,
                workshop_id=2,
                machine_id=None,
                shift_id=None,
                business_date=date(2026, 5, 6),
                input_weight=10_000.0,
                output_weight=9_700.0,
                scrap_weight=300.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_by_user_id=85,
            ),
            MesCoilSnapshot(
                id=703,
                coil_id='MES-703',
                tracking_card_no='RA260506703',
                workshop_code='LZ2050',
                machine_code='LZ2050-1',
                shift_code='N',
                status='synced',
                business_date=None,
                source_payload={'input_weight': 6.0, 'output_weight': 5.2, 'scrap_weight': 0.8},
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(realtime_service, '_build_attendance_summary', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, '_build_expected_count_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, 'build_yield_matrix_projection', lambda *_args, **_kwargs: {})

    payload = realtime_service.build_live_aggregation(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=admin_user(),
    )

    assert payload['data_source'] == 'mixed'
    assert payload['overall_progress']['formal_entry_count'] == 1
    assert 'pending_assignment' not in payload['overall_progress']
    assert payload['factory_total']['output'] == 9.7
    machine = payload['workshops'][0]['machines'][0]
    assert machine['machine_id'] == 11
    assert machine['day_total']['output'] == 9.7
    assert machine['shifts'][0]['submitted_count'] == 1
    assert machine['shifts'][0]['total_output'] == 9.7


def test_build_live_aggregation_pairs_cards_with_operator_separator_variants(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050轧机', workshop_id=2, is_active=True),
            WorkOrder(id=705, tracking_card_no='S一2一054一1', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=705,
                work_order_id=705,
                workshop_id=2,
                machine_id=None,
                shift_id=None,
                business_date=date(2026, 5, 6),
                input_weight=10_000.0,
                output_weight=9_700.0,
                scrap_weight=300.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_by_user_id=85,
            ),
            MesCoilSnapshot(
                id=705,
                coil_id='MES-705',
                tracking_card_no='S-2-054-1',
                workshop_code='LZ2050',
                machine_code='LZ2050-1',
                shift_code='N',
                status='synced',
                business_date=None,
                source_payload={'input_weight': 6.0, 'output_weight': 5.2, 'scrap_weight': 0.8},
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(realtime_service, '_build_attendance_summary', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, '_build_expected_count_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, 'build_yield_matrix_projection', lambda *_args, **_kwargs: {})

    payload = realtime_service.build_live_aggregation(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=admin_user(),
    )

    assert payload['data_source'] == 'mixed'
    assert payload['overall_progress']['formal_entry_count'] == 1
    assert 'pending_assignment' not in payload['overall_progress']
    machine = payload['workshops'][0]['machines'][0]
    assert machine['machine_id'] == 11
    assert machine['day_total']['output'] == 9.7
    assert machine['shifts'][0]['submitted_count'] == 1


def test_build_live_aggregation_does_not_cross_bind_mes_machine_to_other_workshop(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            Workshop(id=4, code='JZ', name='精整车间', sort_order=2, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050轧机', workshop_id=2, is_active=True),
            WorkOrder(id=704, tracking_card_no='RA260506704', process_route_code='finishing', overall_status='created'),
            WorkOrderEntry(
                id=704,
                work_order_id=704,
                workshop_id=4,
                machine_id=None,
                shift_id=None,
                business_date=date(2026, 5, 6),
                input_weight=8_000.0,
                output_weight=7_600.0,
                scrap_weight=400.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_by_user_id=86,
            ),
            MesCoilSnapshot(
                id=704,
                coil_id='MES-704',
                tracking_card_no='RA260506704',
                workshop_code='LZ2050',
                machine_code='LZ2050-1',
                shift_code='N',
                status='synced',
                business_date=date(2026, 5, 6),
                source_payload={'input_weight': 8.0, 'output_weight': 7.6, 'scrap_weight': 0.4},
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(realtime_service, '_build_attendance_summary', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, '_build_expected_count_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, 'build_yield_matrix_projection', lambda *_args, **_kwargs: {})

    payload = realtime_service.build_live_aggregation(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=admin_user(),
    )

    assert payload['data_source'] == 'work_order_runtime'
    assert payload['overall_progress']['formal_entry_count'] == 1
    pending = payload['overall_progress']['pending_assignment']
    assert pending['entry_count'] == 1
    assert pending['missing_machine_count'] == 1
    assert pending['missing_shift_count'] == 1
    assert pending['rows'][0]['workshop_id'] == 4


def test_build_pending_assignment_detail_returns_unbound_draft_rows(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(
                id=3,
                code='N',
                name='夜班',
                shift_type='night',
                start_time=time(20, 0),
                end_time=time(8, 0),
                is_cross_day=True,
                sort_order=3,
                is_active=True,
            ),
            Equipment(id=11, code='LZ2050-1', name='1#轧机', workshop_id=2, operational_status='running', is_active=True),
            User(id=9, username='op-a', password_hash='x', name='主操甲', role='machine_operator', is_active=True),
            MesCoilSnapshot(
                id=901,
                coil_id='MES-RA260506001',
                tracking_card_no='RA260506001',
                workshop_code='LZ2050',
                machine_code='LZ2050-1',
                shift_code='N',
                business_date=date(2026, 5, 6),
                status='synced',
            ),
        ]
    )
    seed_pending_assignment_entry(
        db,
        entry_id=101,
        tracking_card_no='RA260506001',
        workshop_id=2,
        shift_id=3,
        machine_id=None,
    )
    seed_pending_assignment_entry(
        db,
        entry_id=102,
        tracking_card_no='RA260506002',
        workshop_id=2,
        shift_id=3,
        machine_id=11,
        output_weight=88_000.0,
    )
    db.commit()

    payload = realtime_service.build_pending_assignment_detail(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=User(id=7, username='admin', password_hash='x', name='Admin', role='admin'),
    )

    assert payload['business_date'] == '2026-05-06'
    assert payload['total'] == 1
    assert payload['summary'] == {
        'entry_count': 1,
        'draft_entry_count': 1,
        'formal_entry_count': 0,
        'missing_machine_count': 1,
        'missing_shift_count': 0,
        'input': 100.0,
        'output': 96.0,
        'scrap': 4.0,
    }
    assert payload['items'] == [
        {
            'entry_id': 101,
            'work_order_id': 101,
            'tracking_card_no': 'RA260506001',
            'business_date': '2026-05-06',
            'workshop_id': 2,
            'workshop_name': '2050冷轧车间',
            'shift_id': 3,
            'shift_name': '夜班',
            'machine_id': None,
            'entry_status': 'draft',
            'entry_type': 'mobile_coil',
            'input_weight': 100.0,
            'output_weight': 96.0,
            'scrap_weight': 4.0,
            'missing_fields': ['machine_id'],
            'created_by_user_id': 9,
            'created_by_user_name': '主操甲',
            'created_by_username': 'op-a',
            'mes_match_count': 1,
            'mes_machine_id': 11,
            'mes_machine_name': '1#轧机',
            'machine_candidate_count': 1,
            'machine_candidate_names': ['1#轧机'],
            'created_at': payload['items'][0]['created_at'],
        }
    ]


def test_build_pending_assignment_detail_respects_workshop_scope(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            Workshop(id=3, code='JZ', name='精整车间', sort_order=2, is_active=True),
            ShiftConfig(
                id=3,
                code='N',
                name='夜班',
                shift_type='night',
                start_time=time(20, 0),
                end_time=time(8, 0),
                is_cross_day=True,
                sort_order=3,
                is_active=True,
            ),
        ]
    )
    seed_pending_assignment_entry(
        db,
        entry_id=201,
        tracking_card_no='RA260506201',
        workshop_id=2,
        shift_id=3,
        machine_id=None,
    )
    seed_pending_assignment_entry(
        db,
        entry_id=301,
        tracking_card_no='RA260506301',
        workshop_id=3,
        shift_id=3,
        machine_id=None,
    )
    db.commit()

    payload = realtime_service.build_pending_assignment_detail(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=User(
            id=8,
            username='workshop-reviewer',
            password_hash='x',
            name='Workshop Reviewer',
            role='workshop_director',
            workshop_id=2,
            data_scope_type='self_workshop',
        ),
    )

    assert payload['workshop_id'] == 2
    assert payload['total'] == 1
    assert payload['items'][0]['tracking_card_no'] == 'RA260506201'


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

    assert payload['overall_progress'] == {
        'submitted_cells': 1,
        'total_cells': 4,
        'missing_cell_count': 2,
        'attention_cell_count': 4,
        'completion_rate': 25.0,
        'formal_entry_count': 1,
        'draft_entry_count': 1,
        'total_entry_count': 2,
    }
    assert payload['factory_total']['output'] == 17.4
    assert payload['workshops'][0]['workshop_name'] == '冷轧2050车间'
    assert payload['workshops'][0]['workshop_total']['yield_rate'] == 96.67
    assert payload['workshops'][0]['machines'][0]['machine_name'] == '1#'
    assert payload['workshops'][0]['machines'][0]['shifts'][0]['submitted_count'] == 1
    assert payload['workshops'][0]['machines'][0]['shifts'][0]['draft_count'] == 0
    assert payload['workshops'][0]['machines'][0]['shifts'][0]['total_expected'] == 8
    assert payload['workshops'][0]['machines'][0]['shifts'][0]['attendance_status'] == 'confirmed'
    assert payload['workshops'][0]['machines'][0]['shifts'][1]['submission_status'] == 'in_progress'
    assert payload['workshops'][0]['machines'][0]['shifts'][1]['draft_count'] == 1
    assert payload['workshops'][0]['machines'][1]['shifts'][0]['submission_status'] == 'not_started'


def test_aggregate_live_payload_counts_unbound_draft_intake_without_output_totals() -> None:
    workshops = [
        SimpleNamespace(id=2, name='冷轧2050车间'),
    ]
    machines = [
        SimpleNamespace(id=11, workshop_id=2, name='1#'),
    ]
    shifts = [
        SimpleNamespace(id=1, name='白班', sort_order=1),
    ]
    entries = [
        {
            'id': 103,
            'tracking_card_no': 'RA240003',
            'work_order_id': 3,
            'workshop_id': 2,
            'machine_id': None,
            'shift_id': None,
            'business_date': '2026-03-27',
            'input_weight': 100000.0,
            'output_weight': 96000.0,
            'scrap_weight': 4000.0,
            'yield_rate': None,
            'entry_status': 'draft',
            'entry_type': 'in_progress',
            'tracking_card_status': 'in_progress',
            'weight_unit': 'kg',
        },
    ]

    payload = realtime_service.aggregate_live_payload(
        workshops=workshops,
        machines=machines,
        shifts=shifts,
        entries=entries,
        attendance={},
        expected_counts={},
    )

    assert payload['overall_progress']['formal_entry_count'] == 0
    assert payload['overall_progress']['draft_entry_count'] == 1
    assert payload['overall_progress']['total_entry_count'] == 1
    assert payload['overall_progress']['pending_assignment']['entry_count'] == 1
    assert payload['overall_progress']['pending_assignment']['draft_entry_count'] == 1
    assert payload['overall_progress']['pending_assignment']['missing_machine_count'] == 1
    assert payload['overall_progress']['pending_assignment']['missing_shift_count'] == 1
    assert payload['overall_progress']['pending_assignment']['output'] == 96.0
    assert payload['workshops'][0]['workshop_total']['formal_entry_count'] == 0
    assert payload['workshops'][0]['workshop_total']['draft_entry_count'] == 1
    assert payload['workshops'][0]['workshop_total']['total_entry_count'] == 1
    assert payload['factory_total']['output'] == 0.0
    assert payload['workshops'][0]['machines'][0]['shifts'][0]['total_output'] == 0.0


def test_aggregate_live_payload_summarizes_machine_missing_shift_bound_drafts() -> None:
    workshops = [
        SimpleNamespace(id=2, name='冷轧2050车间'),
    ]
    machines = [
        SimpleNamespace(id=11, workshop_id=2, name='1#'),
    ]
    shifts = [
        SimpleNamespace(id=3, name='夜班', sort_order=3),
    ]
    entries = [
        {
            'id': 104,
            'tracking_card_no': 'RA240004',
            'work_order_id': 4,
            'workshop_id': 2,
            'machine_id': None,
            'shift_id': 3,
            'business_date': '2026-03-27',
            'input_weight': 100000.0,
            'output_weight': 96000.0,
            'scrap_weight': 4000.0,
            'yield_rate': None,
            'entry_status': 'draft',
            'entry_type': 'mobile_coil',
            'tracking_card_status': 'in_progress',
            'weight_unit': 'kg',
        },
    ]

    payload = realtime_service.aggregate_live_payload(
        workshops=workshops,
        machines=machines,
        shifts=shifts,
        entries=entries,
        attendance={},
        expected_counts={},
    )

    pending = payload['overall_progress']['pending_assignment']
    assert pending['entry_count'] == 1
    assert pending['draft_entry_count'] == 1
    assert pending['formal_entry_count'] == 0
    assert pending['missing_machine_count'] == 1
    assert pending['missing_shift_count'] == 0
    assert pending['workshop_count'] == 1
    assert pending['shift_count'] == 1
    assert pending['output'] == 96.0
    assert pending['rows'] == [
        {
            'workshop_id': 2,
            'workshop_name': '冷轧2050车间',
            'shift_id': 3,
            'shift_name': '夜班',
            'entry_count': 1,
            'draft_entry_count': 1,
            'formal_entry_count': 0,
            'missing_machine_count': 1,
            'missing_shift_count': 0,
            'input': 100.0,
            'output': 96.0,
        }
    ]
    assert payload['factory_total']['output'] == 0.0
    assert payload['workshops'][0]['machines'][0]['shifts'][0]['draft_count'] == 0


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
    assert payload['overall_progress'] == {
        'submitted_cells': 0,
        'total_cells': 2,
        'missing_cell_count': 2,
        'attention_cell_count': 2,
        'completion_rate': 0.0,
        'formal_entry_count': 0,
        'draft_entry_count': 0,
        'total_entry_count': 0,
    }
    assert len(machine['shifts']) == 3
    assert machine['shifts'][2]['is_applicable'] is False
    assert machine['shifts'][2]['submission_status'] == 'not_applicable'
    assert machine['shifts'][2]['attendance_status'] == 'not_applicable'


def test_mobile_shift_aggregate_rows_create_unbound_live_machine() -> None:
    workshops = [
        SimpleNamespace(id=5, name='2050冷轧车间'),
    ]
    machines = [
        SimpleNamespace(id=12, workshop_id=5, name='2#轧机', assigned_shift_ids=[1, 3], sort_order=2),
    ]
    shifts = [
        SimpleNamespace(id=1, name='1班', sort_order=1),
        SimpleNamespace(id=3, name='3班', sort_order=3),
    ]
    rows = [
        SimpleNamespace(
            id=501,
            workshop_id=5,
            equipment_id=None,
            shift_config_id=3,
            business_date=date(2026, 5, 6),
            input_weight=80_000.0,
            output_weight=74_110.0,
            scrap_weight=1_500.0,
            data_status='pending',
            data_source='mobile_coil_agg',
        )
    ]

    local_machines, entries = realtime_service._build_local_shift_runtime_inputs(
        machines=machines,
        shifts=shifts,
        rows=rows,
    )
    payload = realtime_service.aggregate_live_payload(
        workshops=workshops,
        machines=local_machines,
        shifts=shifts,
        entries=entries,
        attendance={(5, 3): {'status': 'confirmed', 'exception_count': 0}},
        expected_counts={},
    )

    unbound_machine = payload['workshops'][0]['machines'][1]
    assert entries[0]['weight_unit'] == 'kg'
    assert payload['factory_total']['output'] == 74.11
    assert payload['workshops'][0]['machines'][0]['machine_binding_status'] == 'bound'
    assert unbound_machine['machine_name'] == '未绑定机列 / 3班'
    assert unbound_machine['machine_binding_status'] == 'unbound'
    assert unbound_machine['shifts'][1]['submitted_count'] == 1
    assert unbound_machine['shifts'][1]['submission_status'] == 'all_submitted'
    assert unbound_machine['shifts'][1]['total_output'] == 74.11


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
