from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding='utf-8')


def test_backend_completion_ci_cd_artifacts_exist() -> None:
    assert (REPO_ROOT / '.github/workflows/ci.yml').exists()
    assert (REPO_ROOT / '.github/workflows/deploy-staging.yml').exists()
    assert (REPO_ROOT / '.github/workflows/deploy-prod.yml').exists()
    assert (REPO_ROOT / 'backend/Dockerfile').exists()


def test_ci_workflow_runs_backend_tests_and_frontend_build() -> None:
    source = _read('.github/workflows/ci.yml')

    assert 'python-version: "3.11"' in source
    assert 'python -m pytest' in source or 'pytest' in source
    assert 'node-version: "20"' in source
    assert 'npm ci' in source
    assert 'npm run build' in source


def test_deploy_prod_requires_manual_confirm_and_builds_images() -> None:
    source = _read('.github/workflows/deploy-prod.yml')

    assert 'workflow_dispatch:' in source
    assert "github.event.inputs.confirm == 'deploy'" in source
    assert 'docker build -t xintai-backend:prod ./backend' in source
    assert 'docker build -t xintai-frontend:prod ./frontend' in source
    assert 'PROD_SSH_HOST' in source


def test_deploy_staging_builds_images_and_has_optional_ssh_deploy() -> None:
    source = _read('.github/workflows/deploy-staging.yml')

    assert 'docker build -t xintai-backend:staging ./backend' in source
    assert 'docker build -t xintai-frontend:staging ./frontend' in source
    assert 'STAGING_SSH_HOST is not configured; image build completed.' in source
    assert 'git pull --ff-only' in source


def test_backend_dockerfile_uses_multi_stage_build() -> None:
    source = _read('backend/Dockerfile')

    assert 'FROM python:3.11-slim AS builder' in source
    assert 'python -m venv /opt/venv' in source
    assert 'COPY --from=builder /opt/venv /opt/venv' in source
    assert 'USER app' in source
    assert 'HEALTHCHECK' in source
