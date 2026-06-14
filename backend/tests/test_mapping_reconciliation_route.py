from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


def _install_overrides(*, role: str = 'admin'):
    fake_db = object()

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


def test_mapping_reconciliation_requires_admin_role() -> None:
    previous_overrides = _install_overrides(role='manager')

    try:
        client = TestClient(app)
        response = client.get('/api/v1/mapping-reconciliation/sources')
    finally:
        _restore_overrides(previous_overrides)

    assert response.status_code == 403
    assert response.json()['detail'] == 'Mapping reconciliation access denied'
