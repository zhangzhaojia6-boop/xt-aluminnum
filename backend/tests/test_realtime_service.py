from datetime import date, datetime, time
from types import SimpleNamespace

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.consumable import DailyConsumableLog
from app.models.energy import MachineEnergyRecord
from app.models.master import Equipment, MasterCodeAlias, MesTerminalBinding, Team, Workshop
from app.models.mes import MesCoilSnapshot, MesMaterialRecord, MesWorkshopProcessRecord
from app.models.production import MobileShiftReport, ShiftProductionData, WorkOrder, WorkOrderEntry
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
            MesTerminalBinding.__table__,
            ShiftConfig.__table__,
            ShiftProductionData.__table__,
            MobileShiftReport.__table__,
            MachineEnergyRecord.__table__,
            DailyConsumableLog.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            MesCoilSnapshot.__table__,
            MesMaterialRecord.__table__,
            MesWorkshopProcessRecord.__table__,
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
    entry_type: str = 'mobile_coil',
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
            entry_type=entry_type,
            created_by_user_id=9,
        )
    )


def test_build_pending_assignment_detail_ignores_owner_daily_rows(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            User(id=9, username='owner-a', password_hash='x', name='内勤甲', role='consumable_stat', is_active=True),
        ]
    )
    seed_pending_assignment_entry(
        db,
        entry_id=121,
        tracking_card_no='OWNER-121',
        workshop_id=2,
        shift_id=None,
        machine_id=None,
        entry_type='owner_daily',
    )
    db.commit()

    payload = realtime_service.build_pending_assignment_detail(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=admin_user(),
    )

    assert payload['total'] == 0
    assert payload['summary']['entry_count'] == 0


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


def test_build_live_aggregation_uses_mes_weight_when_mes_projection_exists(tmp_path, monkeypatch) -> None:
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
    assert payload['factory_total']['output'] == 5.2
    machine = payload['workshops'][0]['machines'][0]
    assert machine['machine_binding_status'] == 'bound'
    assert machine['day_total']['output'] == 5.2
    assert machine['shifts'][0]['submitted_count'] == 2


def test_build_fill_detail_ledger_includes_machine_energy_without_double_counting(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050# 主操', workshop_id=2, is_active=True),
            User(id=85, username='electrician', password_hash='x', name='电工张', role='machine_operator'),
            MobileShiftReport(
                id=901,
                business_date=date(2026, 5, 6),
                shift_config_id=3,
                workshop_id=2,
                submitted_by_user_id=85,
                leader_name='电工张',
                output_weight=12.5,
                electricity_daily=100.0,
                gas_daily=8.0,
                report_status='submitted',
                submitted_at=datetime(2026, 5, 6, 23, 20),
            ),
            MachineEnergyRecord(
                id=902,
                shift_report_id=901,
                machine_id=11,
                machine_code='LZ2050-1',
                machine_name='2050# 主操',
                energy_kwh=88.0,
                gas_m3=7.0,
            ),
        ]
    )
    db.commit()

    payload = realtime_service.build_fill_detail_ledger(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=admin_user(),
        search='电工张',
    )

    assert payload['summary']['source_counts']['machine_energy'] == 1
    assert payload['summary']['source_counts']['mobile_shift_report'] == 1
    assert payload['summary']['energy_kwh'] == 88.0
    assert payload['summary']['gas_m3'] == 7.0
    assert payload['items'][0]['responsible_name'] == '电工张'


def test_build_fill_detail_ledger_excludes_mes_projection_rows(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=1, code='A', name='长白班', shift_type='day', start_time=time(7, 30), end_time=time(15, 30), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050# 主操', workshop_id=2, is_active=True),
            MesCoilSnapshot(
                id=1201,
                coil_id='mes-coil-1',
                tracking_card_no='MES-001',
                workshop_code='LZ2050',
                machine_code='LZ2050-1',
                shift_code='A',
                status='synced',
                business_date=date(2026, 5, 6),
                source_payload={'output_weight': 9600},
            ),
        ]
    )
    db.commit()

    payload = realtime_service.build_fill_detail_ledger(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=admin_user(),
    )

    assert payload['summary']['source_counts'].get('mes_projection') is None
    assert payload['summary']['entry_count'] == 0
    assert payload['items'] == []


def test_build_fill_detail_ledger_excludes_mes_projection_work_order_entries(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=1, code='A', name='长白班', shift_type='day', start_time=time(7, 30), end_time=time(15, 30), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050# 主操', workshop_id=2, is_active=True),
            User(id=85, username='operator', password_hash='x', name='主操王', role='machine_operator'),
            WorkOrder(id=601, tracking_card_no='TRACK-FILL-1', process_route_code='mobile', overall_status='created'),
            WorkOrder(id=602, tracking_card_no='TRACK-MES-1', process_route_code='mes', overall_status='created'),
            WorkOrderEntry(
                id=701,
                work_order_id=601,
                workshop_id=2,
                machine_id=11,
                shift_id=1,
                business_date=date(2026, 5, 6),
                output_weight=9600.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_by_user_id=85,
                submitted_at=datetime(2026, 5, 6, 9, 10),
            ),
            WorkOrderEntry(
                id=702,
                work_order_id=602,
                workshop_id=2,
                machine_id=11,
                shift_id=1,
                business_date=date(2026, 5, 6),
                output_weight=12000.0,
                entry_status='submitted',
                entry_type='mes_projection',
                created_by_user_id=85,
                submitted_at=datetime(2026, 5, 6, 9, 11),
            ),
        ]
    )
    db.commit()

    payload = realtime_service.build_fill_detail_ledger(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=admin_user(),
    )

    assert payload['summary']['source_counts'] == {'work_order_entry': 1}
    assert payload['summary']['output'] == 9.6
    assert [item['tracking_card_no'] for item in payload['items']] == ['TRACK-FILL-1']


