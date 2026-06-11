from __future__ import annotations

from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_db
from app.core.permissions import get_current_mobile_user
from app.database import Base
from app.main import app
from app.models.master import Equipment, MasterCodeAlias, Workshop
from app.models.mes import MesCoilSnapshot, MesWorkshopProcessRecord
from app.models.production import WorkOrder, WorkOrderEntry
from app.models.system import User


BUSINESS_DATE = date(2026, 6, 10)


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mobile-mes-pending-supplements.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            User.__table__,
            Equipment.__table__,
            MasterCodeAlias.__table__,
            MesCoilSnapshot.__table__,
            MesWorkshopProcessRecord.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _mobile_user(user_id: int = 1) -> User:
    return User(
        id=user_id,
        username='operator',
        password_hash='x',
        name='主操',
        role='machine_operator',
        workshop_id=1,
        data_scope_type='self_workshop',
        is_mobile_user=True,
        is_reviewer=False,
        is_manager=False,
        is_active=True,
    )


def _client_with_db(session_factory, user_id: int = 1):
    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_mobile_user] = lambda: _mobile_user(user_id)
    return TestClient(app)


def _seed_machine(db, *, bound_user_id: int | None = 1) -> None:
    db.add(Workshop(id=1, code='LZ1650', name='1650冷轧', workshop_type='cold_rolling', sort_order=1, is_active=True))
    db.add(_mobile_user(1))
    db.add(
        Equipment(
            id=11,
            code='LZ1650-1',
            name='1650#',
            workshop_id=1,
            equipment_type='cold_mill',
            operational_status='running',
            qr_code='XT-LZ1650-1',
            bound_user_id=bound_user_id,
            is_active=True,
        )
    )


def _seed_mes_pending_item(db) -> None:
    db.add(
        MesCoilSnapshot(
            coil_id='MES-TRACK-1',
            tracking_card_no='26RA00001',
            qr_code='QR-TRACK-1',
            batch_no='26RA00001',
            material_code='MAT-26RA00001',
            customer_alias='河南永晟',
            alloy_grade='5052',
            material_state='H24',
            spec_display='1.0×1200',
            current_workshop='2050车间',
            current_process='冷轧',
            next_workshop='在线退火',
            next_process='退火',
            process_route_text='2050车间(冷轧) - 在线退火',
        )
    )
    db.add(
        MesWorkshopProcessRecord(
            id=101,
            source_id='PROC-101',
            source_path='sqlserver',
            batch_no='26RA00001-2',
            customer_alias='河南永晟',
            workshop_name='2050车间',
            process_name='冷轧',
            device_name='1650冷轧（WAN）',
            input_weight_kg=1000,
            output_weight_kg=960,
            business_date=BUSINESS_DATE,
            end_time=datetime(2026, 6, 10, 10, 0),
            source_payload={'BeginSpecification': '1.0×1200', 'EndSpecification': '0.96×1200'},
        )
    )


def test_mes_pending_supplements_returns_only_current_machine_items(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_machine(db)
        _seed_mes_pending_item(db)
        db.commit()

    client = _client_with_db(session_factory)
    try:
        response = client.get('/api/v1/mobile/mes-pending-supplements', params={'business_date': '2026-06-10'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['business_day_start'] == '09:30'
    assert payload['is_machine_bound'] is True
    assert payload['summary']['matched_machine_count'] == 1
    assert payload['summary']['pending_count'] == 1
    assert payload['summary']['completed_count'] == 0
    assert payload['items'][0]['tracking_card_no'] == '26RA00001'
    assert payload['items'][0]['resolved_machine_id'] == 11
    assert payload['items'][0]['input_weight_kg'] == 1000.0
    assert payload['items'][0]['output_weight_kg'] == 960.0
    assert payload['items'][0]['material_code'] == 'MAT-26RA00001'
    assert payload['items'][0]['material_category'] == 'cold_roll_pass'
    assert payload['items'][0]['material_reference']['current_workshop'] == '2050车间'
    assert payload['items'][0]['process_sequence']['pass_label'] == '单道次'
    assert payload['items'][0]['mes_reference']['process_record_id'] == 101
    assert payload['items'][0]['mes_reference']['material_reference']['material_code'] == 'MAT-26RA00001'


def test_mes_pending_supplements_excludes_completed_local_entry(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_machine(db)
        _seed_mes_pending_item(db)
        work_order = WorkOrder(
            id=201,
            tracking_card_no='26RA00001',
            process_route_code='mobile',
            overall_status='created',
        )
        db.add(work_order)
        db.flush()
        db.add(
            WorkOrderEntry(
                id=201,
                work_order_id=work_order.id,
                workshop_id=1,
                machine_id=11,
                business_date=BUSINESS_DATE,
                input_weight=1000,
                output_weight=960,
                entry_status='submitted',
                entry_type='mobile_coil',
                extra_payload={'mes_reference': {'process_record_id': 101, 'source_id': 'PROC-101'}},
            )
        )
        db.commit()

    client = _client_with_db(session_factory)
    try:
        response = client.get('/api/v1/mobile/mes-pending-supplements', params={'business_date': '2026-06-10'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['summary']['matched_machine_count'] == 1
    assert payload['summary']['pending_count'] == 0
    assert payload['summary']['completed_count'] == 1
    assert payload['items'] == []


def test_mes_pending_supplements_handles_unbound_mobile_user(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_machine(db, bound_user_id=None)
        _seed_mes_pending_item(db)
        db.commit()

    client = _client_with_db(session_factory)
    try:
        response = client.get('/api/v1/mobile/mes-pending-supplements', params={'business_date': '2026-06-10'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['is_machine_bound'] is False
    assert payload['summary']['pending_count'] == 0
    assert payload['items'] == []


def test_mes_pending_supplements_marks_cold_roll_pass_sequence(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_machine(db)
        _seed_mes_pending_item(db)
        db.add(
            MesWorkshopProcessRecord(
                id=100,
                source_id='PROC-100',
                source_path='sqlserver',
                batch_no='26RA00001-1',
                customer_alias='河南永晟',
                workshop_name='2050车间',
                process_name='冷轧',
                device_name='1650冷轧（WAN）',
                input_weight_kg=1100,
                output_weight_kg=1000,
                business_date=BUSINESS_DATE,
                end_time=datetime(2026, 6, 10, 9, 30),
                source_payload={'BeginSpecification': '1.2×1200', 'EndSpecification': '1.0×1200'},
            )
        )
        db.commit()

    client = _client_with_db(session_factory)
    try:
        response = client.get('/api/v1/mobile/mes-pending-supplements', params={'business_date': '2026-06-10'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    sequence_by_id = {item['mes_process_record_id']: item['process_sequence'] for item in payload['items']}
    assert sequence_by_id[100]['pass_label'] == '第1道'
    assert sequence_by_id[101]['pass_label'] == '第2道'
    assert sequence_by_id[101]['pass_total'] == 2
    assert payload['items'][0]['material_category'] == 'cold_roll_pass'
