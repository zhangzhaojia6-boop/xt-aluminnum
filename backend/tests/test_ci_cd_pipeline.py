from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding='utf-8')


def test_backend_completion_ci_cd_artifacts_exist() -> None:
    assert (REPO_ROOT / '.github/workflows/ci.yml').exists()
    assert (REPO_ROOT / '.github/workflows/deploy-staging.yml').exists()
    assert (REPO_ROOT / '.github/workflows/production-sync-status.yml').exists()
    assert (REPO_ROOT / 'backend/Dockerfile').exists()


def test_ci_workflow_runs_backend_tests_and_frontend_build() -> None:
    source = _read('.github/workflows/ci.yml')

    assert 'python-version: "3.11"' in source
    assert 'python -m pytest' in source
    assert 'node-version: "20"' in source
    assert 'npm ci' in source
    assert 'npm run build' in source


def test_production_sync_requires_manual_confirm_and_exact_sha_deploy() -> None:
    source = _read('.github/workflows/production-sync-status.yml')

    assert 'workflow_dispatch:' in source
    assert "github.event.inputs.confirm == 'prod-sync'" in source
    assert 'datahub_sha:' in source
    assert 'hermes_sha:' in source
    assert 'PROD_SSH_HOST' in source
    assert 'DATAHUB_REPO="/srv/aluminum-bypass"' in source
    assert 'require_trusted_head' in source
    assert 'checkout --detach "$DATAHUB_SHA"' in source
    assert 'systemctl restart aluminum-bypass' in source
    assert 'curl -fsS http://127.0.0.1:8000/readyz' in source
    assert 'DEPLOY_FAILED_ROLLBACK_START' in source


def test_deploy_staging_builds_images_and_has_optional_ssh_deploy() -> None:
    source = _read('.github/workflows/deploy-staging.yml')

    assert 'docker build -t xintai-backend:staging ./backend' in source
    assert 'docker build -f frontend/Dockerfile -t xintai-frontend:staging .' in source
    assert 'STAGING_SSH_HOST is not configured; image build completed.' in source
    assert 'git pull --ff-only' in source


def test_backend_dockerfile_uses_multi_stage_build() -> None:
    source = _read('backend/Dockerfile')

    assert 'FROM python:3.11-slim AS builder' in source
    assert 'python -m venv /opt/venv' in source
    assert 'COPY --from=builder /opt/venv /opt/venv' in source
    assert 'USER app' in source
    assert 'HEALTHCHECK' in source
