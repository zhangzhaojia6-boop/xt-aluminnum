from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.auth import verify_password
from app.database import Base
from app.models.master import Equipment, Workshop
from app.models.system import AuditLog, User
from app.services.equipment_service import create_machine_with_account, reset_machine_pin, toggle_machine_status


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'equipment-identity.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__, User.__table__, Equipment.__table__, AuditLog.__table__])
    return sessionmaker(bind=engine, future=True)()


def test_create_machine_with_account_creates_bound_user_pin_and_qr(tmp_path) -> None:
    db = build_session(tmp_path)
    try:
        workshop = Workshop(code='ZR2', name='铸二车间', sort_order=2, is_active=True)
        db.add(workshop)
        db.commit()
        db.refresh(workshop)

        result = create_machine_with_account(
            db,
            workshop_id=workshop.id,
            code='3',
            name='3#机',
            machine_type='cast_roller',
            custom_fields=[{'name': 'al_liquid_kg', 'label': '铝液', 'type': 'number', 'unit': '公斤'}],
            operational_status='running',
        )

        equipment = db.execute(select(Equipment).where(Equipment.id == result['equipment_id'])).scalar_one()
        user = db.execute(select(User).where(User.id == equipment.bound_user_id)).scalar_one()

        assert equipment.code == 'ZR2-3'
        assert equipment.name == '3#机'
        assert equipment.workshop_id == workshop.id
        assert equipment.bound_user_id == user.id
        assert equipment.shift_mode == 'three'
        assert equipment.operational_status == 'running'
        assert equipment.qr_code == 'XT-ZR2-3'
        assert equipment.custom_fields == [{'name': 'al_liquid_kg', 'label': '铝液', 'type': 'number', 'unit': '公斤'}]

        assert user.username == 'ZR2-3'
        assert user.name == '铸二车间 3#机'
        assert user.role == 'shift_leader'
        assert user.workshop_id == workshop.id
        assert user.team_id is None
        assert user.is_mobile_user is True
        assert user.is_active is True
        assert user.pin_code == result['pin']
        assert len(result['pin']) == 6
        assert result['pin'].isdigit()
        assert verify_password(result['pin'], user.password_hash) is True

        assert result['username'] == 'ZR2-3'
        assert result['qr_code'] == 'XT-ZR2-3'
        assert result['workshop_name'] == '铸二车间'
        assert result['machine_name'] == '3#机'
    finally:
        db.close()


def test_reset_machine_pin_updates_user_hash_and_plain_pin(tmp_path) -> None:
    db = build_session(tmp_path)
    try:
        workshop = Workshop(code='ZR2', name='铸二车间', sort_order=2, is_active=True)
        db.add(workshop)
        db.commit()
        db.refresh(workshop)

        created = create_machine_with_account(
            db,
            workshop_id=workshop.id,
            code='5',
            name='5#机',
            machine_type='cast_roller',
        )
        old_pin = created['pin']

        result = reset_machine_pin(db, equipment_id=created['equipment_id'])

        equipment = db.execute(select(Equipment).where(Equipment.id == created['equipment_id'])).scalar_one()
        user = db.execute(select(User).where(User.id == equipment.bound_user_id)).scalar_one()

        assert result['username'] == 'ZR2-5'
        assert result['new_pin'] != old_pin
        assert result['new_pin'] == user.pin_code
        assert verify_password(old_pin, user.password_hash) is False
        assert verify_password(result['new_pin'], user.password_hash) is True
    finally:
        db.close()


def test_toggle_machine_status_syncs_bound_user_activation(tmp_path) -> None:
    db = build_session(tmp_path)
    try:
        workshop = Workshop(code='RZ', name='热轧车间', sort_order=4, is_active=True)
        db.add(workshop)
        db.commit()
        db.refresh(workshop)

        created = create_machine_with_account(
            db,
            workshop_id=workshop.id,
            code='ZJ',
            name='轧机',
            machine_type='hot_mill',
            operational_status='running',
        )

        stopped = toggle_machine_status(db, equipment_id=created['equipment_id'], operational_status='stopped')
        maintenance = toggle_machine_status(db, equipment_id=created['equipment_id'], operational_status='maintenance')
        running = toggle_machine_status(db, equipment_id=created['equipment_id'], operational_status='running')

        equipment = db.execute(select(Equipment).where(Equipment.id == created['equipment_id'])).scalar_one()
        user = db.execute(select(User).where(User.id == equipment.bound_user_id)).scalar_one()

        assert stopped['operational_status'] == 'stopped'
        assert maintenance['operational_status'] == 'maintenance'
        assert running['operational_status'] == 'running'
        assert equipment.operational_status == 'running'
        assert user.is_active is True
    finally:
        db.close()
