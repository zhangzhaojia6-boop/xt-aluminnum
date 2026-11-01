from datetime import date, datetime, time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.consumable import DailyConsumableLog
from app.models.energy import EnergyImportRecord, MachineEnergyRecord
from app.models.imports import ImportBatch
from app.models.master import Equipment, Workshop
from app.models.mes import MesStockRecord, MesWorkshopProcessRecord
from app.models.production import MobileShiftReport, ShiftProductionData, WorkOrder, WorkOrderEntry
from app.schemas.energy import EnergySummaryOut
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
            MesWorkshopProcessRecord.__table__,
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
                MesWorkshopProcessRecord(
                    source_id='pkg-jz-today',
                    source_path='sqlserver',
                    workshop_name='精整',
                    process_name='包装',
                    output_weight_tons=100,
                    business_date=BUSINESS_DATE,
                    end_time=datetime(2026, 6, 12, 12, 0),
                ),
                # 成品库调拨是入库口径，不是包装产量（CONTEXT.md），不能当吨能耗分母
                MesStockRecord(
                    source_id='stock-in-today',
                    source_path='sqlserver',
                    net_weight_tons=300,
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
    # 这一行只给分母，能耗未知就留空，不写 0
    assert basis_row['electricity_value'] is None
    assert basis_row['gas_value'] is None
    assert basis_row['water_value'] is None
    assert basis_row['total_energy'] is None
    assert basis_row['energy_per_ton'] == 10
    assert EnergySummaryOut(**basis_row).source_label == '全厂包装'


def test_imported_energy_summary_exposes_only_recorded_energy_types(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        batch = ImportBatch(
            batch_no='IMP-ENERGY-TYPE-PRESENCE',
            import_type='energy',
            source_type='daily_energy_report_locked',
            file_name='electricity-only.xlsx',
            total_rows=1,
            success_rows=1,
            failed_rows=0,
            status='completed',
            quality_status='ready',
            parsed_successfully=True,
        )
        db.add(batch)
        db.flush()
        db.add(
            EnergyImportRecord(
                import_batch_id=batch.id,
                business_date=BUSINESS_DATE,
                workshop_code='JZ',
                shift_code=None,
                energy_type='electricity',
                energy_value=173500,
                unit='kWh',
            )
        )
        db.commit()

    with session_factory() as db:
        summary = energy_service.summarize_energy_for_date(db, business_date=BUSINESS_DATE)

    assert summary['electricity_value'] == 173500
    assert summary['gas_value'] == 0
    assert summary['available_energy_types'] == ['electricity']


def test_energy_per_ton_is_missing_without_energy_data(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesWorkshopProcessRecord(
                source_id='pkg-jz-no-energy',
                source_path='sqlserver',
                workshop_name='精整',
                process_name='包装',
                output_weight_tons=511.35,
                business_date=BUSINESS_DATE,
                end_time=datetime(2026, 6, 12, 12, 0),
            )
        )
        db.commit()

    with session_factory() as db:
        summary = energy_service.summarize_energy_for_date(db, business_date=BUSINESS_DATE)

    # 没有能耗数据时吨能耗是缺失，不是 0
    assert summary['total_output_weight'] == 511.35
    assert summary['energy_per_ton'] is None
