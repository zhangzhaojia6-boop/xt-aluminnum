"""A4 红阶段：聚合 API 契约测试。

验证三个新 endpoint 的 response schema 和 calculator 桥接：
- GET /api/v1/dashboard/cumulative
- GET /api/v1/dashboard/comparison
- GET /api/v1/dashboard/timeseries
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_db, get_current_user
from app.main import app
from app.models.base import Base


def _fake_manager():
    return SimpleNamespace(
        id=7,
        role='manager',
        is_admin=False,
        is_manager=True,
        is_reviewer=False,
        workshop_id=None,
        data_scope_type='all',
    )


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / 'test.db'
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    def _get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _fake_manager
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestCumulativeEndpoint:
    """GET /api/v1/dashboard/cumulative returns month-to-date aggregates."""

    def test_endpoint_exists(self, client):
        response = client.get('/api/v1/dashboard/cumulative', params={'target_date': '2026-05-14'})
        assert response.status_code != 404, 'Endpoint /cumulative must exist'

    def test_response_has_required_fields(self, client):
        response = client.get('/api/v1/dashboard/cumulative', params={'target_date': '2026-05-14'})
        assert response.status_code == 200
        data = response.json()
        assert 'month_total_output' in data
        assert 'month_total_energy' in data
        assert 'average_daily_output' in data
        assert 'active_days' in data


class TestComparisonEndpoint:
    """GET /api/v1/dashboard/comparison returns day-over-day / week-over-week."""

    def test_endpoint_exists(self, client):
        response = client.get('/api/v1/dashboard/comparison', params={'target_date': '2026-05-14'})
        assert response.status_code != 404, 'Endpoint /comparison must exist'

    def test_response_has_required_fields(self, client):
        response = client.get('/api/v1/dashboard/comparison', params={'target_date': '2026-05-14'})
        assert response.status_code == 200
        data = response.json()
        assert 'day_over_day' in data
        assert 'week_over_week' in data


class TestTimeseriesEndpoint:
    """GET /api/v1/dashboard/timeseries returns daily data points."""

    def test_endpoint_exists(self, client):
        response = client.get(
            '/api/v1/dashboard/timeseries',
            params={'start_date': '2026-05-01', 'end_date': '2026-05-14'},
        )
        assert response.status_code != 404, 'Endpoint /timeseries must exist'

    def test_response_is_list_of_points(self, client):
        response = client.get(
            '/api/v1/dashboard/timeseries',
            params={'start_date': '2026-05-01', 'end_date': '2026-05-14'},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestCalculatorDelegation:
    """Aggregation endpoints must use domain/calculators, not inline formulas."""

    def test_month_average_via_calculator(self):
        from app.domain.calculators.production_calculators import month_average_daily_output
        assert month_average_daily_output(3000.0, 15) == pytest.approx(200.0)

    def test_day_over_day_via_calculator(self):
        from app.domain.calculators.production_calculators import day_over_day_change
        assert day_over_day_change(220.0, 200.0) == pytest.approx(0.1)

    def test_reporting_rate_via_calculator(self):
        from app.domain.calculators.production_calculators import reporting_rate
        assert reporting_rate(18, 20) == pytest.approx(0.9)
