from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.consumable import DailyConsumableLog
from app.models.master import Workshop
from app.models.system import User
from app.services import consumable_service


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'consumable-service.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__, User.__table__, DailyConsumableLog.__table__])
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)()


def _seed(db):
    db.add_all([
        Workshop(id=1, code='ZD', name='铸锭车间', workshop_type='casting', sort_order=1, is_active=True),
        Workshop(id=2, code='ZR3', name='铸三车间', workshop_type='casting', sort_order=2, is_active=True),
        User(id=1, username='owner', password_hash='x', name='内勤', role='consumable_stat', is_active=True),
    ])
    db.commit()


def _field_names(item):
    return [field['name'] for field in item['fields']]


def test_consumable_service_limits_ingot_daily_fields_to_ingot_workshop(tmp_path) -> None:
    db = _session(tmp_path)
    try:
        _seed(db)
        items = {item['workshop_code']: item for item in consumable_service.list_workshops_with_consumables(db)}

        assert 'ingot_block_count' in _field_names(items['ZD'])
        assert 'ingot_input_tons' in _field_names(items['ZD'])
        assert 'ingot_output_tons' in _field_names(items['ZD'])
        assert 'ingot_exception_note' in _field_names(items['ZD'])
        assert 'ingot_block_count' not in _field_names(items['ZR3'])
    finally:
        db.close()


def test_consumable_service_saves_ingot_daily_summary_for_ingot_workshop(tmp_path) -> None:
    db = _session(tmp_path)
    try:
        _seed(db)
        result = consumable_service.upsert_daily_log(
            db,
            workshop_id=1,
            business_date=date(2026, 6, 10),
            payload={
                'ingot_block_count': 12,
                'ingot_input_tons': 33.5,
                'ingot_output_tons': 32.8,
                'ingot_exception_note': '炉次复核',
            },
            note=None,
            current_user=db.get(User, 1),
        )

        assert result['payload'] == {
            'ingot_block_count': 12,
            'ingot_input_tons': 33.5,
            'ingot_output_tons': 32.8,
            'ingot_exception_note': '炉次复核',
        }
    finally:
        db.close()
