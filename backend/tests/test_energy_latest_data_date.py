from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base
from app.models.energy import EnergyImportRecord
from app.models.master import Workshop
from app.models.production import WorkOrder, WorkOrderEntry
from app.services.energy_service import latest_energy_data_date


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _imported(business_date: date, value: float) -> EnergyImportRecord:
    return EnergyImportRecord(
        business_date=business_date,
        workshop_code='JZ',
        energy_type='electricity',
        energy_value=value,
    )


def test_no_energy_data_has_no_date(db_session: Session) -> None:
    assert latest_energy_data_date(db_session) is None


def test_zero_values_do_not_count(db_session: Session) -> None:
    db_session.add_all([_imported(date(2026, 7, 21), 100), _imported(date(2026, 8, 1), 0)])
    db_session.commit()

    assert latest_energy_data_date(db_session) == date(2026, 7, 21)


def test_owner_entries_count_only_when_they_carry_energy(db_session: Session) -> None:
    db_session.add_all([
        _imported(date(2026, 7, 21), 100),
        Workshop(id=1, code='CPK', name='成品库', workshop_type='inventory', is_active=True),
        WorkOrder(id=1, tracking_card_no='OWNER-1', process_route_code='owner_daily'),
        WorkOrderEntry(
            work_order_id=1, workshop_id=1, business_date=date(2026, 9, 18),
            entry_type='owner_daily', entry_status='submitted',
            extra_payload={'total_gas_m3': 300},
        ),
        WorkOrderEntry(
            work_order_id=1, workshop_id=1, business_date=date(2026, 9, 20),
            entry_type='owner_daily', entry_status='submitted',
            extra_payload={'remaining_contract_weight': 4792},
        ),
    ])
    db_session.commit()

    assert latest_energy_data_date(db_session) == date(2026, 9, 18)
