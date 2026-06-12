from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.energy import IotEnergySnapshot
from app.models.master import Workshop
from app.services import energy_service


def _make_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def test_iot_energy_shadow_rows_are_returned_as_read_only_reference() -> None:
    db = _make_session()
    try:
        db.add(Workshop(id=1, code='LJ', name='拉矫车间'))
        db.add_all([
            IotEnergySnapshot(
                business_date=date(2026, 6, 11),
                workshop_id=1,
                meter_code='LJ-DL-01',
                electricity_kwh=1200.5,
                gas_m3=30.0,
                water_m3=4.5,
                reading_at=datetime(2026, 6, 11, 9, 10, tzinfo=timezone.utc),
                source_system='iot_meter',
                sync_run_id=1,
            ),
            IotEnergySnapshot(
                business_date=date(2026, 6, 11),
                workshop_id=1,
                meter_code='LJ-DL-02',
                electricity_kwh=99.5,
                gas_m3=None,
                water_m3=1.5,
                reading_at=datetime(2026, 6, 11, 9, 20, tzinfo=timezone.utc),
                source_system='iot_meter',
                sync_run_id=1,
            ),
        ])
        db.commit()

        rows = energy_service.get_energy_summary(db, business_date=date(2026, 6, 11))

        assert len(rows) == 1
        row = rows[0]
        assert row['source'] == 'iot_shadow'
        assert row['source_label'] == '物联网采集'
        assert row['workshop_id'] == 1
        assert row['workshop_code'] == 'LJ'
        assert row['shift_config_id'] is None
        assert row['shift_code'] is None
        assert row['electricity_value'] == 1300.0
        assert row['gas_value'] == 30.0
        assert row['water_value'] == 6.0
        assert row['total_energy'] == 1336.0
        assert row['output_weight'] == 0.0
        assert row['energy_per_ton'] is None
        assert row['source_updated_at'].isoformat().startswith('2026-06-11T09:20:00')
    finally:
        db.close()
