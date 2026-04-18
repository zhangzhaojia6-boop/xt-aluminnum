from fastapi.testclient import TestClient

from app.core import health as health_service
from app.main import app


def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_healthz(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "app.main.health_service.build_liveness_payload",
        lambda: {"status": "ok", "service": "aluminum-bypass", "checks": {"app": "ok"}},
    )

    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["checks"]["app"] == "ok"


def test_readyz_ok(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "app.main.health_service.build_readiness_payload",
        lambda: (
            True,
            {"status": "ready", "checks": {"database": "ok", "uploads": "ok"}},
        ),
    )

    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"
    assert resp.json()["checks"]["database"] == "ok"


def test_readyz_not_ready(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "app.main.health_service.build_readiness_payload",
        lambda: (
            False,
            {"status": "not_ready", "checks": {"database": "error", "uploads": "ok"}},
        ),
    )

    resp = client.get("/readyz")
    assert resp.status_code == 503
    assert resp.json()["status"] == "not_ready"
    assert resp.json()["checks"]["database"] == "error"


def test_build_readiness_payload_includes_pipeline_gate(monkeypatch):
    monkeypatch.setattr("app.core.health._check_database", lambda: None)
    monkeypatch.setattr("app.core.health._check_upload_dir", lambda: None)
    monkeypatch.setattr("app.core.health.settings.AUTO_PIPELINE_REQUIRE_READY", True)
    monkeypatch.setattr(
        "app.core.health.inspect_pipeline_readiness",
        lambda target_date=None: {
            "target_date": "2026-04-06",
            "hard_gate_passed": False,
            "hard_issues": [{"code": "SCHEDULE_EMPTY"}],
            "warning_issues": [],
            "stats": {},
        },
    )

    ready, payload = health_service.build_readiness_payload()

    assert ready is False
    assert payload["checks"]["pipeline"] == "blocked"
    assert payload["details"]["pipeline"]["hard_issues"][0]["code"] == "SCHEDULE_EMPTY"


def test_build_readiness_payload_includes_mes_sync_details_when_mes_adapter_enabled(monkeypatch):
    monkeypatch.setattr("app.core.health._check_database", lambda: None)
    monkeypatch.setattr("app.core.health._check_upload_dir", lambda: None)
    monkeypatch.setattr("app.core.health.settings.AUTO_PIPELINE_REQUIRE_READY", False)
    monkeypatch.setattr("app.core.health.settings.MES_ADAPTER", "rest_api")
    monkeypatch.setattr(
        "app.services.mes_sync_service.latest_sync_status",
        lambda _db: {
            "last_run_status": "success",
            "lag_seconds": 120.0,
            "last_synced_at": "2026-04-11T10:01:00+08:00",
        },
    )

    ready, payload = health_service.build_readiness_payload()

    assert ready is True
    assert payload["checks"]["mes_sync"] == "ok"
    assert payload["details"]["mes_sync"]["lag_seconds"] == 120.0
