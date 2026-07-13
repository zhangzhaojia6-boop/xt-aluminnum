from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import tempfile

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATHS = (
    '.github/workflows/production-sync-status.yml',
    '.github/workflows/configure-dingtalk-stream-prod.yml',
)


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


def _require_bash() -> str:
    bash = shutil.which('bash')
    assert bash is not None, 'bash is required to syntax-check workflow run blocks on this machine'
    return bash


def _workflow_run_blocks(path: str) -> list[tuple[str, str]]:
    payload = _load(path)
    jobs = payload.get('jobs')
    assert isinstance(jobs, dict)
    blocks: list[tuple[str, str]] = []
    for job_name, job_payload in jobs.items():
        assert isinstance(job_payload, dict)
        steps = job_payload.get('steps', [])
        assert isinstance(steps, list)
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            run = step.get('run')
            if isinstance(run, str):
                blocks.append((f'{job_name}-step{index}', run))
    return blocks


def _find_rollback_trap_line(source: str) -> str:
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if line.startswith('trap ') and 'rollback_on_error' in line:
            return line
    raise AssertionError('rollback trap line not found')


def _extract_shell_function(source: str, name: str) -> str:
    lines = source.splitlines()
    start_index = None
    for index, raw_line in enumerate(lines):
        if raw_line.strip().startswith(f'{name}()'):
            start_index = index
            break
    assert start_index is not None, f'{name}() not found'

    brace_depth = 0
    collected: list[str] = []
    for raw_line in lines[start_index:]:
        collected.append(raw_line)
        brace_depth += raw_line.count('{')
        brace_depth -= raw_line.count('}')
        if brace_depth == 0 and raw_line.strip() == '}':
            break
    return '\n'.join(collected)


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
    assert "trap 'rc=$?; if [ \"$rc\" -ne 0 ]; then rollback_on_error \"$rc\"; fi' EXIT" in source
    assert 'trap rollback_on_error ERR' not in source
    rollback_body = _extract_shell_function(source, 'rollback_on_error')
    assert 'ROLLBACK_FAILED_' in rollback_body
    assert '|| true' not in rollback_body
    assert 'DEPLOY_FAILED_ROLLBACK_DONE' in rollback_body
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


def test_production_sync_status_exit_trap_rolls_back_on_manual_failure_after_mutation() -> None:
    bash = _require_bash()
    trap_line = _find_rollback_trap_line(_read('.github/workflows/production-sync-status.yml'))
    tmp_root = REPO_ROOT
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='\n', suffix='.sh', dir=tmp_root, delete=False) as handle:
        script_path = Path(handle.name)
    marker_path = script_path.with_suffix('.log')
    try:
        script_path.write_text(
            "\n".join(
                [
                    '#!/usr/bin/env bash',
                    'set -euo pipefail',
                    f'MARKER_PATH="{marker_path.name}"',
                    'CHECKOUT_DONE=1',
                    'rollback_on_error() {',
                    '  local rc="${1:-$?}"',
                    '  trap - EXIT ERR',
                    '  echo "DEPLOY_FAILED_ROLLBACK_START"',
                    '  echo "rollback rc=$rc" >> "$MARKER_PATH"',
                    '  echo "DEPLOY_FAILED_ROLLBACK_DONE"',
                    '  exit "$rc"',
                    '}',
                    trap_line,
                    'exit 42',
                    '',
                ]
            ),
            encoding='utf-8',
            newline='\n',
        )
        result = subprocess.run(
            [bash, script_path.name],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_root,
        )
        marker_text = marker_path.read_text(encoding='utf-8').strip() if marker_path.exists() else ''
    finally:
        if marker_path.exists():
            os.unlink(marker_path)
        if script_path.exists():
            os.unlink(script_path)

    assert result.returncode == 42
    assert 'DEPLOY_FAILED_ROLLBACK_START' in result.stdout
    assert 'DEPLOY_FAILED_ROLLBACK_DONE' in result.stdout
    assert marker_text == 'rollback rc=42'


def test_target_workflow_run_blocks_pass_bash_n() -> None:
    bash = _require_bash()
    temp_paths: list[Path] = []
    try:
        failures: list[str] = []
        for workflow_path in WORKFLOW_PATHS:
            for block_name, run_block in _workflow_run_blocks(workflow_path):
                with tempfile.NamedTemporaryFile(
                    'w',
                    encoding='utf-8',
                    newline='\n',
                    prefix=f'{Path(workflow_path).stem}-{block_name}-',
                    suffix='.sh',
                    dir=REPO_ROOT,
                    delete=False,
                ) as handle:
                    shell_path = Path(handle.name)
                temp_paths.append(shell_path)
                shell_path.write_text(run_block, encoding='utf-8', newline='\n')
                result = subprocess.run(
                    [bash, '-n', shell_path.name],
                    capture_output=True,
                    text=True,
                    check=False,
                    cwd=REPO_ROOT,
                )
                if result.returncode != 0:
                    failures.append(
                        f'{workflow_path}:{block_name}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}'
                    )
        assert not failures, '\n\n'.join(failures)
    finally:
        for temp_path in temp_paths:
            if temp_path.exists():
                os.unlink(temp_path)
