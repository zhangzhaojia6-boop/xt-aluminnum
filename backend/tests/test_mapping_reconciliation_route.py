from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.consumable import DailyConsumableLog
from app.models.energy import MachineEnergyRecord
from app.models.executive import CostDailyResult, MachineDailyCostSnapshot
from app.models.master import Equipment, Team, Workshop
from app.models.mes import MesStockRecord, MesWorkshopProcessRecord
from app.models.production import MobileShiftReport, ShiftProductionData, WorkOrder, WorkOrderEntry
from app.models.reconciliation import MappingReconciliationRun
from app.models.shift import ShiftConfig
from app.models.system import User

RECONCILIATION_TABLES = [
    Workshop.__table__,
    Team.__table__,
    User.__table__,
    ShiftConfig.__table__,
    Equipment.__table__,
    ShiftProductionData.__table__,
    WorkOrder.__table__,
    WorkOrderEntry.__table__,
    MobileShiftReport.__table__,
    MachineEnergyRecord.__table__,
    CostDailyResult.__table__,
    MachineDailyCostSnapshot.__table__,
    DailyConsumableLog.__table__,
    MesWorkshopProcessRecord.__table__,
    MesStockRecord.__table__,
    MappingReconciliationRun.__table__,
]


def _install_overrides(*, role: str = 'admin', db_override=None):
    fake_db = object() if db_override is None else db_override

    def fake_get_db():
        yield fake_db

    def fake_get_user() -> User:
        return User(id=1, username=role, password_hash='x', name='User', role=role, is_active=True)

    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    return previous_overrides


def _restore_overrides(previous_overrides) -> None:
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def test_mapping_reconciliation_sources_lists_reference_files(tmp_path, monkeypatch) -> None:
    reference_dir = tmp_path / 'output-skill'
    reference_dir.mkdir()
    (reference_dir / '2026-06-13-summary.txt').write_text('日报摘要', encoding='utf-8')
    monkeypatch.setenv('OUTPUT_SKILL_REFERENCE_ROOT', str(reference_dir))
    previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        response = client.get('/api/v1/mapping-reconciliation/sources')
    finally:
        _restore_overrides(previous_overrides)

    assert response.status_code == 200
    payload = response.json()
    assert payload['reference_source'] == str(reference_dir)
    assert payload['available'] is True
    assert payload['files'][0]['relative_path'] == '2026-06-13-summary.txt'
    assert 'mes_stock_records' in payload['system_sources']
    assert 'machine_energy_records' in payload['system_sources']


def test_mapping_reconciliation_run_compares_rows_without_writing_database() -> None:
    previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/mapping-reconciliation/run',
            json={
                'reference_rows': [
                    {
                        'business_date': '2026-06-13',
                        'workshop': '精整',
                        'shift': '长白班',
                        'output_tons': 12.5,
                    }
                ],
                'system_rows': [
                    {
                        'business_date': '2026-06-13',
                        'workshop': '精整车间',
                        'shift': '白班',
                        'output_kg': 12500,
                    }
                ],
                'fields': [
                    {
                        'metric': 'output',
                        'reference_field': 'output_tons',
                        'system_field': 'output_kg',
                        'reference_unit': 'ton',
                        'system_unit': 'kg',
                        'tolerance': 0.001,
                        'weight': 30,
                    }
                ],
                'dimension_aliases': {'workshop': {'精整车间': '精整'}, 'shift': {'白班': '长白班'}},
            },
        )
    finally:
        _restore_overrides(previous_overrides)

    assert response.status_code == 200
    payload = response.json()
    assert payload['run_mode'] == 'dry_run'
    assert payload['overall_match_rate'] == 100
    assert payload['differences'] == []


def test_mapping_reconciliation_run_returns_difference_summary() -> None:
    previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/mapping-reconciliation/run',
            json={
                'reference_rows': [
                    {
                        'business_date': '2026-06-13',
                        'workshop': '拉矫',
                        'shift': '小夜班',
                        'energy_kwh': 1800,
                    },
                    {
                        'business_date': '2026-06-13',
                        'workshop': '园区剪切',
                        'shift': '小夜班',
                        'energy_kwh': 900,
                    },
                ],
                'system_rows': [
                    {
                        'business_date': '2026-06-13',
                        'workshop': '拉矫车间',
                        'shift': '小夜',
                        'electricity_kwh': 1760,
                    }
                ],
                'fields': [
                    {
                        'metric': 'energy',
                        'reference_field': 'energy_kwh',
                        'system_field': 'electricity_kwh',
                        'reference_unit': 'kwh',
                        'system_unit': 'kwh',
                        'tolerance': 5,
                        'weight': 15,
                    }
                ],
                'dimension_aliases': {'workshop': {'拉矫车间': '拉矫'}, 'shift': {'小夜': '小夜班'}},
            },
        )
    finally:
        _restore_overrides(previous_overrides)

    assert response.status_code == 200
    payload = response.json()
    assert payload['difference_summary'] == {
        'total': 2,
        'by_reason_code': {'value_diff': 1, 'missing_system_row': 1},
        'by_metric': {'energy': 2},
        'reason_breakdown': [
            {'reason_code': 'value_diff', 'label': '数值不一致', 'count': 1},
            {'reason_code': 'missing_system_row', 'label': '系统缺少同维度数据', 'count': 1},
        ],
    }


