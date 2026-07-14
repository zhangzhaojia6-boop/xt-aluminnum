from fastapi.testclient import TestClient

from app.core import health as health_service
from app.main import app


def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["version"]


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


def test_api_v1_healthz_matches_liveness(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "app.main.health_service.build_liveness_payload",
        lambda: {"status": "ok", "service": "aluminum-bypass", "checks": {"app": "ok"}},
    )

    resp = client.get("/api/v1/healthz")
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


def test_api_v1_readyz_matches_readiness(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "app.main.health_service.build_readiness_payload",
        lambda: (
            True,
            {"status": "ready", "checks": {"database": "ok", "uploads": "ok"}},
        ),
    )

    resp = client.get("/api/v1/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"
    assert resp.json()["checks"]["database"] == "ok"


def test_versionz_returns_datahub_and_hermes_sha(monkeypatch):
    client = TestClient(app)

    monkeypatch.setenv("BUILD_SHA", "datahub-sha")
    monkeypatch.setenv("HERMES_BUILD_SHA", "hermes-sha")

    resp = client.get("/versionz")

    assert resp.status_code == 200
    assert resp.json() == {
        "datahub_sha": "datahub-sha",
        "hermes_sha": "hermes-sha",
    }
    assert resp.headers["cache-control"] == "no-store"
    assert resp.headers["pragma"] == "no-cache"


def test_versionz_returns_null_when_shas_are_unset(monkeypatch):
    client = TestClient(app)

    monkeypatch.delenv("BUILD_SHA", raising=False)
    monkeypatch.delenv("HERMES_BUILD_SHA", raising=False)

    resp = client.get("/versionz")

    assert resp.status_code == 200
    assert resp.json() == {
        "datahub_sha": None,
        "hermes_sha": None,
    }


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


def test_build_readiness_payload_keeps_warning_pipeline_ready(monkeypatch):
    monkeypatch.setattr("app.core.health._check_database", lambda: None)
    monkeypatch.setattr("app.core.health._check_upload_dir", lambda: None)
    monkeypatch.setattr("app.core.health.settings.AUTO_PIPELINE_REQUIRE_READY", True)
    monkeypatch.setattr(
        "app.core.health.inspect_pipeline_readiness",
        lambda target_date=None: {
            "target_date": "2026-04-06",
            "hard_gate_passed": True,
            "hard_issues": [],
            "warning_issues": [{"code": "SCHEDULE_EMPTY"}],
            "checks": {
                "equipment_binding": {"status": "warning", "action_required": "bind_machine_users"},
                "schedule": {"status": "warning", "action_required": "seed_schedule"},
            },
            "stats": {},
        },
    )

    ready, payload = health_service.build_readiness_payload()

    assert ready is True
    assert payload["status"] == "ready"
    assert payload["checks"]["pipeline"] == "warning"
    assert payload["checks"]["equipment_binding"] == "warning"
    assert payload["checks"]["schedule"] == "warning"


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


def test_build_readiness_payload_warns_on_stale_mes_sync(monkeypatch):
    monkeypatch.setattr("app.core.health._check_database", lambda: None)
    monkeypatch.setattr("app.core.health._check_upload_dir", lambda: None)
    monkeypatch.setattr("app.core.health.settings.AUTO_PIPELINE_REQUIRE_READY", False)
    monkeypatch.setattr("app.core.health.settings.MES_ADAPTER", "mvc")
    monkeypatch.setattr(
        "app.services.mes_sync_service.latest_sync_status",
        lambda _db: {
            "status": "stale",
            "last_run_status": "success",
            "configured": True,
            "migration_ready": True,
            "source": "mes_projection",
            "lag_seconds": 1800.0,
            "action_required": "check_sync_lag",
        },
    )

    ready, payload = health_service.build_readiness_payload()

    assert ready is True
    assert payload["status"] == "ready"
    assert payload["checks"]["mes_sync"] == "stale"
    assert payload["details"]["mes_sync"]["action_required"] == "check_sync_lag"


def test_build_readiness_payload_trusts_fresh_mes_sync_status_over_business_event_lag(monkeypatch):
    monkeypatch.setattr("app.core.health._check_database", lambda: None)
    monkeypatch.setattr("app.core.health._check_upload_dir", lambda: None)
    monkeypatch.setattr("app.core.health.settings.AUTO_PIPELINE_REQUIRE_READY", False)
    monkeypatch.setattr("app.core.health.settings.MES_ADAPTER", "sqlserver")
    monkeypatch.setattr(
        "app.services.mes_sync_service.latest_sync_status",
        lambda _db: {
            "status": "fresh",
            "last_run_status": "success",
            "configured": True,
            "migration_ready": True,
            "source": "mes_projection",
            "lag_seconds": 35046.0,
            "sync_freshness_seconds": 46.0,
            "action_required": "none",
        },
    )

    ready, payload = health_service.build_readiness_payload()

    assert ready is True
    assert payload["status"] == "ready"
    assert payload["checks"]["mes_sync"] == "ok"
    assert payload["details"]["mes_sync"]["status"] == "fresh"
    assert payload["details"]["mes_sync"]["lag_seconds"] == 46.0
    assert payload["details"]["mes_sync"]["sync_lag_seconds"] == 46.0
    assert payload["details"]["mes_sync"]["source_lag_seconds"] == 35046.0


def test_build_readiness_payload_reports_mes_unconfigured_as_ready(monkeypatch):
    monkeypatch.setattr("app.core.health._check_database", lambda: None)
    monkeypatch.setattr("app.core.health._check_upload_dir", lambda: None)
    monkeypatch.setattr("app.core.health.settings.AUTO_PIPELINE_REQUIRE_READY", False)
    monkeypatch.setattr("app.core.health.settings.MES_ADAPTER", "null")

    ready, payload = health_service.build_readiness_payload()

    assert ready is True
    assert payload["checks"]["mes_sync"] == "unconfigured"
    assert payload["details"]["mes_sync"]["status"] == "unconfigured"
    assert payload["details"]["mes_sync"]["action_required"] == "configure_mes"


def test_build_readiness_payload_warns_on_stale_iot_energy_sync(monkeypatch):
    monkeypatch.setattr("app.core.health._check_database", lambda: None)
    monkeypatch.setattr("app.core.health._check_upload_dir", lambda: None)
    monkeypatch.setattr("app.core.health.settings.AUTO_PIPELINE_REQUIRE_READY", False)
    monkeypatch.setattr("app.core.health.settings.MES_ADAPTER", "null")
    monkeypatch.setattr("app.core.health.settings.IOT_ENERGY_ADAPTER", "sqlserver")
    monkeypatch.setattr(
        "app.services.iot_energy_sync_service.latest_sync_status",
        lambda _db: {
            "status": "stale",
            "configured": True,
            "source": "iot_energy",
            "lag_seconds": 1800.0,
            "action_required": "check_iot_energy_lag",
        },
    )

    ready, payload = health_service.build_readiness_payload()

    assert ready is True
    assert payload["status"] == "ready"
    assert payload["checks"]["iot_energy_sync"] == "stale"
    assert payload["details"]["iot_energy_sync"]["action_required"] == "check_iot_energy_lag"


def test_build_readiness_payload_reports_mes_projection_migration_missing_without_blocking_app_ready(monkeypatch):
    monkeypatch.setattr("app.core.health._check_database", lambda: None)
    monkeypatch.setattr("app.core.health._check_upload_dir", lambda: None)
    monkeypatch.setattr("app.core.health.settings.AUTO_PIPELINE_REQUIRE_READY", False)
    monkeypatch.setattr("app.core.health.settings.MES_ADAPTER", "rest_api")
    monkeypatch.setattr(
        "app.services.mes_sync_service.latest_sync_status",
        lambda _db: {
            "status": "migration_missing",
            "configured": True,
            "migration_ready": False,
            "source": "local_entry",
            "lag_seconds": None,
            "action_required": "run_migration",
        },
    )

    ready, payload = health_service.build_readiness_payload()

    assert ready is True
    assert payload["status"] == "ready"
    assert payload["checks"]["mes_sync"] == "migration_missing"
    assert payload["details"]["mes_sync"]["action_required"] == "run_migration"


def test_build_readiness_payload_redacts_failed_mes_sync_error(monkeypatch):
    monkeypatch.setattr("app.core.health._check_database", lambda: None)
    monkeypatch.setattr("app.core.health._check_upload_dir", lambda: None)
    monkeypatch.setattr("app.core.health.settings.AUTO_PIPELINE_REQUIRE_READY", False)
    monkeypatch.setattr("app.core.health.settings.MES_ADAPTER", "rest_api")
    monkeypatch.setattr(
        "app.services.mes_sync_service.latest_sync_status",
        lambda _db: {
            "status": "failed",
            "configured": True,
            "migration_ready": True,
            "source": "mes_projection",
            "lag_seconds": None,
            "error_message": "SELECT secret FROM mes_sync_run_logs",
            "last_error": "dsn=vendor-token",
            "action_required": "check_vendor",
        },
    )

    ready, payload = health_service.build_readiness_payload()

    assert ready is True
    assert payload["status"] == "ready"
    assert payload["checks"]["mes_sync"] == "failed"
    assert payload["details"]["mes_sync"]["status"] == "failed"
    assert payload["details"]["mes_sync"]["error_message"] == "redacted"
    assert payload["details"]["mes_sync"]["last_error"] == "redacted"
    assert "SELECT secret" not in repr(payload["details"]["mes_sync"])
    assert "vendor-token" not in repr(payload["details"]["mes_sync"])


def test_build_readiness_payload_marks_mes_exception_as_external_health_and_sanitizes_details(monkeypatch):
    class FakeDB:
        def close(self):
            return None

    monkeypatch.setattr("app.core.health._check_database", lambda: None)
    monkeypatch.setattr("app.core.health._check_upload_dir", lambda: None)
    monkeypatch.setattr("app.core.health.settings.AUTO_PIPELINE_REQUIRE_READY", False)
    monkeypatch.setattr("app.core.health.settings.MES_ADAPTER", "rest_api")
    monkeypatch.setattr("app.core.health.get_sessionmaker", lambda: lambda: FakeDB())

    def broken_latest_sync_status(_db):
        raise RuntimeError("SELECT secret FROM mes_sync_cursors")

    monkeypatch.setattr("app.services.mes_sync_service.latest_sync_status", broken_latest_sync_status)

    ready, payload = health_service.build_readiness_payload()

    assert ready is True
    assert payload["status"] == "ready"
    assert payload["checks"]["mes_sync"] == "error:RuntimeError"
    assert payload["details"]["mes_sync"]["status"] == "failed"
    assert payload["details"]["mes_sync"]["error"] == "RuntimeError"
    assert "SELECT secret" not in repr(payload["details"]["mes_sync"])
