from datetime import date, datetime, time
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.energy import EnergyImportRecord
from app.models.master import Workshop
from app.models.mes import MesImportRecord
from app.models.production import ShiftProductionData
from app.models.reconciliation import DataReconciliationItem
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import reconciliation_service


class DummyDB:
    pass


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'reconciliation-granularity.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            ShiftConfig.__table__,
            ShiftProductionData.__table__,
            MesImportRecord.__table__,
            EnergyImportRecord.__table__,
            DataReconciliationItem.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True)()


def _seed_mobile_coil_output(db, *, output_weight: float = 250_000.0) -> None:
    workshop = Workshop(id=11, code='W1', name='一车间', workshop_type='production', sort_order=1, is_active=True)
    shift = ShiftConfig(
        id=21,
        code='A',
        name='白班',
        shift_type='day',
        start_time=time(8, 0),
        end_time=time(16, 0),
        is_cross_day=False,
        sort_order=1,
        is_active=True,
    )
    production = ShiftProductionData(
        id=31,
        business_date=date(2026, 5, 6),
        workshop_id=workshop.id,
        shift_config_id=shift.id,
        input_weight=260_000.0,
        output_weight=output_weight,
        data_source='mobile_coil_agg',
        data_status='pending',
    )
    db.add_all([workshop, shift, production])
    db.commit()


def test_reconciliation_dimension_key(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=4, username='stat', password_hash='x', name='Stat', role='stat', is_active=True)

    def fake_generate(db, *, business_date, reconciliation_type, operator):
        assert business_date == date(2026, 3, 25)
        assert reconciliation_type == 'energy_vs_production'
        assert operator.id == 4
        return [
            SimpleNamespace(
                id=31,
                business_date=business_date,
                reconciliation_type='energy_vs_production',
                source_a='energy',
                source_b='shift_production_data',
                dimension_key='workshop:W1|shift:A',
                field_name='energy_total',
                source_a_value='120',
                source_b_value='100',
                diff_value=20.0,
                status='open',
                resolved_by=None,
                resolved_at=None,
                resolve_note=None,
                created_at=datetime(2026, 3, 25, 10, 0, 0),
                updated_at=datetime(2026, 3, 25, 10, 0, 0),
            )
        ]

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.reconciliation.reconciliation_service.generate_reconciliation', fake_generate)

    client = TestClient(app)
    response = client.post(
        '/api/v1/reconciliation/generate',
        json={'business_date': '2026-03-25', 'reconciliation_type': 'energy_vs_production'},
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]['dimension_key'].startswith('workshop:')

    app.dependency_overrides.clear()


def test_reconciliation_converts_mobile_coil_aggregate_for_production_vs_mes(tmp_path, monkeypatch) -> None:
    db = build_session(tmp_path)
    try:
        _seed_mobile_coil_output(db)
        db.add(
            MesImportRecord(
                id=41,
                business_date=date(2026, 5, 6),
                workshop_code='W1',
                shift_code='A',
                metric_code='output_weight',
                metric_name='产量',
                metric_value=250.0,
                unit='吨',
            )
        )
        db.commit()
        monkeypatch.setattr(reconciliation_service, 'record_audit', lambda *_args, **_kwargs: None)

        items = reconciliation_service.generate_reconciliation(
            db,
            business_date=date(2026, 5, 6),
            reconciliation_type='production_vs_mes',
            operator=SimpleNamespace(id=4),
        )

        assert items == []
    finally:
        db.close()


def test_reconciliation_converts_mobile_coil_aggregate_value_in_energy_gap(tmp_path, monkeypatch) -> None:
    db = build_session(tmp_path)
    try:
        _seed_mobile_coil_output(db)
        db.add(
            EnergyImportRecord(
                id=51,
                business_date=date(2026, 5, 6),
                workshop_code='W1',
                shift_code='A',
                energy_type='electricity',
                energy_value=0.0,
                unit='kWh',
            )
        )
        db.commit()
        monkeypatch.setattr(reconciliation_service, 'record_audit', lambda *_args, **_kwargs: None)

        items = reconciliation_service.generate_reconciliation(
            db,
            business_date=date(2026, 5, 6),
            reconciliation_type='energy_vs_production',
            operator=SimpleNamespace(id=4),
        )

        assert len(items) == 1
        assert items[0].source_b_value == '250.0'
    finally:
        db.close()