def test_build_fill_detail_ledger_limits_entry_query_before_loading(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=1, code='A', name='长白班', shift_type='day', start_time=time(7, 30), end_time=time(15, 30), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050# 主操', workshop_id=2, is_active=True),
            User(id=85, username='operator', password_hash='x', name='主操王', role='machine_operator'),
        ]
    )
    for index in range(5):
        db.add(WorkOrder(id=700 + index, tracking_card_no=f'TRACK-LIMIT-{index}', process_route_code='mobile', overall_status='created'))
        db.add(
            WorkOrderEntry(
                id=800 + index,
                work_order_id=700 + index,
                workshop_id=2,
                machine_id=11,
                shift_id=1,
                business_date=date(2026, 5, 6),
                output_weight=1000.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_by_user_id=85,
                submitted_at=datetime(2026, 5, 6, 9, index),
            )
        )
    db.commit()

    statements: list[str] = []
    bind = db.get_bind()

    def record_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(bind, 'before_cursor_execute', record_sql)
    try:
        payload = realtime_service.build_fill_detail_ledger(
            db,
            business_date=date(2026, 5, 6),
            workshop_id=None,
            current_user=admin_user(),
            limit=2,
        )
    finally:
        event.remove(bind, 'before_cursor_execute', record_sql)

    entry_selects = [statement.lower() for statement in statements if 'work_order_entries' in statement.lower()]
    assert payload['summary']['source_counts'] == {'work_order_entry': 2}
    assert any('limit' in statement for statement in entry_selects)


def test_build_fill_detail_ledger_exposes_template_extra_payload_metrics(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='ZR3', name='铸三车间', workshop_type='casting', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='大夜', shift_type='night', start_time=time(23, 30), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='ZR3-1', name='铸三1#', workshop_id=2, is_active=True),
            User(id=85, username='operator', password_hash='x', name='主操王', role='machine_operator'),
            User(id=86, username='energy-chief', password_hash='x', name='总电工李', role='energy_chief'),
            WorkOrder(id=601, tracking_card_no='TRACK-ZR3-1', process_route_code='mobile', overall_status='created'),
            WorkOrder(id=602, tracking_card_no='OWNER-energy_chief-86-2026-05-06', process_route_code='owner_daily', overall_status='created'),
            WorkOrderEntry(
                id=701,
                work_order_id=601,
                workshop_id=2,
                machine_id=11,
                shift_id=3,
                business_date=date(2026, 5, 6),
                input_weight=1000.0,
                output_weight=960.0,
                scrap_weight=40.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_by_user_id=85,
                submitted_at=datetime(2026, 5, 6, 7, 40),
                extra_payload={
                    'ingot_spec': '6×1600',
                    'cast_speed': 720,
                    'skin_weight': 12,
                },
            ),
            WorkOrderEntry(
                id=702,
                work_order_id=602,
                workshop_id=2,
                machine_id=None,
                shift_id=None,
                business_date=date(2026, 5, 6),
                entry_status='submitted',
                entry_type='owner_daily',
                created_by_user_id=86,
                submitted_at=datetime(2026, 5, 7, 8, 20),
                extra_payload={
                    'total_electricity_kwh': 1200,
                    'hydraulic_oil_daily': 2,
                    'contract_no': 'HT-001',
                },
            ),
        ]
    )
    db.commit()

    payload = realtime_service.build_fill_detail_ledger(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=admin_user(),
    )

    rows = {item['row_id']: item for item in payload['items']}
    operator_metrics = {(item['label'], item['value'], item['unit']) for item in rows['entry-701']['metrics']}
    owner_metrics = {(item['label'], item['value'], item['unit']) for item in rows['entry-702']['metrics']}
    assert ('规格', '6×1600', '') in operator_metrics
    assert ('速度', 720.0, 'mm/min') in operator_metrics
    assert ('皮料段', 12.0, 'kg') in operator_metrics
    assert ('全厂用电', 1200.0, 'kWh') in owner_metrics
    assert ('液压油日用', 2.0, '桶') in owner_metrics
    assert ('合同号', 'HT-001', '') in owner_metrics
    assert payload['summary']['energy_kwh'] == 1200.0


def test_fill_detail_meta_covers_direct_owner_role_fields() -> None:
    expected = {
        'daily_shearing_output': ('当日剪切产量', '吨'),
        'recovery_weight': ('回收重量', '块'),
        'roller_grinding_count': ('磨辊子数量', '个'),
        'overhaul_energy_kwh': ('大修用电', 'kWh'),
    }

    for key, meta in expected.items():
        assert realtime_service.FILL_DETAIL_FIELD_META[key] == meta


def test_owner_daily_status_uses_actual_submitted_owner_qr_before_canonical_duplicate(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=23, code='HS', name='回收车间', workshop_type='recycling', sort_order=1, is_active=True),
            User(id=930, username='HS-CS', password_hash='x', name='回收车间内勤', role='consumable_stat', workshop_id=23, is_active=True),
            User(id=939, username='HS-RC', password_hash='x', name='回收车间回收', role='recovery_owner', workshop_id=23, is_active=True),
            WorkOrder(id=3514, tracking_card_no='OWNER-consumable_stat-930-2026-06-17', process_route_code='owner_daily', overall_status='created'),
            WorkOrderEntry(
                id=3514,
                work_order_id=3514,
                workshop_id=23,
                machine_id=None,
                shift_id=None,
                business_date=date(2026, 6, 17),
                entry_status='submitted',
                entry_type='owner_daily',
                created_by_user_id=930,
                submitted_at=datetime(2026, 6, 17, 15, 17),
                updated_at=datetime(2026, 6, 17, 15, 18),
                extra_payload={'recovery_weight': 63, 'recovery_material_type': '渣锭屑锭'},
            ),
        ]
    )
    db.commit()

    payload = realtime_service._build_owner_daily_status(
        db,
        business_date=date(2026, 6, 17),
        workshop_id=None,
    )

    assert payload['submitted_count'] == 1
    assert payload['total_count'] == 1
    item = payload['items'][0]
    assert item['username'] == 'HS-CS'
    assert item['effective_role'] == 'recovery_owner'
    assert item['role_label'] == '回收'
    assert item['entry_id'] == 3514
    assert payload['totals'][0]['key'] == 'recovery_weight'
    assert payload['totals'][0]['value'] == 63


