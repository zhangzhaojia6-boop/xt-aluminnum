from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.master import Equipment, MasterCodeAlias, MesTerminalBinding, Workshop
from app.models.mes import MesCoilSnapshot, MesWorkshopProcessRecord
from app.services import mes_supplement_readiness_service


BUSINESS_DATE = date(2026, 6, 10)


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-supplement-readiness.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Equipment.__table__,
            MasterCodeAlias.__table__,
            MesTerminalBinding.__table__,
            MesCoilSnapshot.__table__,
            MesWorkshopProcessRecord.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _manager_user():
    return SimpleNamespace(
        id=1,
        role='manager',
        is_admin=False,
        is_manager=True,
        is_reviewer=False,
        data_scope_type='all',
    )


def _mobile_user():
    return SimpleNamespace(
        id=2,
        role='machine_operator',
        is_admin=False,
        is_manager=False,
        is_reviewer=False,
        data_scope_type='self_workshop',
    )


def _seed_base(db) -> None:
    db.add(Workshop(id=1, code='LZ1650', name='1650冷轧', workshop_type='cold_rolling', sort_order=1, is_active=True))
    db.add(
        Equipment(
            id=11,
            code='LZ1650-1',
            name='1650#',
            workshop_id=1,
            equipment_type='cold_mill',
            operational_status='running',
            qr_code='XT-LZ1650-1',
            is_active=True,
        )
    )
    db.add(
        MasterCodeAlias(
            entity_type='equipment',
            canonical_code='LZ1650-1',
            alias_code='MES-LZ1650-1',
            alias_name='1650冷轧（WAN）',
            source_type='mes',
            is_active=True,
        )
    )
    db.add_all(
        [
            MesCoilSnapshot(
                coil_id='MES-COLD-1',
                tracking_card_no='26RA00001',
                batch_no='26RA00001',
                material_code='MAT-26RA00001',
                customer_alias='河南永晟',
                alloy_grade='5052',
                material_state='H24',
                spec_display='1.0×1200',
                current_workshop='2050车间',
                current_process='冷轧',
            ),
            MesCoilSnapshot(
                coil_id='MES-HOT-1',
                tracking_card_no='26RH00001',
                batch_no='26RH00001',
                material_code='HOT-BILLET-1',
                customer_alias='热轧客户',
                alloy_grade='1060',
                material_state='O',
                spec_display='6.5×1220',
                current_workshop='热轧车间',
                current_process='热轧',
            ),
            MesCoilSnapshot(
                coil_id='MES-CAST-1',
                tracking_card_no='26ZJ00001',
                batch_no='26ZJ00001',
                material_code='CAST-BILLET-1',
                customer_alias='铸轧客户',
                alloy_grade='8011',
                material_state='H14',
                spec_display='7.0×1200',
                current_workshop='铸轧车间',
                current_process='铸轧',
            ),
        ]
    )
    db.add_all(
        [
            MesWorkshopProcessRecord(
                id=101,
                source_id='PROC-COLD-101',
                source_path='sqlserver',
                batch_no='26RA00001',
                customer_alias='河南永晟',
                workshop_name='2050车间',
                process_name='冷轧',
                device_name='1650冷轧（WAN）',
                input_weight_kg=1000,
                output_weight_kg=960,
                business_date=BUSINESS_DATE,
                end_time=datetime(2026, 6, 10, 10, 0),
            ),
            MesWorkshopProcessRecord(
                id=102,
                source_id='PROC-HOT-102',
                source_path='sqlserver',
                batch_no='26RH00001',
                workshop_name='热轧车间',
                process_name='热轧',
                device_name='铸轧1#机',
                input_weight_kg=7000,
                output_weight_kg=6800,
                business_date=BUSINESS_DATE,
                end_time=datetime(2026, 6, 10, 11, 0),
            ),
            MesWorkshopProcessRecord(
                id=103,
                source_id='PROC-CAST-103',
                source_path='sqlserver',
                batch_no='26ZJ00001',
                workshop_name='铸轧车间',
                process_name='铸轧',
                device_name='PC',
                input_weight_kg=8000,
                output_weight_kg=None,
                business_date=BUSINESS_DATE,
                end_time=datetime(2026, 6, 10, 12, 0),
                source_payload={'DeviceName': 'PC', 'DeviceCode': 'PC-ZJ-01', 'WorkShopLine': '铸轧1#机'},
            ),
            MesWorkshopProcessRecord(
                id=104,
                source_id='PROC-LEGACY-104',
                source_path='sqlserver',
                batch_no='26RA00002',
                workshop_name='2050车间',
                process_name='冷轧',
                device_name='1650冷轧（WAN）',
                input_weight_kg=1000,
                output_weight_kg=900,
                business_date=BUSINESS_DATE,
                end_time=datetime(2026, 6, 10, 8, 30),
            ),
        ]
    )


