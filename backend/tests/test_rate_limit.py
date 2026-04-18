from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.core.permissions import get_current_manager_user
from app.core.rate_limit import ConcurrentConnectionLimiter, SlidingWindowRateLimiter, reset_rate_limits
from app.main import app


class DummyDB:
    pass


def test_sliding_window_rate_limiter_rejects_after_limit_and_recovers() -> None:
    limiter = SlidingWindowRateLimiter()

    allowed_1 = limiter.consume('user:1:dashboard', limit=2, window_seconds=60, now=0.0)
    allowed_2 = limiter.consume('user:1:dashboard', limit=2, window_seconds=60, now=1.0)
    blocked = limiter.consume('user:1:dashboard', limit=2, window_seconds=60, now=2.0)
    recovered = limiter.consume('user:1:dashboard', limit=2, window_seconds=60, now=61.0)

    assert allowed_1.allowed is True
    assert allowed_2.allowed is True
    assert blocked.allowed is False
    assert blocked.retry_after == 58
    assert recovered.allowed is True


def test_concurrent_connection_limiter_blocks_third_connection_until_release() -> None:
    limiter = ConcurrentConnectionLimiter()

    permit_1 = limiter.acquire('user:1:realtime', limit=2)
    permit_2 = limiter.acquire('user:1:realtime', limit=2)
    blocked = limiter.acquire('user:1:realtime', limit=2)

    assert permit_1 is not None
    assert permit_2 is not None
    assert blocked is None

    permit_1.release()
    permit_3 = limiter.acquire('user:1:realtime', limit=2)

    assert permit_3 is not None


def test_factory_dashboard_rate_limit_returns_429(monkeypatch) -> None:
    reset_rate_limits()

    def fake_get_db():
        yield DummyDB()

    def fake_get_user():
        return SimpleNamespace(
            id=7,
            role='manager',
            is_admin=False,
            is_manager=True,
            is_reviewer=False,
            workshop_id=None,
            data_scope_type='all',
        )

    monkeypatch.setattr('app.routers.dashboard.report_service.build_factory_dashboard', lambda *_args, **_kwargs: {'ok': True})
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_manager_user] = fake_get_user

    client = TestClient(app)
    try:
        for _ in range(30):
            response = client.get('/api/v1/dashboard/factory')
            assert response.status_code == 200

        response = client.get('/api/v1/dashboard/factory')
        assert response.status_code == 429
        assert response.json()['detail'] == 'Rate limit exceeded'
    finally:
        app.dependency_overrides.clear()
        reset_rate_limits()