def test_build_live_aggregation_reports_formal_mobile_entries_missing_output_weight(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050# 主操', workshop_id=2, is_active=True),
            WorkOrder(id=602, tracking_card_no='RA260506602', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=602,
                work_order_id=602,
                workshop_id=2,
                machine_id=11,
                shift_id=3,
                business_date=date(2026, 5, 6),
                input_weight=100_000.0,
                output_weight=None,
                scrap_weight=4_000.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_by_user_id=85,
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

    missing = payload['data_quality']['missing_output_weight']
    assert missing['entry_count'] == 1
    assert missing['input'] == 100.0
    assert missing['scrap'] == 4.0
    assert missing['items'] == [
        {
            'entry_id': 602,
            'work_order_id': 602,
            'tracking_card_no': 'RA260506602',
            'workshop_id': 2,
            'workshop_name': '2050冷轧车间',
            'machine_id': 11,
            'machine_name': '2050# 主操',
            'shift_id': 3,
            'shift_name': '夜班',
            'input_weight': 100.0,
            'output_weight': None,
            'scrap_weight': 4.0,
            'entry_status': 'submitted',
            'entry_type': 'mobile_coil',
        }
    ]


def test_resolve_missing_output_weight_updates_submitted_mobile_entry_and_clears_quality(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050# 主操', workshop_id=2, is_active=True),
            WorkOrder(id=603, tracking_card_no='RA260506603', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=603,
                work_order_id=603,
                workshop_id=2,
                machine_id=11,
                shift_id=3,
                business_date=date(2026, 5, 6),
                input_weight=100_000.0,
                output_weight=None,
                scrap_weight=4_000.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_by_user_id=85,
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr('app.services.work_order.entry.record_entity_change', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order.entry.event_bus.publish', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order.entry._resolve_entry_template_key', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(realtime_service, '_build_attendance_summary', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, '_build_expected_count_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, 'build_yield_matrix_projection', lambda *_args, **_kwargs: {})

    result = realtime_service.resolve_missing_output_weight(
        db,
        entry_id=603,
        output_weight=96.0,
        reason='现场复核产出重量',
        current_user=admin_user(),
    )

    entry = db.get(WorkOrderEntry, 603)
    assert entry.output_weight == 96_000.0
    assert result['entry_id'] == 603
    assert result['output_weight'] == 96.0
    assert result['yield_rate'] == 96.0

    payload = realtime_service.build_live_aggregation(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=admin_user(),
    )
    assert payload['data_quality']['missing_output_weight']['entry_count'] == 0


def test_resolve_missing_output_weight_rejects_output_above_input(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            WorkOrder(id=604, tracking_card_no='RA260506604', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=604,
                work_order_id=604,
                workshop_id=2,
                machine_id=None,
                shift_id=None,
                business_date=date(2026, 5, 6),
                input_weight=100_000.0,
                output_weight=None,
                scrap_weight=4_000.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_by_user_id=85,
            ),
        ]
    )
    db.commit()

    try:
        realtime_service.resolve_missing_output_weight(
            db,
            entry_id=604,
            output_weight=101.0,
            reason='现场复核产出重量',
            current_user=admin_user(),
        )
    except Exception as exc:  # noqa: BLE001
        assert getattr(exc, 'status_code', None) == 422
        assert getattr(exc, 'detail', None) == 'output_weight_exceeds_input'
    else:
        raise AssertionError('expected output_weight_exceeds_input')


def test_resolve_missing_output_weight_rejects_out_of_scope_before_weight_validation(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            Workshop(id=3, code='ZL', name='铸轧车间', sort_order=2, is_active=True),
            WorkOrder(id=605, tracking_card_no='RA260506605', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=605,
                work_order_id=605,
                workshop_id=2,
                machine_id=None,
                shift_id=None,
                business_date=date(2026, 5, 6),
                input_weight=100_000.0,
                output_weight=None,
                scrap_weight=4_000.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_by_user_id=85,
            ),
        ]
    )
    db.commit()

    scoped_user = User(
        id=8,
        username='shift-leader',
        password_hash='x',
        name='Shift leader',
        role='shift_leader',
        workshop_id=3,
        data_scope_type='self_workshop',
    )
    try:
        realtime_service.resolve_missing_output_weight(
            db,
            entry_id=605,
            output_weight=101.0,
            reason='现场复核产出重量',
            current_user=scoped_user,
        )
    except Exception as exc:  # noqa: BLE001
        assert getattr(exc, 'status_code', None) == 403
        assert getattr(exc, 'detail', None) == 'work order entry access denied'
    else:
        raise AssertionError('expected work_order_entry access denial')


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


def test_build_live_aggregation_replaces_matched_fill_weight_with_same_day_mes_weight(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050轧机', workshop_id=2, is_active=True),
            WorkOrder(id=1703, tracking_card_no='RA2605061703', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=1703,
                work_order_id=1703,
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
                id=1703,
                coil_id='MES-1703',
                tracking_card_no='RA2605061703',
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
    assert payload['factory_total']['output'] == 5.2
    machine = payload['workshops'][0]['machines'][0]
    assert machine['day_total']['output'] == 5.2
    assert machine['shifts'][0]['total_output'] == 5.2


def test_mtd_totals_use_mes_material_for_hot_roll_and_process_for_downstream(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=1, code='RZ', name='热轧车间', workshop_type='hot_roll', sort_order=1, is_active=True),
            Workshop(id=2, code='LZ1650', name='1650车间', workshop_type='cold_roll', sort_order=2, is_active=True),
            MesMaterialRecord(
                source_id='mat-hot-roll',
                source_path='sqlserver:material_records',
                material_code='mat-hot-roll',
                workshop_name='热轧车间',
                line_name='1#',
                weight_kg=70000,
                weight_tons=70,
                production_date=datetime(2026, 6, 16, 8, 0),
            ),
            MesWorkshopProcessRecord(
                source_id='mes-cold-1650',
                source_path='sqlserver',
                workshop_name='1650车间',
                process_name='冷轧',
                output_weight_tons=33,
                business_date=date(2026, 6, 16),
                source_payload={'pass_count': 11},
            ),
        ]
    )
    db.commit()

    payload = realtime_service._build_mtd_totals(
        db,
        business_date=date(2026, 6, 16),
        workshop_ids=[1, 2],
        workshop_id=None,
    )

    assert payload['by_workshop'][1]['mtd_output'] == 70.0
    assert payload['by_workshop'][1]['source_basis'] == 'mes_material_records'
    assert payload['by_workshop'][2]['mtd_output'] == 0.0
    assert payload['by_workshop'][2]['mtd_process_output'] == 33.0
    assert payload['by_workshop'][2]['source_basis'] == 'mes_workshop_process_records'
    assert payload['factory']['mtd_output'] == 70.0
    assert payload['factory']['mtd_process_output'] == 103.0


def test_live_aggregation_uses_mes_process_and_material_machine_output(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=1, code='RZ', name='热轧车间', workshop_type='hot_roll', sort_order=1, is_active=True),
            Workshop(id=2, code='LZ1650', name='1650车间', workshop_type='cold_roll', sort_order=2, is_active=True),
            ShiftConfig(id=3, code='D', name='白班', shift_type='day', start_time=time(8, 0), end_time=time(20, 0), is_active=True),
            Equipment(
                id=10,
                code='RZ-ZJ',
                name='热轧机',
                workshop_id=1,
                equipment_type='hot_mill',
                sort_order=1,
                is_active=True,
            ),
            Equipment(
                id=20,
                code='LZ1650-1',
                name='1650#',
                workshop_id=2,
                equipment_type='cold_mill',
                sort_order=1,
                is_active=True,
            ),
            MesMaterialRecord(
                source_id='mat-hot-roll-live',
                source_path='sqlserver:material_records',
                material_code='mat-hot-roll-live',
                workshop_name='热轧车间',
                line_name='1#',
                weight_kg=70000,
                weight_tons=70,
                production_date=datetime(2026, 6, 17, 8, 5),
            ),
            MesWorkshopProcessRecord(
                source_id='mes-cold-1650-live',
                source_path='sqlserver',
                workshop_name='1650车间',
                process_name='冷轧',
                device_name='1650冷轧（WAN）',
                input_weight_tons=35,
                output_weight_tons=33,
                business_date=date(2026, 6, 17),
                source_payload={'pass_count': 11},
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(realtime_service, '_build_attendance_summary', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, '_build_expected_count_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, 'build_yield_matrix_projection', lambda *_args, **_kwargs: {})

    payload = realtime_service.build_live_aggregation(
        db,
        business_date=date(2026, 6, 17),
        workshop_id=None,
        current_user=admin_user(),
    )

    hot_machine = payload['workshops'][0]['machines'][0]
    cold_machine = payload['workshops'][1]['machines'][0]
    assert hot_machine['day_total']['output'] == 70.0
    assert hot_machine['day_total']['source_basis'] == 'mes_material_records'
    assert cold_machine['day_total']['input'] == 35.0
    assert cold_machine['day_total']['output'] == 33.0
    assert cold_machine['day_total']['source_basis'] == 'mes_workshop_process_records'
    assert payload['workshops'][0]['workshop_total']['output'] == 70.0
    assert payload['workshops'][1]['workshop_total']['output'] == 33.0
    assert payload['factory_total']['output'] == 103.0
    assert payload['factory_total']['process_output'] == 103.0
    assert payload['factory_total']['source_basis'] == 'mes_machine_output'


def test_live_aggregation_keeps_park_online_and_unresolved_mes_process_output(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=3, code='ZXTF-P', name='园区在线退火', workshop_type='annealing', sort_order=1, is_active=True),
            Workshop(id=4, code='JZ', name='精整车间', workshop_type='finishing', sort_order=2, is_active=True),
            ShiftConfig(id=3, code='D', name='白班', shift_type='day', start_time=time(8, 0), end_time=time(20, 0), is_active=True),
            Equipment(
                id=31,
                code='ZXTF-3',
                name='园区北',
                workshop_id=3,
                equipment_type='annealing_line',
                sort_order=1,
                is_active=True,
            ),
            Equipment(
                id=41,
                code='JZ-ZJ-Z',
                name='纵剪',
                workshop_id=4,
                equipment_type='slitter',
                sort_order=1,
                is_active=True,
            ),
            MesWorkshopProcessRecord(
                source_id='park-online-live',
                source_path='sqlserver',
                workshop_name='园区在线车间',
                process_name='在线退火',
                device_name='园区北线（WIFI）',
                input_weight_tons=123.52,
                output_weight_tons=121.8,
                business_date=date(2026, 6, 17),
            ),
            MesWorkshopProcessRecord(
                source_id='finishing-packaging-pc',
                source_path='sqlserver',
                workshop_name='精整',
                process_name='包装',
                device_name='PC',
                input_weight_tons=81.89,
                output_weight_tons=84.16,
                business_date=date(2026, 6, 17),
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(realtime_service, '_build_attendance_summary', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, '_build_expected_count_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, 'build_yield_matrix_projection', lambda *_args, **_kwargs: {})

    payload = realtime_service.build_live_aggregation(
        db,
        business_date=date(2026, 6, 17),
        workshop_id=None,
        current_user=admin_user(),
    )

    park_machine = payload['workshops'][0]['machines'][0]
    finishing_machines = payload['workshops'][1]['machines']
    unresolved = next(item for item in finishing_machines if str(item['machine_name']).startswith('MES未匹配机台 / 包装'))
    assert park_machine['machine_name'] == '园区北'
    assert park_machine['day_total']['output'] == 121.8
    assert payload['workshops'][0]['workshop_total']['output'] == 121.8
    assert unresolved['day_total']['output'] == 84.16
    assert unresolved['machine_binding_status'] == 'unbound'
    assert payload['workshops'][1]['workshop_total']['output'] == 84.16
    assert payload['factory_total']['output'] == 205.96


def test_live_aggregation_maps_scoped_packaging_pc_to_packaging_machine(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=4, code='JZ', name='精整车间', workshop_type='finishing', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='D', name='白班', shift_type='day', start_time=time(8, 0), end_time=time(20, 0), is_active=True),
            Equipment(
                id=41,
                code='JZ-BZJ',
                name='包装机',
                workshop_id=4,
                equipment_type='packaging_machine',
                sort_order=2,
                is_active=True,
            ),
            MesTerminalBinding(
                terminal_code='PC',
                terminal_name='精整包装PC',
                mes_device_name='PC',
                workshop_name='精整车间',
                process_name='包装',
                equipment_id=41,
                confidence='high',
                is_active=True,
            ),
            MesWorkshopProcessRecord(
                source_id='finishing-packaging-pc',
                source_path='sqlserver',
                workshop_name='精整',
                process_name='包装',
                device_name='PC',
                input_weight_tons=81.89,
                output_weight_tons=84.16,
                business_date=date(2026, 6, 17),
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(realtime_service, '_build_attendance_summary', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, '_build_expected_count_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, 'build_yield_matrix_projection', lambda *_args, **_kwargs: {})

    payload = realtime_service.build_live_aggregation(
        db,
        business_date=date(2026, 6, 17),
        workshop_id=None,
        current_user=admin_user(),
    )

    machine = payload['workshops'][0]['machines'][0]
    assert machine['machine_id'] == 41
    assert machine['machine_name'] == '包装机'
    assert machine['machine_binding_status'] == 'bound'
    assert machine['day_total']['output'] == 84.16
    assert machine['day_total']['binding_sources'] == {'mes_terminal_binding': 1}


def test_build_live_aggregation_infers_mes_machine_from_route_when_device_missing(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(
                id=11,
                code='LZ2050-1',
                name='2050轧机',
                workshop_id=2,
                equipment_type='cold_mill',
                is_active=True,
            ),
            MasterCodeAlias(
                entity_type='workshop',
                canonical_code='LZ2050',
                alias_code='2050车间',
                alias_name='2050车间',
                source_type='mes_mvc',
                is_active=True,
            ),
            WorkOrder(id=706, tracking_card_no='RA260506706', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=706,
                work_order_id=706,
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
                id=706,
                coil_id='MES-706',
                tracking_card_no='RA260506706',
                workshop_code=None,
                process_code=None,
                machine_code=None,
                shift_code='N',
                next_workshop='2050车间',
                next_process='冷轧',
                status='synced',
                business_date=None,
                source_payload={'NextWorkShop': '2050车间', 'NextProcess': '冷轧'},
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
    assert 'pending_assignment' not in payload['overall_progress']
    machine = payload['workshops'][0]['machines'][0]
    assert machine['machine_id'] == 11
    assert machine['shifts'][0]['submitted_count'] == 1
    assert machine['shifts'][0]['total_output'] == 9.7


def test_build_live_aggregation_infers_north_annealing_line_from_route(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=29, code='ZXTF-N', name='新厂在线退火', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=149, code='ZXTF-1', name='新厂北', workshop_id=29, equipment_type='annealing_line', is_active=True),
            Equipment(id=150, code='ZXTF-2', name='新厂南', workshop_id=29, equipment_type='annealing_line', is_active=True),
            MasterCodeAlias(
                entity_type='workshop',
                canonical_code='ZXTF-N',
                alias_code='新厂在线车间',
                alias_name='新厂在线车间',
                source_type='mes_mvc',
                is_active=True,
            ),
            MesCoilSnapshot(
                id=713,
                coil_id='MES-713',
                tracking_card_no='R2-7316-3',
                workshop_code='新厂在线车间',
                machine_code=None,
                shift_code='N',
                current_process='北线退火',
                status='synced',
                business_date=date(2026, 6, 16),
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(realtime_service, '_build_attendance_summary', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, '_build_expected_count_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, 'build_yield_matrix_projection', lambda *_args, **_kwargs: {})

    payload = realtime_service.build_live_aggregation(
        db,
        business_date=date(2026, 6, 16),
        workshop_id=None,
        current_user=admin_user(),
    )

    assert payload['mes_machine_binding']['mes_rows_with_machine'] == 1
    assert payload['mes_machine_binding']['route_inferred_machine_count'] == 1
    assert payload['mes_machine_binding']['unresolved_machine_count'] == 0


def test_build_live_aggregation_uses_mes_terminal_binding(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=4, code='JZ', name='精整车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=21, code='JZ-ZJ1', name='纵剪1#', workshop_id=4, equipment_type='slitter', is_active=True),
            Equipment(id=22, code='JZ-ZJ2', name='纵剪2#', workshop_id=4, equipment_type='slitter', is_active=True),
            MesTerminalBinding(
                terminal_code='PC-JZ-01',
                terminal_name='精整一号终端',
                workshop_name='精整车间',
                process_name='纵剪',
                equipment_id=21,
                confidence='high',
                is_active=True,
            ),
            MesCoilSnapshot(
                id=714,
                coil_id='MES-714',
                tracking_card_no='RA260506714',
                workshop_code='JZ',
                machine_code=None,
                shift_code='N',
                current_process='纵剪',
                status='synced',
                business_date=date(2026, 5, 6),
                source_payload={'DeviceCode': 'PC-JZ-01'},
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

    assert payload['mes_machine_binding']['mes_rows_with_machine'] == 1
    assert payload['mes_machine_binding']['unresolved_machine_count'] == 0
    assert payload['mes_machine_binding']['mes_rows_without_machine'] == 0


def test_build_live_aggregation_keeps_ambiguous_mes_route_unassigned(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=4, code='JZ', name='精整车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=21, code='JZ-ZJ1', name='纵剪1#', workshop_id=4, equipment_type='slitter', is_active=True),
            Equipment(id=22, code='JZ-ZJ2', name='纵剪2#', workshop_id=4, equipment_type='slitter', is_active=True),
            WorkOrder(id=708, tracking_card_no='RA260506708', process_route_code='slitting', overall_status='created'),
            WorkOrderEntry(
                id=708,
                work_order_id=708,
                workshop_id=4,
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
                id=708,
                coil_id='MES-708',
                tracking_card_no='RA260506708',
                workshop_code='JZ',
                machine_code=None,
                shift_code='N',
                next_process='纵剪',
                status='synced',
                business_date=None,
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

    pending = payload['overall_progress']['pending_assignment']
    assert pending['entry_count'] == 1
    assert pending['missing_machine_count'] == 1
    assert pending['missing_shift_count'] == 0
    assert pending['rows'][0]['missing_machine_count'] == 1


def test_build_live_aggregation_does_not_count_mes_projection_as_pending_assignment(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=4, code='JZ', name='精整车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=21, code='JZ-ZJ1', name='纵剪1#', workshop_id=4, equipment_type='slitter', is_active=True),
            Equipment(id=22, code='JZ-ZJ2', name='纵剪2#', workshop_id=4, equipment_type='slitter', is_active=True),
            MesCoilSnapshot(
                id=709,
                coil_id='MES-709',
                tracking_card_no='RA260506709',
                workshop_code='JZ',
                machine_code=None,
                shift_code=None,
                next_process='纵剪',
                status='synced',
                business_date=date(2026, 5, 6),
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
    assert 'pending_assignment' not in payload['overall_progress']
    assert payload['mes_machine_binding']['unresolved_machine_count'] == 1


def test_build_live_aggregation_exposes_current_and_active_business_date_context(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050轧机', workshop_id=2, is_active=True),
            WorkOrder(id=710, tracking_card_no='RA260506710', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=710,
                work_order_id=710,
                workshop_id=2,
                machine_id=11,
                shift_id=3,
                business_date=date(2026, 5, 6),
                input_weight=10_000.0,
                output_weight=9_700.0,
                scrap_weight=300.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_at=datetime(2026, 5, 7, 8, 10),
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(realtime_service, '_local_now', lambda: datetime(2026, 5, 7, 9, 30))
    monkeypatch.setattr(realtime_service, '_build_attendance_summary', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, '_build_expected_count_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, 'build_yield_matrix_projection', lambda *_args, **_kwargs: {})

    payload = realtime_service.build_live_aggregation(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=admin_user(),
    )

    context = payload['business_date_context']
    assert context == {
        'requested_business_date': '2026-05-06',
        'current_business_date': '2026-05-07',
        'active_business_date': '2026-05-06',
        'active_date_source': 'recent_upload',
        'latest_fill_business_date': '2026-05-06',
        'requested_entry_count': 1,
        'current_date_entry_count': 0,
        'active_date_entry_count': 1,
        'has_current_date_entries': False,
        'is_requested_current_date': False,
        'is_showing_active_business_date': True,
    }


def test_live_business_date_context_keeps_active_date_in_workshop_scope(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            Workshop(id=4, code='JZ', name='精整车间', sort_order=2, is_active=True),
            ShiftConfig(id=3, code='C', name='大夜班', shift_type='night', start_time=time(23, 30), end_time=time(7, 30), is_active=True),
            WorkOrder(id=720, tracking_card_no='RA260507720', process_route_code='cold-roll', overall_status='created'),
            WorkOrder(id=721, tracking_card_no='RA260506721', process_route_code='finishing', overall_status='created'),
            WorkOrderEntry(
                id=720,
                work_order_id=720,
                workshop_id=2,
                shift_id=3,
                business_date=date(2026, 5, 7),
                output_weight=9700.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_at=datetime(2026, 5, 7, 8, 0),
            ),
            WorkOrderEntry(
                id=721,
                work_order_id=721,
                workshop_id=4,
                shift_id=3,
                business_date=date(2026, 5, 6),
                output_weight=12000.0,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_at=datetime(2026, 5, 7, 8, 30),
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(realtime_service, '_local_now', lambda: datetime(2026, 5, 7, 9, 30))

    context = realtime_service._build_live_business_date_context(
        db,
        requested_date=date(2026, 5, 7),
        workshop_id=2,
    )

    assert context['current_business_date'] == '2026-05-07'
    assert context['active_business_date'] == '2026-05-07'
    assert context['latest_fill_business_date'] == '2026-05-07'
    assert context['active_date_entry_count'] == 1
    assert context['is_showing_active_business_date'] is True


def test_build_live_aggregation_exposes_mes_machine_binding_status(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            Workshop(id=4, code='JZ', name='精整车间', sort_order=2, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050轧机', workshop_id=2, equipment_type='cold_mill', is_active=True),
            Equipment(id=21, code='JZ-ZJ1', name='纵剪1#', workshop_id=4, equipment_type='slitter', is_active=True),
            Equipment(id=22, code='JZ-ZJ2', name='纵剪2#', workshop_id=4, equipment_type='slitter', is_active=True),
            MasterCodeAlias(
                entity_type='workshop',
                canonical_code='LZ2050',
                alias_code='2050车间',
                alias_name='2050车间',
                source_type='mes_mvc',
                is_active=True,
            ),
            WorkOrder(id=711, tracking_card_no='RA260506711', process_route_code='cold-roll', overall_status='created'),
            WorkOrder(id=712, tracking_card_no='RA260506712', process_route_code='slitting', overall_status='created'),
            WorkOrderEntry(
                id=711,
                work_order_id=711,
                workshop_id=2,
                machine_id=None,
                shift_id=None,
                business_date=date(2026, 5, 6),
                input_weight=10_000.0,
                output_weight=9_700.0,
                scrap_weight=300.0,
                entry_status='submitted',
                entry_type='mobile_coil',
            ),
            WorkOrderEntry(
                id=712,
                work_order_id=712,
                workshop_id=4,
                machine_id=None,
                shift_id=None,
                business_date=date(2026, 5, 6),
                input_weight=8_000.0,
                output_weight=7_500.0,
                scrap_weight=500.0,
                entry_status='submitted',
                entry_type='mobile_coil',
            ),
            MesCoilSnapshot(
                id=711,
                coil_id='MES-711',
                tracking_card_no='RA260506711',
                workshop_code=None,
                machine_code=None,
                shift_code='N',
                next_workshop='2050车间',
                next_process='冷轧',
                status='synced',
                business_date=date(2026, 5, 6),
            ),
            MesCoilSnapshot(
                id=712,
                coil_id='MES-712',
                tracking_card_no='RA260506712',
                workshop_code='JZ',
                machine_code=None,
                shift_code='N',
                next_process='纵剪',
                status='synced',
                business_date=date(2026, 5, 6),
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

    assert payload['mes_machine_binding'] == {
        'mes_row_count': 2,
        'mes_rows_with_machine': 1,
        'mes_rows_without_machine': 1,
        'direct_machine_code_count': 0,
        'route_inferred_machine_count': 1,
        'unresolved_machine_count': 1,
        'upstream_machine_code_missing_count': 2,
        'fill_entry_count': 2,
        'fill_entries_with_mes_match': 2,
        'fill_entries_bound_to_machine': 1,
        'fill_entries_pending_machine': 1,
        'pending_assignment_entry_count': 1,
        'pending_machine_assignment_count': 1,
    }


def test_mes_machine_binding_summary_uses_strict_runtime_match() -> None:
    summary = realtime_service._build_mes_machine_binding_summary(
        mes_rows=[
            {
                'id': 701,
                'tracking_card_no': 'RA260506701',
                'machine_id': 11,
                'machine_binding_source': 'route_inferred',
                'upstream_machine_code_missing': True,
            },
            {
                'id': 702,
                'tracking_card_no': 'RA260506702',
                'machine_id': 12,
                'machine_binding_source': 'route_inferred',
                'upstream_machine_code_missing': True,
            },
        ],
        entries=[
            {
                'tracking_card_no': 'RA260506701',
                'entry_type': 'mobile_coil',
                'machine_id': 11,
                'mes_match_count': 1,
            },
            {
                'tracking_card_no': 'RA260506702',
                'entry_type': 'mobile_coil',
                'machine_id': 12,
            },
        ],
        pending_assignment={},
    )

    assert summary['fill_entry_count'] == 2
    assert summary['fill_entries_with_mes_match'] == 1
    assert summary['fill_entries_bound_to_machine'] == 1
    assert summary['fill_entries_pending_machine'] == 0


def test_mes_machine_binding_summary_counts_only_target_business_date() -> None:
    summary = realtime_service._build_mes_machine_binding_summary(
        mes_rows=[
            {
                'id': 801,
                'tracking_card_no': 'RA260602801',
                'business_date': '2026-06-02',
                'source_business_date': '2026-06-02',
                'machine_id': 11,
                'machine_binding_source': 'route_inferred',
                'upstream_machine_code_missing': True,
            },
            {
                'id': 802,
                'tracking_card_no': 'RA260601802',
                'business_date': '2026-06-02',
                'source_business_date': '2026-06-01',
                'machine_id': None,
                'machine_binding_source': 'unresolved',
                'upstream_machine_code_missing': True,
            },
        ],
        entries=[
            {
                'tracking_card_no': 'RA260601802',
                'entry_type': 'mobile_coil',
                'machine_id': 12,
                'mes_match_count': 1,
            }
        ],
        pending_assignment={},
        business_date=date(2026, 6, 2),
    )

    assert summary['mes_row_count'] == 1
    assert summary['route_inferred_machine_count'] == 1
    assert summary['unresolved_machine_count'] == 0
    assert summary['upstream_machine_code_missing_count'] == 1
    assert summary['fill_entries_with_mes_match'] == 1


def test_build_live_aggregation_excludes_cross_date_mes_helper_rows_from_summary(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='A', name='长白班', shift_type='day', start_time=time(7, 30), end_time=time(15, 30), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050轧机', workshop_id=2, equipment_type='cold_mill', is_active=True),
            WorkOrder(id=801, tracking_card_no='RA260602801', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=801,
                work_order_id=801,
                workshop_id=2,
                machine_id=None,
                shift_id=None,
                business_date=date(2026, 6, 2),
                input_weight=10_000.0,
                output_weight=9_700.0,
                scrap_weight=300.0,
                entry_status='submitted',
                entry_type='mobile_coil',
            ),
            MesCoilSnapshot(
                id=801,
                coil_id='MES-801-old',
                tracking_card_no='RA260602801',
                workshop_code='LZ2050',
                machine_code='LZ2050-1',
                shift_code='A',
                status='synced',
                business_date=date(2026, 6, 1),
            ),
            MesCoilSnapshot(
                id=802,
                coil_id='MES-802-current',
                tracking_card_no='RA260602802',
                workshop_code='LZ2050',
                machine_code='LZ2050-1',
                shift_code='A',
                status='synced',
                business_date=date(2026, 6, 2),
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(realtime_service, '_build_attendance_summary', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, '_build_expected_count_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(realtime_service, 'build_yield_matrix_projection', lambda *_args, **_kwargs: {})

    payload = realtime_service.build_live_aggregation(
        db,
        business_date=date(2026, 6, 2),
        workshop_id=None,
        current_user=admin_user(),
    )

    assert payload['mes_machine_binding']['mes_row_count'] == 1
    assert payload['mes_machine_binding']['direct_machine_code_count'] == 1
    assert payload['mes_machine_binding']['fill_entries_with_mes_match'] == 1


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


def test_build_live_aggregation_pairs_fill_uploads_with_mes_material_code_alias(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050轧机', workshop_id=2, is_active=True),
            WorkOrder(id=707, tracking_card_no='S一2一054一1', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=707,
                work_order_id=707,
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
                id=707,
                coil_id='fallback:26RA03630:26-s-2-054-1',
                tracking_card_no='26RA03630',
                material_code='26-s-2-054-1',
                workshop_code='LZ2050',
                machine_code='LZ2050-1',
                shift_code='N',
                status='synced',
                business_date=None,
                source_payload={'MaterialCode': '26-s-2-054-1'},
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


def test_build_live_aggregation_resolves_virtual_role_qr_to_reporting_machine(tmp_path, monkeypatch) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=5, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=5, code='N', name='小夜', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=81, code='LZ2050-1-OP', name='冷轧2050车间 2050# 主操', workshop_id=5, equipment_type='virtual_role_qr', operational_status='running', is_active=True),
            Equipment(id=123, code='LZ2050-1', name='2050轧机', workshop_id=5, equipment_type='cold_mill', operational_status='running', assigned_shift_ids=[1, 2, 3], is_active=True),
            WorkOrder(id=810, tracking_card_no='RA260506810', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=810,
                work_order_id=810,
                workshop_id=5,
                machine_id=81,
                shift_id=5,
                business_date=date(2026, 5, 6),
                input_weight=31_642.0,
                output_weight=29_850.0,
                scrap_weight=1_792.0,
                entry_status='submitted',
                entry_type='mobile_coil',
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

    real_machine = next(item for item in payload['workshops'][0]['machines'] if item['machine_id'] == 123)
    assert real_machine['day_total']['output'] == 29.85
    assert real_machine['shifts'][0]['submitted_count'] == 1
    assert all(item['machine_id'] != 81 for item in payload['workshops'][0]['machines'])


def test_build_live_cell_detail_pairs_fill_upload_with_mes_machine_binding(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050轧机', workshop_id=2, is_active=True),
            WorkOrder(id=706, tracking_card_no='RA260506706', process_route_code='cold-roll', overall_status='created'),
            WorkOrderEntry(
                id=706,
                work_order_id=706,
                workshop_id=2,
                machine_id=None,
                shift_id=None,
                business_date=date(2026, 5, 6),
                input_weight=10_000.0,
                output_weight=9_700.0,
                scrap_weight=300.0,
                yield_rate=0.97,
                entry_status='submitted',
                entry_type='mobile_coil',
                created_by_user_id=85,
            ),
            MesCoilSnapshot(
                id=706,
                coil_id='MES-706',
                tracking_card_no='RA260506706',
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

    payload = realtime_service.build_live_cell_detail(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=2,
        machine_id=11,
        shift_id=3,
        current_user=admin_user(),
    )

    assert payload['items'] == [
        {
            'tracking_card_no': 'RA260506706',
            'entry_id': 706,
            'work_order_id': 706,
            'entry_status': 'submitted',
            'entry_type': 'mobile_coil',
            'input_weight': 10.0,
            'output_weight': 9.7,
            'scrap_weight': 0.3,
            'yield_rate': 97.0,
            'yield_rate_source': 'runtime_compat',
            'machine_id': 11,
            'shift_id': 3,
        }
    ]


def test_build_live_cell_detail_includes_bound_mobile_shift_upload(tmp_path) -> None:
    db = build_realtime_session(tmp_path)
    db.add_all(
        [
            Workshop(id=2, code='LZ2050', name='2050冷轧车间', sort_order=1, is_active=True),
            ShiftConfig(id=3, code='N', name='夜班', shift_type='night', start_time=time(20, 0), end_time=time(8, 0), is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050轧机', workshop_id=2, is_active=True),
            ShiftProductionData(
                id=801,
                business_date=date(2026, 5, 6),
                shift_config_id=3,
                workshop_id=2,
                equipment_id=11,
                input_weight=12_000.0,
                output_weight=11_400.0,
                scrap_weight=600.0,
                data_source='mobile_coil_agg',
                data_status='pending',
            ),
        ]
    )
    db.commit()

    payload = realtime_service.build_live_cell_detail(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=2,
        machine_id=11,
        shift_id=3,
        current_user=admin_user(),
    )

    assert payload['items'] == [
        {
            'tracking_card_no': 'SHIFT-801',
            'entry_id': 801,
            'work_order_id': None,
            'entry_status': 'submitted',
            'entry_type': 'mobile_coil_agg',
            'input_weight': 12.0,
            'output_weight': 11.4,
            'scrap_weight': 0.6,
            'yield_rate': 95.0,
            'yield_rate_source': 'local_shift_data',
            'machine_id': 11,
            'shift_id': 3,
        }
    ]


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
            'machine_candidates': [{'machine_id': 11, 'machine_name': '1#轧机'}],
            'created_at': payload['items'][0]['created_at'],
        }
    ]


def test_build_pending_assignment_detail_matches_mes_material_code_alias(tmp_path) -> None:
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
            MesCoilSnapshot(
                id=902,
                coil_id='fallback:26RA03630:26-s-2-054-1',
                tracking_card_no='26RA03630',
                material_code='26-s-2-054-1',
                workshop_code='LZ2050',
                machine_code='LZ2050-1',
                shift_code='N',
                status='synced',
                business_date=None,
            ),
        ]
    )
    seed_pending_assignment_entry(
        db,
        entry_id=103,
        tracking_card_no='S一2一054一1',
        workshop_id=2,
        shift_id=3,
        machine_id=None,
    )
    db.commit()

    payload = realtime_service.build_pending_assignment_detail(
        db,
        business_date=date(2026, 5, 6),
        workshop_id=None,
        current_user=User(id=7, username='admin', password_hash='x', name='Admin', role='admin'),
    )

    assert payload['total'] == 1
    assert payload['items'][0]['mes_match_count'] == 1
    assert payload['items'][0]['mes_machine_id'] == 11
    assert payload['items'][0]['mes_machine_name'] == '1#轧机'


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
    assert payload['factory_total']['output'] == 9.7
    assert payload['workshops'][0]['workshop_name'] == '冷轧2050车间'
    assert payload['workshops'][0]['workshop_total']['yield_rate'] == 97.0
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


def test_aggregate_live_payload_excludes_bound_draft_weight_from_output_totals() -> None:
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
            'id': 105,
            'tracking_card_no': 'RA240005',
            'work_order_id': 5,
            'workshop_id': 2,
            'machine_id': 11,
            'shift_id': 1,
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

    shift = payload['workshops'][0]['machines'][0]['shifts'][0]
    assert payload['overall_progress']['formal_entry_count'] == 0
    assert payload['overall_progress']['draft_entry_count'] == 1
    assert shift['submitted_count'] == 0
    assert shift['draft_count'] == 1
    assert shift['submission_status'] == 'in_progress'
    assert shift['total_input'] == 0.0
    assert shift['total_output'] == 0.0
    assert shift['total_scrap'] == 0.0
    assert payload['workshops'][0]['machines'][0]['day_total']['output'] == 0.0
    assert payload['workshops'][0]['workshop_total']['output'] == 0.0
    assert payload['factory_total']['output'] == 0.0


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


def test_mobile_shift_aggregate_rows_use_reporting_machine_for_virtual_role_qr() -> None:
    machines = [
        SimpleNamespace(
            id=81,
            workshop_id=5,
            code='LZ2050-1-OP',
            name='冷轧2050车间 2050# 主操',
            equipment_type='virtual_role_qr',
            is_active=True,
            operational_status='running',
            sort_order=1,
        ),
        SimpleNamespace(
            id=123,
            workshop_id=5,
            code='LZ2050-1',
            name='2050轧机',
            equipment_type='cold_mill',
            is_active=True,
            operational_status='running',
            sort_order=2,
        ),
    ]
    shifts = [SimpleNamespace(id=3, name='小夜', sort_order=3)]
    rows = [
        SimpleNamespace(
            id=801,
            workshop_id=5,
            equipment_id=81,
            shift_config_id=3,
            business_date=date(2026, 5, 6),
            input_weight=31_642.0,
            output_weight=29_850.0,
            scrap_weight=1_792.0,
            data_status='pending',
            data_source='mobile_coil_agg',
        )
    ]

    _local_machines, entries = realtime_service._build_local_shift_runtime_inputs(
        machines=machines,
        shifts=shifts,
        rows=rows,
    )

    assert entries[0]['machine_id'] == 123


def test_apply_yield_matrix_authority_keeps_factory_total_as_main_fact_reference() -> None:
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
        'workshop_yields': {'cold_roll_2050': 95.8},
    }

    updated = realtime_service._apply_yield_matrix_authority(payload, workshops, yield_matrix_lane)

    assert updated['factory_total']['yield_rate'] == 97.0
    assert updated['workshops'][0]['workshop_total']['yield_rate'] == 95.8
    assert updated['workshops'][0]['workshop_total']['yield_rate_source'] == 'yield_matrix_lane'
    assert updated['yield_matrix_lane']['quality_status'] == 'ready'


def test_inject_factory_packaging_output_uses_mes_as_live_main_metric(monkeypatch) -> None:
    business_date = date(2026, 6, 9)
    monkeypatch.setattr(
        realtime_service.mes_factory_production_fact,
        'build_factory_production_fact',
        lambda _db, *, target_date: {
            'factory_feeding_daily_input': 50.0,
            'factory_feeding_month_to_date_input': 60.0,
            'factory_finished_inbound_daily_output': 39.25,
            'factory_finished_inbound_month_to_date_output': 49.25,
            'daily_yield_rate': 78.5,
            'month_yield_rate': 82.08,
            'yield_rate_source': 'mes_feeding_to_finished_inbound',
            'packaging_fact': {
                'daily_row_count': 1,
                'month_row_count': 2,
                'mes_home_daily_output': 42.5,
                'mes_home_month_to_date_output': 52.5,
            },
        },
    )

    payload = realtime_service._inject_factory_packaging_output(
        {'factory_total': {'output': 99.0}},
        None,
        business_date=business_date,
        scoped_workshop_id=None,
    )

    assert payload['factory_total']['packaging_output'] == 42.5
    assert payload['factory_total']['daily_output'] == 42.5
    assert payload['factory_total']['factory_total_output'] == 42.5
    assert payload['factory_total']['factory_feeding_daily_input'] == 50.0
    assert payload['factory_total']['finished_inbound_output'] == 39.25
    assert payload['factory_total']['finished_inbound_monthly_output'] == 49.25
    assert payload['factory_total']['yield_rate'] == 78.5
    assert payload['factory_total']['yield_rate_source'] == 'mes_feeding_to_finished_inbound'
    assert payload['factory_total']['business_day_start'] == '07:30'
    assert payload['factory_total']['daily_output_source'] == 'mes_workshop_process_records'
    assert payload['factory_total']['packaging_monthly_output'] == 52.5
    assert payload['factory_total']['month_to_date_output'] == 52.5