def test_mapping_reconciliation_run_returns_match_summary_for_ui() -> None:
    previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/mapping-reconciliation/run',
            json={
                'reference_rows': [
                    {
                        'business_date': '2026-06-13',
                        'workshop': '精整',
                        'shift': '长白班',
                        'output_tons': 12.5,
                        'energy_kwh': 1800,
                    }
                ],
                'system_rows': [
                    {
                        'business_date': '2026-06-13',
                        'workshop': '精整车间',
                        'shift': '白班',
                        'output_kg': 12500,
                        'electricity_kwh': 1600,
                    }
                ],
                'fields': [
                    {
                        'metric': 'output',
                        'reference_field': 'output_tons',
                        'system_field': 'output_kg',
                        'reference_unit': 'ton',
                        'system_unit': 'kg',
                        'tolerance': 0.001,
                        'weight': 30,
                    },
                    {
                        'metric': 'energy',
                        'reference_field': 'energy_kwh',
                        'system_field': 'electricity_kwh',
                        'reference_unit': 'kwh',
                        'system_unit': 'kwh',
                        'tolerance': 5,
                        'weight': 15,
                    },
                ],
                'dimension_aliases': {'workshop': {'精整车间': '精整'}, 'shift': {'白班': '长白班'}},
            },
        )
    finally:
        _restore_overrides(previous_overrides)

    assert response.status_code == 200
    payload = response.json()
    assert payload['match_summary'] == {
        'total_fields': 2,
        'matched_fields': 1,
        'unmatched_fields': 1,
        'overall_match_rate': 66.67,
        'field_breakdown': [
            {'metric': 'output', 'match_rate': 100},
            {'metric': 'energy', 'match_rate': 0},
        ],
    }


def test_mapping_reconciliation_run_persists_and_exposes_run_detail() -> None:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=RECONCILIATION_TABLES)
    db = Session(engine)
    previous_overrides = _install_overrides(db_override=db)

    try:
        client = TestClient(app)
        run_response = client.post(
            '/api/v1/mapping-reconciliation/run',
            json={
                'reference_rows': [
                    {
                        'business_date': '2026-06-13',
                        'workshop': '拉矫',
                        'shift': '小夜班',
                        'energy_kwh': 1800,
                    }
                ],
                'system_rows': [
                    {
                        'business_date': '2026-06-13',
                        'workshop': '拉矫车间',
                        'shift': '小夜',
                        'electricity_kwh': 1760,
                    }
                ],
                'fields': [
                    {
                        'metric': 'energy',
                        'reference_field': 'energy_kwh',
                        'system_field': 'electricity_kwh',
                        'reference_unit': 'kwh',
                        'system_unit': 'kwh',
                        'tolerance': 5,
                        'weight': 15,
                    }
                ],
                'dimension_aliases': {'workshop': {'拉矫车间': '拉矫'}, 'shift': {'小夜': '小夜班'}},
            },
        )
        run_payload = run_response.json()
        detail_response = client.get(f"/api/v1/mapping-reconciliation/runs/{run_payload['run_id']}")
        differences_response = client.get(f"/api/v1/mapping-reconciliation/runs/{run_payload['run_id']}/differences")
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert run_response.status_code == 200
    assert run_payload['run_id'] > 0
    assert run_payload['run_mode'] == 'dry_run'

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload['id'] == run_payload['run_id']
    assert detail_payload['run_mode'] == 'dry_run'
    assert detail_payload['created_by_id'] == 1
    assert detail_payload['result']['overall_match_rate'] == 0
    assert detail_payload['result']['difference_summary']['total'] == 1

    assert differences_response.status_code == 200
    assert differences_response.json()['differences'][0]['reason_code'] == 'value_diff'


def test_mapping_reconciliation_run_can_parse_reference_file_and_read_system_rows(tmp_path, monkeypatch) -> None:
    reference_dir = tmp_path / 'output-skill'
    reference_dir.mkdir()
    (reference_dir / 'daily.txt').write_text(
        '2026年6月13日 生产日报\n'
        '精整 长白班 产量 12.5 吨\n',
        encoding='utf-8',
    )
    monkeypatch.setenv('OUTPUT_SKILL_REFERENCE_ROOT', str(reference_dir))

    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=RECONCILIATION_TABLES)
    db = Session(engine)
    db.add(
        MesWorkshopProcessRecord(
            source_id='mes-route-1',
            source_path='ProcessRecord',
            business_date=date(2026, 6, 13),
            workshop_name='精整车间',
            process_name='包装',
            device_name='PC-01',
            output_weight_kg=12500,
        )
    )
    db.commit()
    previous_overrides = _install_overrides(db_override=db)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/mapping-reconciliation/run',
            json={
                'reference_file': 'daily.txt',
                'business_date': '2026-06-13',
                'fields': [
                    {
                        'metric': 'output',
                        'reference_field': 'output_tons',
                        'system_field': 'output_tons',
                        'reference_unit': 'ton',
                        'system_unit': 'ton',
                        'tolerance': 0.001,
                        'weight': 30,
                    }
                ],
                'dimensions': ['business_date', 'workshop'],
                'dimension_aliases': {'workshop': {'精整车间': '精整'}},
            },
        )
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload['run_mode'] == 'dry_run'
    assert payload['reference_parse']['status'] == 'parsed'
    assert payload['system_rows_count'] == 1
    assert payload['overall_match_rate'] == 100
    assert payload['differences'] == []


def test_mapping_reconciliation_requires_admin_role() -> None:
    previous_overrides = _install_overrides(role='manager')

    try:
        client = TestClient(app)
        response = client.get('/api/v1/mapping-reconciliation/sources')
    finally:
        _restore_overrides(previous_overrides)

    assert response.status_code == 403
    assert response.json()['detail'] == 'Mapping reconciliation access denied'