def test_supplement_readiness_summarizes_mes_mapping_and_window_delta(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_base(db)
        db.commit()

        payload = mes_supplement_readiness_service.build_supplement_readiness(
            db,
            business_date=BUSINESS_DATE,
            limit=100,
        )

    assert payload['status'] == 'needs_mapping'
    assert payload['coverage']['sample_count'] == 3
    assert payload['coverage']['output_weight_rate'] == 0.6667
    assert payload['coverage']['machine_match_rate'] == 1.0
    assert payload['coverage']['machine_match_scope_count'] == 2
    assert payload['coverage']['generic_terminal_count'] == 1
    assert payload['coverage']['snapshot_match_rate'] == 1.0
    assert payload['coverage']['cold_roll_sequence_rate'] == 1.0
    assert payload['machine_binding']['unmatched_count'] == 0
    assert payload['material_categories']['cold_roll_pass'] == 1
    assert payload['material_categories']['hot_roll_process'] == 1
    assert payload['material_categories']['cast_roll_process'] == 1
    assert payload['window_comparison']['supplement_window_count'] == 3
    assert payload['window_comparison']['stored_business_date_count'] == 4
    assert payload['window_comparison']['delta_count'] == -1
    assert payload['generic_terminals'][0]['source_id'] == 'PROC-CAST-103'
    assert payload['generic_terminals'][0]['terminal_hints']['DeviceCode'] == 'PC-ZJ-01'
    assert payload['generic_terminals'][0]['terminal_hints']['WorkShopLine'] == '铸轧1#机'
    assert payload['unmatched_devices'] == []
    assert 'output_weight_coverage_below_80_percent' in payload['warnings']
    assert 'machine_match_coverage_below_70_percent' not in payload['warnings']


def test_packaging_pc_terminal_does_not_block_machine_readiness(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(Workshop(id=1, code='JZ', name='精整', workshop_type='finishing', sort_order=1, is_active=True))
        db.add_all(
            [
                MesWorkshopProcessRecord(
                    id=201,
                    source_id='PACK-201',
                    source_path='sqlserver',
                    batch_no='26PACK001',
                    workshop_name='精整',
                    process_name='包装',
                    device_name='PC',
                    output_weight_kg=3200,
                    business_date=BUSINESS_DATE,
                    end_time=datetime(2026, 6, 10, 10, 0),
                ),
                MesWorkshopProcessRecord(
                    id=202,
                    source_id='PACK-202',
                    source_path='sqlserver',
                    batch_no='26PACK002',
                    workshop_name='园区精整',
                    process_name='包装',
                    device_name='PC',
                    output_weight_kg=2800,
                    business_date=BUSINESS_DATE,
                    end_time=datetime(2026, 6, 10, 11, 0),
                ),
            ]
        )
        db.commit()

        payload = mes_supplement_readiness_service.build_supplement_readiness(
            db,
            business_date=BUSINESS_DATE,
            limit=100,
        )

    assert payload['status'] == 'ready'
    assert payload['coverage']['machine_match_rate'] == 1.0
    assert payload['coverage']['machine_match_scope_count'] == 0
    assert payload['coverage']['generic_terminal_count'] == 2
    assert len(payload['generic_terminals']) == 2
    assert payload['generic_terminals'][0]['binding_source'] == 'generic_mes_terminal'
    assert payload['coverage']['cold_roll_sequence_rate'] == 1.0
    assert payload['machine_binding']['unmatched_count'] == 0
    assert payload['unmatched_devices'] == []
    assert 'machine_match_coverage_below_70_percent' not in payload['warnings']
    assert 'cold_roll_sequence_coverage_below_80_percent' not in payload['warnings']


def test_pc_terminal_binding_promotes_generic_terminal_into_machine_scope(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(Workshop(id=1, code='JZ', name='精整', workshop_type='finishing', sort_order=1, is_active=True))
        db.add(
            Equipment(
                id=21,
                code='JZ-PACK-1',
                name='包装入库线',
                workshop_id=1,
                equipment_type='slitter',
                operational_status='running',
                qr_code='XT-JZ-PACK-1',
                is_active=True,
            )
        )
        db.add(
            MesTerminalBinding(
                terminal_code='PC-JZ-01',
                terminal_name='精整包装一体机',
                mes_device_name='PC',
                workshop_name='精整',
                process_name='包装',
                equipment_id=21,
                is_active=True,
            )
        )
        db.add(
            MesWorkshopProcessRecord(
                id=301,
                source_id='PACK-301',
                source_path='sqlserver',
                batch_no='26PACK301',
                workshop_name='精整',
                process_name='包装',
                device_name='PC',
                output_weight_kg=3200,
                business_date=BUSINESS_DATE,
                end_time=datetime(2026, 6, 10, 10, 0),
                source_payload={'DeviceCode': 'PC-JZ-01', 'WorkShopLine': '包装入库线'},
            )
        )
        db.commit()

        payload = mes_supplement_readiness_service.build_supplement_readiness(
            db,
            business_date=BUSINESS_DATE,
            limit=100,
        )

    assert payload['status'] == 'ready'
    assert payload['coverage']['machine_match_scope_count'] == 1
    assert payload['coverage']['generic_terminal_count'] == 0
    assert payload['machine_binding']['matched_count'] == 1
    assert payload['machine_binding']['source_counts']['mes_terminal_binding'] == 1
    assert payload['generic_terminals'] == []


def test_mes_supplement_readiness_route_is_management_only(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_base(db)
        db.commit()

    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = _manager_user
    try:
        response = TestClient(app).get('/api/v1/mes/supplement-readiness', params={'business_date': '2026-06-10'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()['business_date'] == '2026-06-10'
    assert response.json()['coverage']['sample_count'] == 3

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = _mobile_user
    try:
        rejected = TestClient(app).get('/api/v1/mes/supplement-readiness', params={'business_date': '2026-06-10'})
    finally:
        app.dependency_overrides.clear()

    assert rejected.status_code == 403
