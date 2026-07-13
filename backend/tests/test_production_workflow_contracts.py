from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding='utf-8')


def _load(path: str) -> dict:
    with (REPO_ROOT / path).open(encoding='utf-8') as handle:
        payload = yaml.safe_load(handle)
    assert isinstance(payload, dict)
    return payload


def _workflow_inputs(payload: dict) -> dict:
    on_block = payload.get('on', payload.get(True))
    assert isinstance(on_block, dict)
    dispatch = on_block.get('workflow_dispatch')
    assert isinstance(dispatch, dict)
    inputs = dispatch.get('inputs')
    assert isinstance(inputs, dict)
    return inputs


def test_production_sync_status_workflow_requires_exact_sha_deploy_and_rollback_contract() -> None:
    payload = _load('.github/workflows/production-sync-status.yml')
    source = _read('.github/workflows/production-sync-status.yml')
    inputs = _workflow_inputs(payload)
    mode_options = inputs['mode']['options']

    assert 'status' in mode_options
    assert 'deploy' in mode_options
    assert 'sync' not in mode_options
    assert 'datahub_sha' in inputs
    assert 'hermes_sha' in inputs
    assert "git merge --ff-only origin/main" not in source
    assert "backend/scripts/hermes_dingtalk_stream_gateway.py --health" not in source
    assert "^[0-9a-f]{40}$" in source
    assert 'checkout --detach "$DATAHUB_SHA"' in source
    assert 'checkout --detach "$HERMES_SHA"' in source
    assert 'pg_restore -l "$DB_BACKUP"' in source or 'pg_restore -l "$db_backup"' in source
    assert 'trap rollback_on_error ERR' in source
    assert '/versionz' in source
    assert 'BUILD_SHA' in source
    assert 'HERMES_BUILD_SHA' in source
    assert '/srv/aluminum-bypass' in source
    assert '/srv/hermes-cloud/runtime/.hermes/hermes-agent' in source


def test_production_sync_status_workflow_proves_stream_and_smoke_evidence_contract() -> None:
    source = _read('.github/workflows/production-sync-status.yml')

    assert '/api/v1/dingtalk/agent-inbound' in source
    assert 'x-dingtalk-inbound-token' in source
    assert 'smoke-trace' in source
    assert 'multimodal_evidence' in source
    assert 'chat_inbox' in source
    assert 'journalctl -u hermes-gateway' in source
    assert 'Connected via Stream Mode' in source
    assert 'systemctl show -p ActiveEnterTimestamp' in source


def test_configure_dingtalk_stream_prod_workflow_targets_real_gateway_contract() -> None:
    payload = _load('.github/workflows/configure-dingtalk-stream-prod.yml')
    source = _read('.github/workflows/configure-dingtalk-stream-prod.yml')
    inputs = _workflow_inputs(payload)

    assert inputs['authorized_group_ids']['default'] == '*'
    assert "backend/scripts/hermes_dingtalk_stream_gateway.py --health" not in source
    assert 'systemctl restart hermes-gateway' in source
    assert '/readyz' in source
    assert 'journalctl -u hermes-gateway' in source
    assert 'Connected via Stream Mode' in source
    assert 'systemctl show -p ActiveEnterTimestamp' in source
    assert 'multimodal_evidence' in source
    assert 'chat_inbox' in source
    assert 'external_message_logs' in source
