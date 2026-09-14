from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.energy import EnergyImportRecord
from app.services import report_service


def test_timeseries_keeps_requested_dates_without_inventing_missing_readings():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        points = report_service.build_timeseries(
            db, start_date=date(2026, 9, 12), end_date=date(2026, 9, 13)
        )
    assert points == [
        {'date': '2026-09-12', 'output': None, 'energy': None},
        {'date': '2026-09-13', 'output': None, 'energy': None},
    ]


def test_timeseries_distinguishes_missing_electricity_from_confirmed_zero():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            EnergyImportRecord(business_date=date(2026, 9, 12), energy_type='gas', energy_value=100, unit='m3'),
            EnergyImportRecord(business_date=date(2026, 9, 13), energy_type='electricity', energy_value=0, unit='kWh'),
        ])
        db.commit()
        points = report_service.build_timeseries(
            db, start_date=date(2026, 9, 12), end_date=date(2026, 9, 13)
        )
    assert [point['energy'] for point in points] == [None, 0.0]
