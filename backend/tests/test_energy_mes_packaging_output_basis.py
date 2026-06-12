from datetime import date, time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.consumable import DailyConsumableLog
from app.models.energy import EnergyImportRecord, MachineEnergyRecord
from app.models.imports import ImportBatch
from app.models.master import Equipment, Workshop
from app.models.mes import MesStockRecord
from app.models.production import MobileShiftReport, ShiftProductionData, WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import energy_service


BUSINESS_DATE = date(2026, 6, 12)


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'energy-mes-packaging.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Workshop.__table__,
            Equipment.__table__,
            ShiftConfig.__table__,
            MobileShiftReport.__table__,
            ShiftProductionData.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            DailyConsumableLog.__table__,
            ImportBatch.__table__,
            EnergyImportRecord.__table__,
            MachineEnergyRecord.__table__,
            MesStockRecord.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def test_energy_summary_uses_mes_packaging_output_when_shift_output_is_empty(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                Workshop(id=1, code='JZ', name='精整', is_active=True),
                Equipment(id=1, code='JZ-1', name='精整1#线', workshop_id=1, is_active=True),
                ShiftConfig(
                    id=1,
                    code='A',
                    name='长白班',
                    shift_type='day',
                    start_time=time(7, 30),
                    end_time=time(15, 30),
                    is_active=True,
                ),
                User(id=1, username='electrician', password_hash='x', name='电工', role='energy_stat', is_active=True),
                MobileShiftReport(
                    id=1,
                    workshop_id=1,
                    shift_config_id=1,
                    owner_user_id=1,
                    submitted_by_user_id=1,
                    business_date=BUSINESS_DATE,
                    report_status='submitted',
                ),
                MachineEnergyRecord(
                    shift_report_id=1,
                    machine_id=1,
                    machine_name='精整1#线',
                    energy_kwh=1000,
                    gas_m3=0,
                ),
                MesStockRecord(
                    source_id='stock-in-today',
                    source_path='sqlserver',
                    net_weight_tons=100,
                    status_name='1',
                    business_date=BUSINESS_DATE,
                    source_payload={
                        'FromDepartment': '精整',
                        'ToDepartment': '成品库',
                        'Status': 1,
                    },
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        summary = energy_service.summarize_energy_for_date(db, business_date=BUSINESS_DATE)

    assert summary['total_energy'] == 1000
    assert summary['total_output_weight'] == 100
    assert summary['output_basis'] == 'mes_packaging_output'
    assert summary['energy_per_ton'] == 10
    basis_row = next(row for row in summary['rows'] if row['source'] == 'mes_packaging_output_basis')
    assert basis_row['output_weight'] == 100
    assert basis_row['total_energy'] is None
    assert basis_row['energy_per_ton'] == 10
