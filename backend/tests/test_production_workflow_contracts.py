from __future__ import annotations

import base64
import json
from pathlib import Path
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import time

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATHS = (
    '.github/workflows/production-sync-status.yml',
    '.github/workflows/configure-dingtalk-stream-prod.yml',
    '.github/workflows/configure-hermes-codex-prod.yml',
    '.github/workflows/read-hermes-codex-handoff-prod.yml',
    '.github/workflows/import-dingtalk-history-prod.yml',
    '.github/workflows/daily-report-alignment-prod.yml',
    '.github/workflows/hermes-acceptance-prod.yml',
    '.github/workflows/archive-prod-untracked.yml',
    '.github/workflows/mes-readonly-audit-prod.yml',
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


def _workflow_concurrency(payload: dict) -> dict:
    concurrency = payload.get('concurrency')
    assert isinstance(concurrency, dict)
    return concurrency


def _require_bash() -> str:
    bash = shutil.which('bash')
    if os.name == 'nt':
        candidates = (
            Path(os.environ.get('ProgramFiles', '')) / 'Git' / 'bin' / 'bash.exe',
            Path(os.environ.get('ProgramFiles', '')) / 'Git' / 'usr' / 'bin' / 'bash.exe',
        )
        bash = next((str(candidate) for candidate in candidates if candidate.is_file()), bash)
        if bash and Path(bash).resolve() == Path(os.environ.get('SystemRoot', 'C:\\Windows')) / 'System32' / 'bash.exe':
            pytest.skip('POSIX bash is required; Windows compatibility bash is unsupported')
    assert bash is not None, 'bash is required to syntax-check workflow run blocks on this machine'
    return bash


def _remove_test_tree(path: Path) -> None:
    if not path.exists():
        return
    assert path.resolve().parent == REPO_ROOT

    def remove_readonly(func, target, _exc_info) -> None:
        mode = stat.S_IRUSR | stat.S_IWUSR
        if Path(target).is_dir():
            mode |= stat.S_IXUSR
        os.chmod(target, mode)
        func(target)

    last_error: OSError | None = None
    for _attempt in range(3):
        try:
            shutil.rmtree(path, onerror=remove_readonly)
        except OSError as error:
            last_error = error
        if not path.exists():
            return
        time.sleep(0.05)
    raise AssertionError(f'failed to remove test directory: {path}') from last_error


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


def _find_rollback_trap_line(source: str, token: str = 'rollback_on_error') -> str:
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if line.startswith('trap ') and token in line:
            return line
    raise AssertionError(f'rollback trap line not found for {token}')


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


def _extract_hermes_gateway_verifier(source: str) -> str:
    capture_body = _extract_shell_function(source, 'capture_hermes_gateway_command_contract')
    start_marker = "<<'PY'\n"
    end_marker = '\n          PY'
    start = capture_body.find(start_marker)
    assert start >= 0, 'Hermes gateway verifier heredoc start not found'
    start += len(start_marker)
    end = capture_body.find(end_marker, start)
    assert end >= 0, 'Hermes gateway verifier heredoc end not found'
    return textwrap.dedent(capture_body[start:end])


def test_hermes_mutating_workflows_use_official_gateway_lifecycle() -> None:
    production = _read('.github/workflows/production-sync-status.yml')
    dingtalk = _read('.github/workflows/configure-dingtalk-stream-prod.yml')
    codex = _read('.github/workflows/configure-hermes-codex-prod.yml')

    production_stop = _extract_shell_function(production, 'stop_hermes_gateway')
    production_resolver = _extract_shell_function(
        production, 'resolve_hermes_runtime_python'
    )
    dingtalk_restart = _extract_shell_function(dingtalk, 'restart_hermes_gateway')
    dingtalk_resolver = _extract_shell_function(
        dingtalk, 'resolve_hermes_runtime_python'
    )
    codex_restart = _extract_shell_function(codex, 'restart_hermes_gateway')

    assert '-m hermes_cli.main gateway stop --system' in production_stop
    assert 'HERMES_GATEWAY_STOP=command_failed' in production_stop
    assert 'systemctl is-active --quiet hermes-gateway' in production_stop
    assert 'HERMES_GATEWAY_STOP=still_active' in production_stop
    assert '/proc/{runtime_pid}/cmdline' in production_resolver
    assert 'candidate.resolve() == runtime_executable' in production_resolver
    assert '"ExecStart", "--value", "hermes-gateway"' in production_resolver
    assert 'service_args[0]' in production_resolver
    assert '-m hermes_cli.main gateway restart --system' in dingtalk_restart
    assert '/proc/{runtime_pid}/cmdline' in dingtalk_resolver
    assert 'candidate.resolve() == runtime_executable' in dingtalk_resolver
    assert '"ExecStart", "--value", "hermes-gateway"' in dingtalk_resolver
    assert '-m hermes_cli.main gateway restart --system' in codex_restart
    for source in (production, dingtalk, codex):
        assert 'systemctl restart hermes-gateway' not in source
        assert 'systemctl stop hermes-gateway' not in source


def test_production_deploy_rejects_hermes_restart_journal_failures() -> None:
    source = _read('.github/workflows/production-sync-status.yml')
    journal_gate = _extract_shell_function(source, 'verify_hermes_restart_journal')

    assert 'journalctl -u hermes-gateway --since "@$since_epoch"' in journal_gate
    assert "Failed with result ['\\\"]exit-code['\\\"]" in journal_gate
    assert 'Feishu / Lark' in journal_gate
    assert 'No adapter available for feishu' in journal_gate
    assert 'restart_drain_timeout.*expected' in journal_gate
    assert 'systemctl show -p Result --value hermes-gateway' in journal_gate
    assert 'HERMES_RESTART_JOURNAL=clean' in journal_gate

    epoch_index = source.find('HERMES_RESTART_EPOCH="$(date +%s)"')
    stop_index = source.find('stop_hermes_gateway', epoch_index)
    stream_index = source.find('report_stream_connection "yes" 40 3', stop_index)
    gate_index = source.find(
        'verify_hermes_restart_journal "$HERMES_RESTART_EPOCH"',
        stream_index,
    )
    assert -1 not in (epoch_index, stop_index, stream_index, gate_index)
    assert epoch_index < stop_index < stream_index < gate_index


@pytest.mark.parametrize(
    ('cli_exit_code', 'expected_exit_code'),
    ((0, 0), (1, 1)),
)
def test_production_stop_uses_official_hermes_cli_and_propagates_failure(
    cli_exit_code: int,
    expected_exit_code: int,
) -> None:
    bash = _require_bash()
    source = _read('.github/workflows/production-sync-status.yml')
    stop_body = textwrap.dedent(
        _extract_shell_function(source, 'stop_hermes_gateway')
    )
    tmp_root = REPO_ROOT
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='\n', suffix='.sh', dir=tmp_root, delete=False) as handle:
        script_path = Path(handle.name)
    fake_python_path = script_path.with_suffix('.python')
    marker_path = script_path.with_suffix('.log')
    try:
        fake_python_path.write_text(
            '#!/usr/bin/env bash\nprintf "cli:%s\\n" "$*" >> "$MARKER_PATH"\nexit "$CLI_EXIT_CODE"\n',
            encoding='utf-8',
            newline='\n',
        )
        fake_python_path.chmod(fake_python_path.stat().st_mode | stat.S_IXUSR)
        script_path.write_text(
            "\n".join(
                [
                    '#!/usr/bin/env bash',
                    'set -euo pipefail',
                    f'FAKE_PYTHON="{fake_python_path.as_posix()}"',
                    f'MARKER_PATH="{marker_path.as_posix()}"',
                    f'CLI_EXIT_CODE={cli_exit_code}',
                    'HERMES_HOME=/test/hermes',
                    'export MARKER_PATH CLI_EXIT_CODE',
                    'resolve_hermes_runtime_python() { printf "%s\\n" "$FAKE_PYTHON"; }',
                    'systemctl() {',
                    '  if [ "$1" = "show" ]; then printf "4242\\n"; return 0; fi',
                    '  if [ "$1" = "is-active" ]; then return 1; fi',
                    '  printf "systemctl:%s\\n" "$*" >> "$MARKER_PATH"',
                    '}',
                    stop_body,
                    'if stop_hermes_gateway; then exit 0; else rc=$?; exit "$rc"; fi',
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
            timeout=15,
        )
        marker_lines = marker_path.read_text(encoding='utf-8').splitlines() if marker_path.exists() else []
    finally:
        if marker_path.exists():
            os.unlink(marker_path)
        if fake_python_path.exists():
            os.unlink(fake_python_path)
        if script_path.exists():
            os.unlink(script_path)

    assert result.returncode == expected_exit_code
    assert marker_lines == ['cli:-P -m hermes_cli.main gateway stop --system']


def test_mes_readonly_audit_workflow_is_pinned_sanitized_and_compare_only() -> None:
    path = '.github/workflows/mes-readonly-audit-prod.yml'
    payload = _load(path)
    source = _read(path)
    inputs = _workflow_inputs(payload)
    concurrency = _workflow_concurrency(payload)
    job = payload['jobs']['mes-readonly-audit-prod']

    assert inputs['confirm']['description'].find('mes-readonly-audit') >= 0
    assert {'confirm', 'datahub_sha', 'hermes_sha'} <= set(inputs)
    assert job['if'] == "github.event.inputs.confirm == 'mes-readonly-audit'"
    assert job['environment'] == 'production'
    assert concurrency == {
        'group': 'xintai-production-ops',
        'cancel-in-progress': False,
    }
    assert 'SSH_KNOWN_HOSTS: ${{ secrets.PROD_SSH_KNOWN_HOSTS }}' in source
    assert 'StrictHostKeyChecking=yes' in source
    assert 'UserKnownHostsFile=~/.ssh/known_hosts' in source
    assert 'ssh-keyscan' not in source
    assert "grep -Eq '^[0-9a-f]{40}$'" in source
    assert 'git -C "$DATAHUB_REPO" status --porcelain' in source
    assert 'git -C "$HERMES_REPO" status --porcelain' in source
    assert 'git -C "$DATAHUB_REPO" rev-parse HEAD' in source
    assert 'git -C "$HERMES_REPO" rev-parse HEAD' in source
    assert '[ "$actual_datahub_sha" = "$EXPECTED_DATAHUB_SHA" ]' in source
    assert '[ "$actual_hermes_sha" = "$EXPECTED_HERMES_SHA" ]' in source
    assert '/srv/aluminum-bypass/backend/.venv/bin/python' in source
    assert 'scripts/check_mes_readonly_reliability.py' in source
    assert '--days 3' in source
    assert '--fault-drill' in source
    assert '--json' in source
    assert '/var/lib/aluminum-bypass/acceptance/mes-readonly-audit-' in source
    assert 'scp -i ~/.ssh/deploy_key' in source
    assert 'actions/upload-artifact@v4' in source
    assert 'if: always()' in source
    assert 'if-no-files-found: warn' in source
    assert 'DATABASE_URL' not in source
    assert 'MES_SQLSERVER_PASSWORD' not in source
    assert 'printenv' not in source
    assert 'set -x' not in source
    assert 'SELECT ' not in source
    assert 'psql ' not in source
    assert 'sqlcmd ' not in source
    assert 'cat "$remote_artifact"' not in source


def test_production_sync_status_workflow_requires_exact_sha_deploy_and_rollback_contract() -> None:
    payload = _load('.github/workflows/production-sync-status.yml')
    source = _read('.github/workflows/production-sync-status.yml')
    inputs = _workflow_inputs(payload)
    concurrency = _workflow_concurrency(payload)
    mode_options = inputs['mode']['options']

    assert concurrency == {
        'group': 'xintai-production-ops',
        'cancel-in-progress': False,
    }
    assert 'status' in mode_options
    assert 'deploy' in mode_options
    assert 'rollback' in mode_options
    assert 'sync' not in mode_options
    assert 'datahub_sha' in inputs
    assert 'hermes_sha' in inputs
    assert 'rollback_confirm' in inputs
    assert "git merge --ff-only origin/main" not in source
    assert "backend/scripts/hermes_dingtalk_stream_gateway.py --health" not in source
    assert "^[0-9a-f]{40}$" in source
    assert 'checkout --detach "$DATAHUB_SHA"' in source
    assert 'checkout --detach "$HERMES_SHA"' in source
    assert 'pg_restore -l "$DB_BACKUP"' in source or 'pg_restore -l "$db_backup"' in source
    assert 'DATAHUB_TRUSTED_REF="origin/main"' in source
    assert 'HERMES_TRUSTED_REMOTE_URL="https://github.com/zhangzhaojia6-boop/hermes-agent.git"' in source
    assert 'HERMES_TRUSTED_BRANCH="refs/heads/main"' in source
    assert 'HERMES_TRUSTED_REF="refs/remotes/xintai_cloud/main"' in source
    assert 'trusted_head="$(git -C "$repo" rev-parse "$trusted_ref")"' in source
    assert 'if [ "$sha" != "$trusted_head" ]; then' in source
    assert 'fetch --prune "$HERMES_TRUSTED_REMOTE_URL" "+$HERMES_TRUSTED_BRANCH:$HERMES_TRUSTED_REF"' in source
    assert 'HERMES_TRUSTED_REF_UNAVAILABLE' in source
    assert 'require_commit_exists "$DATAHUB_REPO" "$DATAHUB_SHA"' in source
    assert 'update_trusted_refs' in source
    assert 'require_commit_exists "$HERMES_REPO" "$HERMES_SHA"' in source
    assert 'require_trusted_head "$DATAHUB_REPO" "$DATAHUB_SHA" "$DATAHUB_TRUSTED_REF" DATAHUB' in source
    assert 'require_trusted_head "$HERMES_REPO" "$HERMES_SHA" "$HERMES_TRUSTED_REF" HERMES' in source
    assert 'require_trusted_ancestor "$DATAHUB_REPO" "$DATAHUB_SHA" "$DATAHUB_TRUSTED_REF" DATAHUB' in source
    assert 'require_trusted_ancestor "$HERMES_REPO" "$HERMES_SHA" "$HERMES_TRUSTED_REF" HERMES' in source
    assert 'test "$ROLLBACK_CONFIRM" = "rollback-to-merged-sha"' in source
    assert 'append_remote_assignment()' in source
    assert 'printf -v REMOTE_PREAMBLE' in source
    assert 'MODE=\'$effective_mode\' DATAHUB_SHA=\'$DATAHUB_SHA\'' not in source
    assert '} | ssh -i ~/.ssh/deploy_key -p "$SSH_PORT" -o StrictHostKeyChecking=yes -o UserKnownHostsFile=~/.ssh/known_hosts "$SSH_USER@$SSH_HOST" "bash -s"' in source
    assert "trap 'rc=$?; if [ \"$rc\" -ne 0 ]; then rollback_on_error \"$rc\"; fi' EXIT" in source
    assert 'trap rollback_on_error ERR' not in source
    assert 'get_alembic_revisions()' in source
    assert 'alembic_revisions_valid()' in source
    assert 'alembic_single_revision_valid()' in source
    assert 'PRE_MIGRATION_REVISIONS' in source
    assert 'POST_MIGRATION_REVISIONS' in source
    assert 'PRE_MIGRATION_REVISION_DETECTION_FAILED' in source
    assert 'POST_MIGRATION_REVISION_DETECTION_FAILED' in source
    assert 'NEEDS_DB_RESTORE=1' in source
    assert 'if alembic_revisions_valid "$PRE_MIGRATION_REVISIONS" && alembic_revisions_valid "$POST_MIGRATION_REVISIONS" && [ "$PRE_MIGRATION_REVISIONS" = "$POST_MIGRATION_REVISIONS" ]; then' in source
    assert 'NEEDS_DB_RESTORE=0' in source
    datahub_exists_index = source.find('require_commit_exists "$DATAHUB_REPO" "$DATAHUB_SHA"')
    trusted_fetch_index = source.find('\n          update_trusted_refs\n')
    hermes_exists_index = source.find('require_commit_exists "$HERMES_REPO" "$HERMES_SHA"')
    trusted_head_index = source.find('require_trusted_head "$HERMES_REPO" "$HERMES_SHA" "$HERMES_TRUSTED_REF" HERMES')
    pre_index = source.find('if PRE_MIGRATION_REVISIONS="$(get_alembic_revisions "$RAW_DATABASE_URL")"; then')
    set_restore_index = source.find('NEEDS_DB_RESTORE=1')
    alembic_index = source.find('alembic upgrade head')
    post_index = source.find('if POST_MIGRATION_REVISIONS="$(get_alembic_revisions "$RAW_DATABASE_URL")"; then')
    reset_restore_index = source.find('NEEDS_DB_RESTORE=0', post_index)
    assert -1 not in (datahub_exists_index, trusted_fetch_index, hermes_exists_index, trusted_head_index, pre_index, set_restore_index, alembic_index, post_index, reset_restore_index)
    assert datahub_exists_index < trusted_fetch_index < hermes_exists_index < trusted_head_index < set_restore_index
    assert set_restore_index < pre_index < alembic_index < post_index < reset_restore_index
    rollback_body = _extract_shell_function(source, 'rollback_on_error')
    assert 'stop_hermes_gateway' in rollback_body
    assert 'systemctl stop aluminum-bypass' in rollback_body
    assert 'ROLLBACK_DATABASE_DOWNGRADE_TO=$PRE_MIGRATION_REVISIONS' in rollback_body
    assert 'ROLLBACK_FAILED_DATABASE_DOWNGRADE' in rollback_body
    assert 'alembic downgrade "$PRE_MIGRATION_REVISIONS"' in rollback_body
    assert 'pg_restore --single-transaction --exit-on-error --clean --if-exists --no-owner --no-privileges -d "$DATABASE_LIBPQ_URL" "$DB_BACKUP"' in rollback_body
    assert '"$DATAHUB_REPO/backend/.venv/bin/python" -m pip install -r "$DATAHUB_REPO/backend/requirements.txt"' in rollback_body
    assert 'npm ci --no-audit --no-fund &&' in rollback_body
    assert 'npm run build' in rollback_body
    assert 'restore_hermes_runtime_dropin' in rollback_body
    assert 'ROLLBACK_HERMES_RUNTIME_RESTORED' in rollback_body
    assert 'ROLLBACK_HERMES_DEPENDENCY_SYNC_SKIPPED' not in rollback_body
    assert 'ROLLBACK_FAILED_' in rollback_body
    assert '|| true' not in rollback_body
    assert 'DEPLOY_FAILED_ROLLBACK_DONE' in rollback_body
    hermes_stop_index = rollback_body.find('stop_hermes_gateway')
    stop_index = rollback_body.find('systemctl stop aluminum-bypass')
    migration_downgrade_index = rollback_body.find('alembic downgrade "$PRE_MIGRATION_REVISIONS"')
    repo_restore_index = rollback_body.find('checkout --detach "$PREVIOUS_DATAHUB_HEAD"')
    db_restore_index = rollback_body.find('pg_restore --single-transaction --exit-on-error --clean --if-exists --no-owner --no-privileges -d "$DATABASE_LIBPQ_URL" "$DB_BACKUP"')
    deps_restore_index = rollback_body.find('"$DATAHUB_REPO/backend/.venv/bin/python" -m pip install -r "$DATAHUB_REPO/backend/requirements.txt"')
    frontend_restore_index = rollback_body.find('npm run build')
    runtime_restore_index = rollback_body.find('restore_hermes_runtime_dropin')
    restart_index = rollback_body.find('systemctl restart aluminum-bypass')
    assert -1 not in (hermes_stop_index, stop_index, migration_downgrade_index, repo_restore_index, db_restore_index, deps_restore_index, frontend_restore_index, runtime_restore_index, restart_index)
    assert hermes_stop_index < stop_index < migration_downgrade_index < repo_restore_index < db_restore_index < deps_restore_index < frontend_restore_index < runtime_restore_index < restart_index
    assert 'ROLLBACK_FAILED_READYZ' in rollback_body
    assert source.rfind('trap - EXIT') > source.find('report_status "yes"')
    assert '/versionz' in source
    assert 'BUILD_SHA' in source
    assert 'HERMES_BUILD_SHA' in source
    assert '/srv/aluminum-bypass' in source
    assert '/srv/hermes-cloud/runtime/.hermes/hermes-agent' in source


def test_production_status_rejects_invalid_or_expiring_tls_certificate() -> None:
    source = _read('.github/workflows/production-sync-status.yml')
    tls_body = _extract_shell_function(source, 'report_tls_certificate')
    status_body = _extract_shell_function(source, 'report_status')

    assert 'PRODUCTION_DOMAIN="${PRODUCTION_DOMAIN:-xtmijd.com}"' in source
    assert 'openssl s_client -connect "${domain}:443" -servername "$domain"' in tls_body
    assert 'curl -fsS --max-time 15 "https://${domain}/healthz"' in tls_body
    assert 'openssl x509 -in "$cert_file" -checkend 1209600' in tls_body
    assert 'TLS_CERTIFICATE_STATUS=ok' in tls_body
    assert 'report_tls_certificate' in status_body


def test_production_sync_status_workflow_proves_stream_and_smoke_evidence_contract() -> None:
    source = _read('.github/workflows/production-sync-status.yml')

    assert '/api/v1/dingtalk/agent-inbound' in source
    assert 'x-dingtalk-inbound-signature' in source
    assert 'x-dingtalk-inbound-timestamp' in source
    assert 'x-dingtalk-inbound-nonce' in source
    assert 'x-dingtalk-inbound-kind' in source
    assert '-H "x-dingtalk-inbound-token:' not in source
    assert 'smoke_kind="task10_smoke"' in source
    assert 'xintaiSourceTransport' not in source
    assert 'smoke-trace' in source
    assert 'multimodal_evidence' in source
    assert 'chat_inbox' in source
    assert "source_payload->>'source_transport' = 'dingtalk_stream'" in source
    assert "payload->>'source_transport' = 'dingtalk_stream'" in source
    assert "LIKE 'dingtalk-stream-sha256:%'" not in source
    assert 'journalctl -u hermes-gateway' in source
    assert 'systemctl show -p ActiveEnterTimestamp' in source
    assert 'systemctl show -p MainPID' in source
    assert 'gateway_state.json' in source
    assert 'stream_runtime_state_is_connected' in source
    assert 'HERMES_STREAM_STATE_PID_MATCH=' in source
    assert 'HERMES_STREAM_STATE_START_MATCH=' in source
    assert 'HERMES_STREAM_STATE_DINGTALK=' in source
    assert "grep -F 'Connected via Stream Mode'" not in source
    assert 'local attempts="${2:-1}"' in source
    assert 'local delay_seconds="${3:-0}"' in source
    assert 'for attempt in $(seq 1 "$attempts")' in source
    assert 'sleep "$delay_seconds"' in source
    assert 'report_stream_connection "yes" 40 3' in source


def test_production_sync_status_reports_latest_stream_trace_without_message_content() -> None:
    source = _read('.github/workflows/production-sync-status.yml')
    diagnostic_body = _extract_shell_function(source, 'query_latest_stream_trace')
    report_body = _extract_shell_function(source, 'report_status')

    assert 'dingtalk_inbound_receipts' in diagnostic_body
    assert 'agent_runs' in diagnostic_body
    assert 'agent_outbox_messages' in diagnostic_body
    assert 'external_message_logs' in diagnostic_body
    assert 'run_answer_has_chinese' in diagnostic_body
    assert 'run_answer_has_source' in diagnostic_body
    assert 'run_answer_has_trace_id' in diagnostic_body
    assert '"run_answer":' not in diagnostic_body
    assert 'LATEST_STREAM_TRACE=$(query_latest_stream_trace "$RAW_DATABASE_URL")' in report_body


def test_production_stream_gate_emits_redacted_failure_diagnostics_before_rollback(tmp_path: Path) -> None:
    source = _read('.github/workflows/production-sync-status.yml')

    diagnostic_body = _extract_shell_function(source, 'report_stream_diagnostics')
    assert 'HERMES_STREAM_DIAGNOSTICS_START' in diagnostic_body
    assert 'HERMES_STREAM_DIAGNOSTICS_END' in diagnostic_body
    assert 'journalctl -u hermes-gateway' in diagnostic_body
    assert 'agent.log' in diagnostic_body
    assert 'gateway.log' in diagnostic_body
    assert 'errors.log' in diagnostic_body
    assert '[REDACTED]' in diagnostic_body
    assert 'access[_-]?token' in diagnostic_body
    assert '(?:client|app)[_-]?secret' in diagnostic_body
    assert '[?&](?:access[_-]?token|ticket|client[_-]?id' in diagnostic_body
    assert 'app[_-]?key' in diagnostic_body
    assert 'robot(?:[_-]?code)?' in diagnostic_body

    connection_body = _extract_shell_function(source, 'report_stream_connection')
    disconnected_index = connection_body.index('HERMES_STREAM_CONNECTED=no')
    diagnostic_index = connection_body.index('report_stream_diagnostics "$active_since"')
    failure_index = connection_body.index('return 1')
    assert disconnected_index < diagnostic_index < failure_index

    heredoc_start = diagnostic_body.index("<<'PY'\n") + len("<<'PY'\n")
    heredoc_end = diagnostic_body.index('\n          PY', heredoc_start)
    sanitizer = textwrap.dedent(diagnostic_body[heredoc_start:heredoc_end])
    diagnostic_file = tmp_path / 'stream.log'
    client_id = 'fake-client-id-for-redaction'
    client_secret = 'fake-client-secret-for-redaction'
    robot_code = 'fake-robot-code-for-redaction'
    diagnostic_file.write_text(
        '\n'.join(
            (
                '__JOURNAL__',
                (
                    '[dingtalk] Failed to connect '
                    f'client_id={client_id} app_secret={client_secret} '
                    f'robot={robot_code} access_token=fake-access-token '
                    'ticket=fake-ticket '
                    'client_id=legacy-client-id robot_code=legacy-robot-code app_key=legacy-app-key '
                    'endpoint=wss://api.dingtalk.com/v1.0/gateway/connections/open?ticket=fake-query-ticket '
                    'response={"ticket":"fake-json-ticket"} '
                    'authorization=Bearer fake-bearer-token '
                    'text="private-text" content=private-content '
                    'payload={"message":"private-message"}'
                ),
                'WARNING unrelated warning with private-warning-content',
                'ordinary chat content must-not-leak',
            )
        ),
        encoding='utf-8',
    )
    result = subprocess.run(
        [sys.executable, '-', str(diagnostic_file), client_id, client_secret, robot_code],
        input=sanitizer,
        text=True,
        capture_output=True,
        check=True,
    )
    assert '[dingtalk] Failed to connect' in result.stdout
    assert '[REDACTED]' in result.stdout
    assert client_id not in result.stdout
    assert client_secret not in result.stdout
    assert robot_code not in result.stdout
    assert 'fake-access-token' not in result.stdout
    assert 'fake-ticket' not in result.stdout
    assert 'fake-query-ticket' not in result.stdout
    assert 'fake-json-ticket' not in result.stdout
    assert 'legacy-client-id' not in result.stdout
    assert 'legacy-robot-code' not in result.stdout
    assert 'legacy-app-key' not in result.stdout
    assert 'fake-bearer-token' not in result.stdout
    assert 'private-text' not in result.stdout
    assert 'private-content' not in result.stdout
    assert 'private-message' not in result.stdout
    assert 'private-warning-content' not in result.stdout
    assert 'must-not-leak' not in result.stdout


def test_stream_diagnostic_failure_preserves_original_gate_exit_code(tmp_path: Path) -> None:
    bash = _require_bash()
    source = _read('.github/workflows/production-sync-status.yml')
    connection_body = textwrap.dedent(_extract_shell_function(source, 'report_stream_connection'))
    script_path = tmp_path / 'stream-gate.sh'
    script_path.write_text(
        '\n'.join(
            (
                '#!/usr/bin/env bash',
                'set -euo pipefail',
                'systemctl() {',
                '  if [ "$1" = "show" ]; then printf "%s\\n" "Wed 2026-07-15 08:00:00 CST"; fi',
                '  return 0',
                '}',
                'journalctl() { return 0; }',
                'report_stream_diagnostics() { return 73; }',
                connection_body,
                'set +e',
                '( set -e; report_stream_connection "yes" 1 0 ) > result.out 2>&1',
                'gate_rc="$?"',
                'set -e',
                '[ "$gate_rc" -eq 1 ]',
                'grep -Fq "HERMES_STREAM_DIAGNOSTICS_UNAVAILABLE" result.out',
                '',
            )
        ),
        encoding='utf-8',
        newline='\n',
    )
    result = subprocess.run(
        [bash, script_path.name],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    'workflow_path',
    (
        '.github/workflows/production-sync-status.yml',
        '.github/workflows/configure-dingtalk-stream-prod.yml',
    ),
)
def test_stream_runtime_gate_requires_current_service_pid_and_fresh_real_connection(
    workflow_path: str,
    tmp_path: Path,
) -> None:
    source = _read(workflow_path)
    assert 'active_since_epoch=9223372036854775807' in source
    assert 'active_since_epoch=0' not in source
    verifier_body = _extract_shell_function(source, 'stream_runtime_state_is_connected')
    heredoc_start = verifier_body.index("<<'PY'\n") + len("<<'PY'\n")
    heredoc_end = verifier_body.index('\n          PY', heredoc_start)
    verifier = textwrap.dedent(verifier_body[heredoc_start:heredoc_end])
    state_path = tmp_path / 'gateway_state.json'
    active_since_epoch = 1_752_537_600  # 2025-07-15T00:00:00Z

    def run_verifier(payload: dict) -> subprocess.CompletedProcess[str]:
        state_path.write_text(json.dumps(payload), encoding='utf-8')
        return subprocess.run(
            [sys.executable, '-', str(state_path), '4242', '777', str(active_since_epoch)],
            input=verifier,
            text=True,
            capture_output=True,
            check=False,
        )

    healthy = {
        'pid': 4242,
        'start_time': 777,
        'gateway_state': 'running',
        'platforms': {
            'dingtalk': {
                'state': 'connected',
                'updated_at': '2025-07-15T00:00:05+00:00',
            },
        },
    }
    result = run_verifier(healthy)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'HERMES_STREAM_STATE_PID_MATCH=yes' in result.stdout
    assert 'HERMES_STREAM_STATE_START_MATCH=yes' in result.stdout
    assert 'HERMES_STREAM_STATE_GATEWAY=running' in result.stdout
    assert 'HERMES_STREAM_STATE_DINGTALK=connected' in result.stdout
    assert 'HERMES_STREAM_STATE_FRESH=yes' in result.stdout

    for invalid in (
        {**healthy, 'pid': 9999},
        {**healthy, 'start_time': 666, 'platforms': {'dingtalk': {'state': 'connected', 'updated_at': '2025-07-15T00:00:00.100+00:00'}}},
        {**healthy, 'gateway_state': 'starting'},
        {**healthy, 'platforms': None},
        {
            **healthy,
            'platforms': {'dingtalk': {'state': 'disconnected', 'updated_at': '2025-07-15T00:00:05+00:00'}},
        },
        {
            **healthy,
            'platforms': {'dingtalk': {'state': 'connected', 'updated_at': '2025-07-14T23:59:59+00:00'}},
        },
    ):
        result = run_verifier(invalid)
        assert result.returncode != 0, result.stdout + result.stderr
        assert 'Traceback' not in result.stderr


def test_production_sync_deploy_applies_stream_config_inside_rollback_boundary() -> None:
    source = _read('.github/workflows/production-sync-status.yml')

    assert 'STREAM_APP_KEY: ${{ secrets.PROD_DINGTALK_STREAM_APP_KEY }}' in source
    assert 'STREAM_APP_SECRET: ${{ secrets.PROD_DINGTALK_STREAM_APP_SECRET }}' in source
    assert 'STREAM_ROBOT_CODE: ${{ secrets.PROD_DINGTALK_STREAM_ROBOT_CODE }}' in source
    assert 'STREAM_AGENT_ID: ${{ secrets.PROD_DINGTALK_STREAM_AGENT_ID }}' in source
    assert 'STREAM_APP_ID: ${{ secrets.PROD_DINGTALK_STREAM_APP_ID }}' in source
    assert 'if [ "$effective_mode" = "deploy" ]; then\n            test -n "$STREAM_APP_KEY"\n            test -n "$STREAM_APP_SECRET"\n          fi' in source
    assert 'append_remote_assignment STREAM_APP_KEY_B64 "$(b64 "$STREAM_APP_KEY")"' in source
    assert 'append_remote_assignment STREAM_APP_SECRET_B64 "$(b64 "$STREAM_APP_SECRET")"' in source

    apply_body = _extract_shell_function(source, 'apply_dingtalk_stream_config')
    assert 'upsert_env_value "$DATAHUB_ENV_FILE" "DINGTALK_STREAM_ENABLED" "true"' in apply_body
    assert 'upsert_env_value "$DATAHUB_ENV_FILE" "DINGTALK_AUTHORIZED_GROUP_IDS" "*"' in apply_body
    assert 'upsert_env_value "$HERMES_ENV_FILE" "DINGTALK_CLIENT_ID" "$stream_app_key"' in apply_body
    assert 'upsert_env_value "$HERMES_ENV_FILE" "DINGTALK_CLIENT_SECRET" "$stream_app_secret"' in apply_body
    assert 'upsert_env_value "$HERMES_ENV_FILE" "DINGTALK_ALLOWED_USERS" "*"' in apply_body
    assert 'upsert_env_value "$HERMES_ENV_FILE" "DINGTALK_ALLOWED_CHATS" ""' in apply_body
    assert 'upsert_env_value "$HERMES_ENV_FILE" "DINGTALK_FREE_RESPONSE_CHATS" ""' in apply_body
    assert 'upsert_env_value "$HERMES_ENV_FILE" "DINGTALK_REQUIRE_MENTION" "true"' in apply_body
    assert 'HERMES_DM_ALLOWED_USERS="666327013924069283,076765530923422118,081323311123422118"' in source
    assert 'configure_hermes_dingtalk_access()' in source
    assert 'extra["dm_allowed_users"] = dm_allowed_users' in source
    assert 'extra["require_mention"] = True' in source
    assert 'extra["allowed_chats"] = []' in source
    assert 'extra["free_response_chats"] = []' in source
    assert 'HERMES_CONFIG_BACKUP="$(backup_env_file "$HERMES_CONFIG_FILE")"' in source
    assert 'restore_env_backup "$HERMES_CONFIG_FILE" "$HERMES_CONFIG_BACKUP"' in source
    assert 'HERMES_DM_ALLOWED_USERS_MATCH=' in source
    assert 'HERMES_GROUP_REQUIRE_MENTION=' in source
    assert 'HERMES_GROUP_SCOPE=' in source
    assert 'all_application_groups' in source
    assert 'upsert_env_value "$HERMES_ENV_FILE" "HERMES_LANGUAGE" "zh"' in apply_body
    assert 'upsert_env_value "$HERMES_ENV_FILE" "XINTAI_SOUL_SYNC_ENABLED" "true"' in apply_body
    assert 'upsert_env_value "$HERMES_ENV_FILE" "XINTAI_EVIDENCE_RELAY_ENABLED" "true"' in apply_body
    assert 'DINGTALK_STREAM_CONFIGURATION_APPLIED=yes' in apply_body
    assert 'echo "$stream_app_key"' not in apply_body
    assert 'echo "$stream_app_secret"' not in apply_body

    trap_index = source.find("trap 'rc=$?; if [ \"$rc\" -ne 0 ]; then rollback_on_error \"$rc\"; fi' EXIT")
    stop_index = source.find('stop_hermes_gateway', trap_index)
    apply_index = source.find('apply_dingtalk_stream_config', stop_index)
    restart_index = source.find('systemctl restart aluminum-bypass', apply_index)
    assert -1 not in (trap_index, stop_index, apply_index, restart_index)
    assert trap_index < stop_index < apply_index < restart_index
    assert 'if [ "$MODE" = "deploy" ]; then\n            apply_dingtalk_stream_config\n          fi' in source


def test_production_sync_stream_config_applier_writes_expected_values_without_logging_secrets(tmp_path: Path) -> None:
    bash = _require_bash()
    source = _read('.github/workflows/production-sync-status.yml')
    app_key = 'test-app-key'
    app_secret = 'test-app-secret'
    relay_token = 'existing-relay-token'

    def encoded(value: str) -> str:
        return base64.b64encode(value.encode('utf-8')).decode('ascii')

    script_path = tmp_path / 'apply-stream-config.sh'
    datahub_env = tmp_path / 'datahub.env'
    hermes_env = tmp_path / 'hermes.env'
    datahub_env.write_text(f'HERMES_DINGTALK_STREAM_RELAY_TOKEN={relay_token}\n', encoding='utf-8')
    hermes_env.write_text('', encoding='utf-8')
    script_path.write_text(
        '\n'.join(
            [
                '#!/usr/bin/env bash',
                'set -euo pipefail',
                'DATAHUB_ENV_FILE=datahub.env',
                'HERMES_ENV_FILE=hermes.env',
                f'STREAM_APP_KEY_B64={encoded(app_key)}',
                f'STREAM_APP_SECRET_B64={encoded(app_secret)}',
                f'STREAM_ROBOT_CODE_B64={encoded(app_key)}',
                f'STREAM_AGENT_ID_B64={encoded("4689391809")}',
                f'STREAM_APP_ID_B64={encoded("test-app-id")}',
                textwrap.dedent(_extract_shell_function(source, 'read_env_value')),
                textwrap.dedent(_extract_shell_function(source, 'decode_b64')),
                'upsert_env_value() {',
                '  local file="$1" key="$2" value="$3"',
                '  if grep -q "^${key}=" "$file"; then',
                '    sed -i "s|^${key}=.*|${key}=${value}|" "$file"',
                '  else',
                '    printf "%s=%s\\n" "$key" "$value" >> "$file"',
                '  fi',
                '}',
                'configure_hermes_dingtalk_access() { :; }',
                textwrap.dedent(_extract_shell_function(source, 'apply_dingtalk_stream_config')),
                'apply_dingtalk_stream_config',
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
        cwd=tmp_path,
        timeout=15,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'DINGTALK_STREAM_CONFIGURATION_APPLIED=yes' in result.stdout
    assert app_key not in result.stdout
    assert app_secret not in result.stdout
    datahub_values = datahub_env.read_text(encoding='utf-8')
    hermes_values = hermes_env.read_text(encoding='utf-8')
    assert 'DINGTALK_AUTHORIZED_GROUP_IDS=*' in datahub_values
    assert f'DINGTALK_APP_KEY={app_key}' in datahub_values
    assert f'DINGTALK_CLIENT_SECRET={app_secret}' in hermes_values
    assert 'DINGTALK_ALLOWED_USERS=*' in hermes_values
    assert 'DINGTALK_ALLOWED_CHATS=' in hermes_values
    assert 'DINGTALK_FREE_RESPONSE_CHATS=' in hermes_values
    assert 'DINGTALK_REQUIRE_MENTION=true' in hermes_values
    assert 'HERMES_LANGUAGE=zh' in hermes_values
    assert f'XINTAI_DINGTALK_STREAM_RELAY_TOKEN={relay_token}' in hermes_values


def test_production_sync_status_reports_hermes_runtime_without_exposing_process_arguments() -> None:
    source = _read('.github/workflows/production-sync-status.yml')
    report_body = _extract_shell_function(source, 'report_hermes_runtime')

    assert 'systemctl show -p MainPID --value hermes-gateway' in report_body
    assert 'readlink -f "/proc/$runtime_pid/exe"' not in report_body
    assert 'resolve_hermes_runtime_python "$runtime_pid"' in report_body
    assert 'args.index("-m", 1)' in report_body
    assert 'HERMES_RUNTIME_PYTHON=' in report_body
    assert 'HERMES_RUNTIME_PYTHON_VERSION=' in report_body
    assert 'HERMES_RUNTIME_PREFIX=' in report_body
    assert 'HERMES_RUNTIME_BASE_PREFIX=' in report_body
    assert 'HERMES_RUNTIME_IS_VENV=' in report_body
    assert 'HERMES_RUNTIME_PACKAGE_VERSION=' in report_body
    assert 'HERMES_RUNTIME_DINGTALK_STREAM_VERSION=' in report_body
    assert 'HERMES_RUNTIME_ENTRYPOINT=' in report_body
    assert 'HERMES_RUNTIME_CWD=' in report_body
    assert 'HERMES_SERVICE_FRAGMENT_PATH=' in report_body
    assert 'HERMES_SERVICE_USER=' in report_body
    assert 'HERMES_SERVICE_WORKING_DIRECTORY=' in report_body
    assert 'HERMES_HOST_OS_ID=' in report_body
    assert 'HERMES_HOST_OS_VERSION_ID=' in report_body
    assert 'HERMES_HOST_UV=' in report_body
    assert 'HERMES_HOST_PYTHON_3_11=' in report_body
    assert 'HERMES_HOST_PYTHON_3_12=' in report_body
    assert '/proc/{runtime_pid}/cmdline' in report_body
    assert 'HERMES_RUNTIME_ARGV' not in report_body
    report_status_body = _extract_shell_function(source, 'report_status')
    assert 'report_hermes_runtime' in report_status_body
    assert 'capture_hermes_gateway_command_contract' in report_status_body
    assert 'HERMES_GATEWAY_DEPLOY_CONTRACT=ready' in report_status_body
    assert 'HERMES_GATEWAY_DEPLOY_CONTRACT=rejected' in report_status_body


def test_production_status_exposes_daily_report_contract_gate_without_breaking_old_rollback() -> None:
    source = _read('.github/workflows/production-sync-status.yml')
    report_status_body = _extract_shell_function(source, 'report_status')

    assert 'backend/scripts/check_daily_report_field_contract.py' in report_status_body
    assert 'scripts/check_daily_report_field_contract.py --json' in report_status_body
    assert 'DAILY_REPORT_FIELD_CONTRACT_GATE_START' in report_status_body
    assert 'DAILY_REPORT_FIELD_CONTRACT_GATE_END' in report_status_body
    assert 'DAILY_REPORT_FIELD_CONTRACT_GATE=not_available_for_sha' in report_status_body


def test_production_sync_status_builds_reversible_isolated_hermes_runtime() -> None:
    source = _read('.github/workflows/production-sync-status.yml')
    deployment = source[source.find('RAW_DATABASE_URL="$(read_env_value DATABASE_URL "$DATAHUB_ENV_FILE")"'):]

    assert 'install_managed_uv()' in source
    assert 'prepare_hermes_runtime()' in source
    assert 'backup_hermes_runtime_dropin()' in source
    assert 'restore_hermes_runtime_dropin()' in source
    assert 'write_hermes_runtime_dropin()' in source
    assert 'HERMES_MANAGED_UV="$HERMES_HOME/bin/uv"' in source
    assert 'HERMES_UV_VERSION="0.11.28"' in source
    assert 'UV_PYTHON_INSTALL_DIR=/usr/local/share/uv/python' in source
    assert 'UV_PYTHON_BIN_DIR=/usr/local/share/uv/bin' in source
    assert 'uv-x86_64-unknown-linux-gnu.tar.gz' in source
    assert 'e490a6464492183c5d4534a5527fb4440f7f2bb2f228162ad7e4afe076dc0224' in source
    assert 'uv-aarch64-unknown-linux-gnu.tar.gz' in source
    assert '03e9fe0a81b0718d0bc84625de3885df6cc3f89a8b6af6121d6b9f6113fb6533' in source
    assert 'https://github.com/astral-sh/uv/releases/download/$HERMES_UV_VERSION/$uv_asset' in source
    assert 'sha256sum -c -' in source
    assert 'https://astral.sh/uv/install.sh' not in source
    assert 'python install 3.11' in source
    assert 'venv "$release_env" --python 3.11' in source
    assert 'UV_PROJECT_ENVIRONMENT="$release_env"' in source
    assert 'sync --locked --extra dingtalk --no-editable' in source
    assert 'git -C "$HERMES_REPO" archive "$target_sha"' in source
    assert 'cd "$build_source"' in source
    assert 'HERMES_RUNTIME_ENV_ROOT="$HERMES_HOME/runtime-envs"' in source
    assert 'release_env="$HERMES_RUNTIME_ENV_ROOT/$target_sha"' in source
    assert 'capture_hermes_gateway_command_contract()' in source
    assert 'ExecStart=$runtime_python -P $HERMES_GATEWAY_ARGS' in source
    writer_body = _extract_shell_function(source, 'write_hermes_runtime_dropin')
    assert 'ExecStopPost' not in writer_body
    assert 'WorkingDirectory=' not in writer_body
    assert 'HERMES_TARGET_PACKAGE_OUTSIDE_RUNTIME' in source
    assert 'HERMES_DEPENDENCY_SYNC_SKIPPED' not in source

    capture_index = deployment.find('capture_hermes_gateway_command_contract')
    prepare_index = deployment.find('prepare_hermes_runtime "$HERMES_SHA"')
    backup_index = deployment.find('backup_hermes_runtime_dropin')
    trap_index = deployment.find("trap 'rc=$?; if [ \"$rc\" -ne 0 ]; then rollback_on_error \"$rc\"; fi' EXIT")
    stop_index = deployment.find('stop_hermes_gateway')
    checkout_index = deployment.find('git -C "$HERMES_REPO" checkout --detach "$HERMES_SHA"')
    switch_index = deployment.find('write_hermes_runtime_dropin "$HERMES_TARGET_RUNTIME_ENV"')
    restart_index = deployment.find('systemctl start hermes-gateway')
    assert -1 not in (capture_index, prepare_index, trap_index, backup_index, stop_index, checkout_index, switch_index, restart_index)
    assert capture_index < prepare_index < backup_index < trap_index < stop_index < checkout_index < switch_index < restart_index


def test_production_status_reports_managed_uv_state_without_secret_material() -> None:
    source = _read('.github/workflows/production-sync-status.yml')
    report_body = _extract_shell_function(source, 'report_status')
    uv_report_body = _extract_shell_function(source, 'report_managed_uv_state')
    install_body = _extract_shell_function(source, 'install_managed_uv')

    assert 'report_managed_uv_state' in report_body
    assert 'HERMES_MANAGED_UV_STATE=' in uv_report_body
    assert 'HERMES_MANAGED_UV_VERSION=' in uv_report_body
    assert 'HERMES_MANAGED_UV_FAILURE_REASON=' in uv_report_body
    assert 'HERMES_UV_ARCHIVE_RESIDUE_COUNT=' in uv_report_body
    assert 'HERMES_UV_EXTRACT_RESIDUE_COUNT=' in uv_report_body
    assert install_body.count('read_managed_uv_version') >= 2
    assert 'cat ' not in uv_report_body
    assert 'systemctl show -p Environment' not in uv_report_body


def test_managed_uv_report_executes_all_states_under_strict_bash() -> None:
    bash = _require_bash()
    source = _read('.github/workflows/production-sync-status.yml')
    parser_body = textwrap.dedent(_extract_shell_function(source, 'read_managed_uv_version'))
    install_body = textwrap.dedent(_extract_shell_function(source, 'install_managed_uv'))
    report_body = textwrap.dedent(_extract_shell_function(source, 'report_managed_uv_state'))
    tmp_root = Path(tempfile.mkdtemp(prefix='managed-uv-report-', dir=REPO_ROOT))
    script_path = tmp_root / 'harness.sh'
    try:
        script_path.write_text(
            "\n".join(
                [
                    '#!/usr/bin/env bash',
                    'set -euo pipefail',
                    'HERMES_UV_VERSION=0.11.28',
                    parser_body,
                    install_body,
                    report_body,
                    'HERMES_MANAGED_UV="$PWD/missing-uv"',
                    'report_managed_uv_state > missing.out',
                    'printf "not executable\\n" > "$PWD/fake-uv"',
                    'chmod 644 "$PWD/fake-uv"',
                    'HERMES_MANAGED_UV="$PWD/fake-uv"',
                    'report_managed_uv_state > not-executable.out',
                    'printf "#!/usr/bin/env bash\\nprintf \'token=must-not-leak\\n\' >&2\\nexit 42\\n" > "$PWD/fake-uv"',
                    'chmod 755 "$PWD/fake-uv"',
                    'report_managed_uv_state > execution-failed.out',
                    'if install_managed_uv > install-execution-failed.out; then exit 1; fi',
                    'printf "#!/usr/bin/env bash\\nprintf \'uv token=must-not-leak\\n\'\\n" > "$PWD/fake-uv"',
                    'report_managed_uv_state > unreadable.out',
                    'printf "#!/usr/bin/env bash\\nprintf \'uv 0.11.27 (x86_64-unknown-linux-gnu)\\n\'\\n" > "$PWD/fake-uv"',
                    'report_managed_uv_state > mismatch.out',
                    'if install_managed_uv > install-mismatch.out; then exit 1; fi',
                    'printf "#!/usr/bin/env bash\\nprintf \'uv 0.11.28 (x86_64-unknown-linux-gnu)\\n\'\\n" > "$PWD/fake-uv"',
                    'report_managed_uv_state > ready.out',
                    'install_managed_uv > install.out',
                    'grep -Fq "HERMES_MANAGED_UV_STATE=missing" missing.out',
                    'grep -Fq "HERMES_MANAGED_UV_STATE=not_executable" not-executable.out',
                    'grep -Fq "HERMES_MANAGED_UV_STATE=execution_failed" execution-failed.out',
                    'grep -Fq "HERMES_MANAGED_UV_FAILURE_REASON=exit_code_42" execution-failed.out',
                    'grep -Fq "HERMES_MANAGED_UV_INVALID=exit_code_42" install-execution-failed.out',
                    'grep -Fq "HERMES_MANAGED_UV_STATE=version_unreadable" unreadable.out',
                    'grep -Fq "HERMES_MANAGED_UV_FAILURE_REASON=invalid_version_output" unreadable.out',
                    '! grep -Fq "must-not-leak" execution-failed.out install-execution-failed.out unreadable.out',
                    'grep -Fq "HERMES_MANAGED_UV_STATE=version_mismatch" mismatch.out',
                    'grep -Fq "HERMES_MANAGED_UV_VERSION=0.11.27" mismatch.out',
                    'grep -Fq "HERMES_MANAGED_UV_VERSION_MISMATCH=expected_0.11.28_actual_0.11.27" install-mismatch.out',
                    'grep -Fq "HERMES_MANAGED_UV_STATE=ready" ready.out',
                    'grep -Fq "HERMES_MANAGED_UV_VERSION=0.11.28" ready.out',
                    'grep -Fq "HERMES_MANAGED_UV_VERSION=0.11.28" install.out',
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
            timeout=15,
        )
    finally:
        _remove_test_tree(tmp_root)

    assert result.returncode == 0, result.stdout + result.stderr


def test_hermes_runtime_switch_rejects_unknown_gateway_command_shapes() -> None:
    source = _read('.github/workflows/production-sync-status.yml')
    capture_body = _extract_shell_function(source, 'capture_hermes_gateway_command_contract')

    assert 'local attempts="${1:-5}"' in capture_body
    assert 'local delay_seconds="${2:-1}"' in capture_body
    assert 'for attempt in $(seq 1 "$attempts")' in capture_body
    assert 'HERMES_GATEWAY_COMMAND_ATTEMPT=' in capture_body
    assert 'sleep "$delay_seconds"' in capture_body
    assert (
        'command_args = service_runtime_args[1:] if service_runtime_args[:1] == ["-P"] else service_runtime_args'
        in capture_body
    )
    assert 'if command_args[-1:] == ["--replace"]:' in capture_body
    assert 'command_args = command_args[:-1]' in capture_body
    assert 'command_args == ["-m", "hermes_cli.main", "gateway", "run"]' in capture_body
    assert 'command_args[:3] == ["-m", "hermes_cli.main", "-p"]' in capture_body
    assert 'command_args[4:] == ["gateway", "run"]' in capture_body
    assert 're.fullmatch(r"[A-Za-z0-9_.-]+", command_args[3])' in capture_body
    assert 'def classify_service_arg(value: str) -> str:' in capture_body
    assert '"hermes_module"' in capture_body
    assert '"--replace": "legacy_replace_flag"' in capture_body
    assert '"safe_name"' in capture_body
    assert 'unexpected Hermes gateway command shape:service_argc=' in capture_body
    assert ':service_classes=' in capture_body
    assert 'systemctl", "show", "-p", "ExecStart", "--value", "hermes-gateway"' in capture_body
    assert 'systemctl", "show", "-p", "MainPID", "--value", "hermes-gateway"' in capture_body
    assert 'Hermes gateway MainPID changed during verification' in capture_body
    assert 'service_exec.count("argv[]=") != 1' in capture_body
    assert 'runtime_argv not in (service_args, ["hermes"])' in capture_body
    assert 'Hermes running process has an unexpected title' in capture_body
    assert 'service_args[1:] != args' not in capture_body
    assert 'service_path != Path(runtime_executable).resolve()' in capture_body
    assert 'runtime_executable = str(Path(f"/proc/{runtime_pid}/exe").resolve())' in capture_body
    assert 'command_args = args[1:] if args[:1] == ["-P"] else args' not in capture_body
    assert 'unexpected Hermes gateway command shape' in capture_body
    assert 'HERMES_GATEWAY_ARGS=' in capture_body


def test_hermes_gateway_verifier_executes_title_command_and_redaction_contracts() -> None:
    verifier_source = _extract_hermes_gateway_verifier(
        _read('.github/workflows/production-sync-status.yml')
    )
    namespace = {'__name__': 'hermes_gateway_verifier_test'}
    exec(compile(verifier_source, '<hermes-gateway-verifier>', 'exec'), namespace)
    verify = namespace['verify_gateway_command_contract']

    executable = '/opt/hermes/python3.11'

    def service_exec(*args: str) -> str:
        joined = ' '.join((executable, *args))
        return f'path={executable} ; argv[]={joined} ; ignore_errors=no ;'

    canonical = ('-m', 'hermes_cli.main', 'gateway', 'run')
    full_argv = [executable, *canonical]
    assert verify('4242', service_exec(*canonical), '4242', executable, full_argv) == ' '.join(canonical)

    legacy = (*canonical, '--replace')
    assert verify('4242', service_exec(*legacy), '4242', executable, ['hermes']) == ' '.join(canonical)

    profiled = ('-P', '-m', 'hermes_cli.main', '-p', 'factory', 'gateway', 'run', '--replace')
    assert verify('4242', service_exec(*profiled), '4242', executable, ['hermes']) == (
        '-m hermes_cli.main -p factory gateway run'
    )

    with pytest.raises(SystemExit, match='Hermes running process has an unexpected title'):
        verify('4242', service_exec(*canonical), '4242', executable, ['hermes', 'gateway'])

    sensitive_option = '--api-token=must-not-leak'
    with pytest.raises(SystemExit) as command_error:
        verify(
            '4242',
            service_exec(*canonical, sensitive_option),
            '4242',
            executable,
            ['hermes'],
        )
    assert 'unexpected Hermes gateway command shape' in str(command_error.value)
    assert sensitive_option not in str(command_error.value)

    bad_profile = 'factory:secret'
    with pytest.raises(SystemExit) as profile_error:
        verify(
            '4242',
            service_exec('-m', 'hermes_cli.main', '-p', bad_profile, 'gateway', 'run'),
            '4242',
            executable,
            ['hermes'],
        )
    assert bad_profile not in str(profile_error.value)

    with pytest.raises(SystemExit, match='MainPID changed'):
        verify('4242', service_exec(*canonical), '4343', executable, ['hermes'])
    with pytest.raises(SystemExit, match='wrapper commands are unsupported'):
        verify('4242', service_exec(*canonical), '4242', '/opt/hermes/other-python', ['hermes'])


def test_hermes_gateway_command_contract_retries_transient_pid_and_rejects_persistent_failure(tmp_path: Path) -> None:
    bash = _require_bash()
    source = _read('.github/workflows/production-sync-status.yml')
    capture_body = textwrap.dedent(_extract_shell_function(source, 'capture_hermes_gateway_command_contract'))
    script_path = tmp_path / 'gateway-contract-retry.sh'
    script_path.write_text(
        "\n".join(
            [
                '#!/usr/bin/env bash',
                'set -euo pipefail',
                'SCENARIO=""',
                'SYSTEMCTL_COUNT_FILE="$PWD/systemctl-count"',
                'systemctl() {',
                '  local count',
                '  count="$(cat "$SYSTEMCTL_COUNT_FILE")"',
                '  count=$((count + 1))',
                '  printf "%s\\n" "$count" > "$SYSTEMCTL_COUNT_FILE"',
                '  if { [ "$SCENARIO" = "transient" ] && [ "$count" -gt 1 ]; } || [ "$SCENARIO" = "verifier" ]; then',
                '    printf "4242\\n"',
                '  else',
                '    printf "0\\n"',
                '  fi',
                '}',
                'python3() {',
                '  cat >/dev/null',
                '  if [ "$SCENARIO" = "verifier" ]; then',
                '    printf "%s\\n" "unexpected Hermes gateway command shape:service_argc=2:service_classes=option,opaque" >&2',
                '    return 1',
                '  fi',
                '  printf "%s\\n" "-m hermes_cli.main gateway run"',
                '}',
                capture_body,
                'printf "0\\n" > "$SYSTEMCTL_COUNT_FILE"',
                'SCENARIO="transient"',
                'capture_hermes_gateway_command_contract 2 0 > transient.out',
                '[ "$HERMES_GATEWAY_ARGS" = "-m hermes_cli.main gateway run" ]',
                'grep -Fq "HERMES_GATEWAY_COMMAND_ATTEMPT=1/2:main_pid_unavailable" transient.out',
                'grep -Fq "HERMES_GATEWAY_COMMAND_ATTEMPT=2/2:accepted" transient.out',
                'grep -Fq "HERMES_GATEWAY_COMMAND_CONTRACT=accepted" transient.out',
                'printf "0\\n" > "$SYSTEMCTL_COUNT_FILE"',
                'SCENARIO="persistent"',
                'HERMES_GATEWAY_ARGS="stale"',
                'set +e',
                'capture_hermes_gateway_command_contract 2 0 > persistent.out',
                'persistent_rc="$?"',
                'set -e',
                '[ "$persistent_rc" -ne 0 ]',
                '[ -z "$HERMES_GATEWAY_ARGS" ]',
                'grep -Fq "HERMES_GATEWAY_COMMAND_ATTEMPT=1/2:main_pid_unavailable" persistent.out',
                'grep -Fq "HERMES_GATEWAY_COMMAND_ATTEMPT=2/2:main_pid_unavailable" persistent.out',
                'grep -Fq "HERMES_GATEWAY_COMMAND_ERROR=main_pid_unavailable" persistent.out',
                'grep -Fq "HERMES_GATEWAY_COMMAND_CONTRACT=rejected" persistent.out',
                'printf "0\\n" > "$SYSTEMCTL_COUNT_FILE"',
                'SCENARIO="verifier"',
                'set +e',
                'capture_hermes_gateway_command_contract 1 0 > verifier.out',
                'verifier_rc="$?"',
                'set -e',
                '[ "$verifier_rc" -ne 0 ]',
                'grep -Fq "HERMES_GATEWAY_COMMAND_ATTEMPT=1/1:rejected" verifier.out',
                'grep -Fq "HERMES_GATEWAY_COMMAND_ERROR=unexpected Hermes gateway command shape:service_argc=2:service_classes=option,opaque" verifier.out',
                'grep -Fq "HERMES_GATEWAY_COMMAND_CONTRACT=rejected" verifier.out',
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
        cwd=tmp_path,
        timeout=15,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_hermes_runtime_dropin_switch_and_restore_preserve_previous_service_command() -> None:
    bash = _require_bash()
    source = _read('.github/workflows/production-sync-status.yml')
    function_bodies = [
        textwrap.dedent(_extract_shell_function(source, name))
        for name in (
            'backup_hermes_runtime_dropin',
            'restore_hermes_runtime_dropin',
            'write_hermes_runtime_dropin',
        )
    ]
    tmp_root = Path(tempfile.mkdtemp(prefix='runtime-dropin-', dir=REPO_ROOT))
    target_sha = 'a' * 40
    script_path = tmp_root / 'harness.sh'
    try:
        script_path.write_text(
            "\n".join(
                [
                    '#!/usr/bin/env bash',
                    'set -euo pipefail',
                    'HERMES_HOME="$PWD/hermes-home"',
                    'HERMES_RUNTIME_ENV_ROOT="$PWD/runtime-envs"',
                    'HERMES_RUNTIME_DROPIN_DIR="$PWD/dropin"',
                    'HERMES_RUNTIME_DROPIN_FILE="$HERMES_RUNTIME_DROPIN_DIR/10-xintai-runtime.conf"',
                    'HERMES_RUNTIME_DROPIN_BACKUP=',
                    'HERMES_RUNTIME_DROPIN_EXISTED=0',
                    'HERMES_GATEWAY_ARGS="-m hermes_cli.main gateway run"',
                    f'release_env="$HERMES_RUNTIME_ENV_ROOT/{target_sha}"',
                    'mkdir -p "$release_env/bin" "$HERMES_RUNTIME_DROPIN_DIR"',
                    'printf "#!/usr/bin/env bash\\n" > "$release_env/bin/python"',
                    'chmod +x "$release_env/bin/python"',
                    'printf "[Service]\\nExecStart=/usr/bin/python3.10 -m hermes_cli.main gateway run\\nExecStopPost=-/bin/true\\nEnvironment=KEEP_ME=yes\\n" > "$HERMES_RUNTIME_DROPIN_FILE"',
                    'systemctl() { printf "systemctl:%s\\n" "$*"; }',
                    *function_bodies,
                    'backup_hermes_runtime_dropin',
                    'write_hermes_runtime_dropin "$release_env"',
                    'cp "$HERMES_RUNTIME_DROPIN_FILE" switched.conf',
                    'restore_hermes_runtime_dropin',
                    'cp "$HERMES_RUNTIME_DROPIN_FILE" restored.conf',
                    'test -z "$HERMES_RUNTIME_DROPIN_BACKUP"',
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
            timeout=15,
        )
        switched = (tmp_root / 'switched.conf').read_text(encoding='utf-8')
        restored = (tmp_root / 'restored.conf').read_text(encoding='utf-8')
    finally:
        _remove_test_tree(tmp_root)

    assert result.returncode == 0, result.stderr
    normalized_switched = switched.replace('\\', '/')
    assert f'/runtime-envs/{target_sha}/bin/python -P -m hermes_cli.main gateway run' in normalized_switched
    assert 'ExecStopPost' not in switched
    assert restored == '[Service]\nExecStart=/usr/bin/python3.10 -m hermes_cli.main gateway run\nExecStopPost=-/bin/true\nEnvironment=KEEP_ME=yes\n'
    assert result.stdout.count('systemctl:daemon-reload') == 2


def test_configure_dingtalk_stream_prod_workflow_targets_real_gateway_contract() -> None:
    payload = _load('.github/workflows/configure-dingtalk-stream-prod.yml')
    source = _read('.github/workflows/configure-dingtalk-stream-prod.yml')
    inputs = _workflow_inputs(payload)
    concurrency = _workflow_concurrency(payload)

    assert concurrency == {
        'group': 'xintai-production-ops',
        'cancel-in-progress': False,
    }
    assert 'authorized_group_ids' not in inputs
    assert inputs['acceptance_marker']['required'] is False
    assert inputs['acceptance_since']['required'] is False
    assert inputs['min_text']['default'] == '10'
    assert inputs['min_files']['default'] == '5'
    assert inputs['expected_u1_sha256']['required'] is False
    assert inputs['expected_u2_sha256']['required'] is False
    assert inputs['expected_hermes_sha']['required'] is False
    assert "backend/scripts/hermes_dingtalk_stream_gateway.py --health" not in source
    assert 'rollback_on_apply_error()' in source
    assert "trap 'rc=$?; if [ \"$rc\" -ne 0 ]; then rollback_on_apply_error \"$rc\"; fi' EXIT" in source
    assert 'trap - EXIT' in source
    assert 'append_remote_assignment()' in source
    assert 'printf -v REMOTE_PREAMBLE' in source
    assert 'AUTHORIZED_GROUP_IDS: ${{ github.event.inputs.authorized_group_ids }}' not in source
    assert 'upsert_env_value "$HERMES_ENV_FILE" "DINGTALK_ALLOWED_CHATS" ""' in source
    assert 'upsert_env_value "$HERMES_ENV_FILE" "DINGTALK_FREE_RESPONSE_CHATS" ""' in source
    assert 'upsert_env_value "$HERMES_ENV_FILE" "DINGTALK_ALLOWED_USERS" "*"' in source
    assert 'HERMES_DM_ALLOWED_USERS="666327013924069283,076765530923422118,081323311123422118"' in source
    assert 'configure_hermes_dingtalk_access()' in source
    assert 'extra["dm_allowed_users"] = dm_allowed_users' in source
    assert 'extra["require_mention"] = True' in source
    assert 'extra["allowed_chats"] = []' in source
    assert 'extra["free_response_chats"] = []' in source
    assert 'upsert_env_value "$HERMES_ENV_FILE" "DINGTALK_REQUIRE_MENTION" "false"' not in source
    assert 'hermes_config_backup="$(backup_env_file "$HERMES_CONFIG_FILE" hermes.config)"' in source
    assert 'restore_env_backup "$HERMES_CONFIG_FILE" "$hermes_config_backup" hermes_config' in source
    assert 'HERMES_DM_ALLOWED_USERS_MATCH=' in source
    assert 'HERMES_GROUP_REQUIRE_MENTION=' in source
    assert 'HERMES_GROUP_SCOPE=' in source
    assert 'all_application_groups' in source
    assert '^XT-P1-[A-Za-z0-9][A-Za-z0-9._-]{7,120}$' in source
    assert '^[0-9]{4}-[0-9]{2}-[0-9]{2}T' in source
    assert '^[0-9a-f]{64}$' in source
    assert '^[0-9a-f]{40}$' in source
    assert 'append_remote_assignment ACCEPTANCE_MARKER_B64' in source
    assert 'append_remote_assignment ACCEPTANCE_SINCE_B64' in source
    assert 'append_remote_assignment MIN_TEXT_B64' in source
    assert 'append_remote_assignment MIN_FILES_B64' in source
    assert 'append_remote_assignment EXPECTED_U1_SHA256_B64' in source
    assert 'append_remote_assignment EXPECTED_U2_SHA256_B64' in source
    assert 'append_remote_assignment EXPECTED_HERMES_SHA_B64' in source
    assert '} | ssh -i ~/.ssh/deploy_key -p "$SSH_PORT" -o StrictHostKeyChecking=yes -o UserKnownHostsFile=~/.ssh/known_hosts "$SSH_USER@$SSH_HOST" "bash -s"' in source
    assert """MODE='$MODE'""" not in source
    ssh_launch_index = source.find('} | ssh -i ~/.ssh/deploy_key -p "$SSH_PORT" -o StrictHostKeyChecking=yes -o UserKnownHostsFile=~/.ssh/known_hosts "$SSH_USER@$SSH_HOST" "bash -s"')
    assert ssh_launch_index != -1
    assert 'STREAM_APP_KEY_B64' not in source[ssh_launch_index:ssh_launch_index + 200]
    assert 'STREAM_APP_SECRET_B64' not in source[ssh_launch_index:ssh_launch_index + 200]
    apply_trap_index = source.find("trap 'rc=$?; if [ \"$rc\" -ne 0 ]; then rollback_on_apply_error \"$rc\"; fi' EXIT")
    first_mutation_index = source.find('upsert_env_value "$DATAHUB_ENV_FILE" "DINGTALK_STREAM_ENABLED" "true"')
    assert -1 not in (apply_trap_index, first_mutation_index)
    assert apply_trap_index < first_mutation_index
    assert 'upsert_env_value "$DATAHUB_ENV_FILE" "DINGTALK_AUTHORIZED_GROUP_IDS" "*"' in source
    assert 'restart_hermes_gateway' in source
    assert '/readyz' in source
    assert 'systemctl show -p ActiveEnterTimestamp' in source
    assert 'systemctl show -p MainPID' in source
    assert 'gateway_state.json' in source
    assert 'stream_runtime_state_is_connected' in source
    assert "grep -F 'Connected via Stream Mode'" not in source
    assert 'multimodal_evidence' in source
    assert 'chat_inbox' in source
    assert 'external_message_logs' in source
    assert 'dingtalk_inbound_receipts' in source
    assert 'agent_runs' in source
    assert 'agent_outbox_messages' in source
    assert "source_payload->>'source_transport' = 'dingtalk_stream'" in source
    assert "payload->>'source_transport' = 'dingtalk_stream'" in source
    assert "LIKE 'dingtalk-stream-sha256:%'" not in source
    assert "- verify" in source
    assert 'perform_apply_preflight()' in source
    assert 'scan_secret_exposure()' in source
    assert 'run_acceptance_gate()' in source
    assert 'verify_duplicate_replay()' in source
    assert 'verify_fresh_stream_evidence()' not in source
    assert 'report_stream_connection "yes" 40 3' in source
    assert 'DATAHUB_STREAM_RELAY_TOKEN_PRESENT=' in source
    assert 'HERMES_STREAM_RELAY_TOKEN_PRESENT=' in source
    assert 'run_acceptance_gate PRE' in source
    assert 'run_acceptance_gate POST' in source
    assert 'scan_secret_exposure PRE_APPLY' in source or 'scan_secret_exposure POST_APPLY' in source
    assert 'scan_secret_exposure POST_VERIFY' in source
    assert 'VERIFY_EVENT_AFTER_RESTART=WAITING' in source
    assert 'VERIFY_EVENT_AFTER_RESTART=FOUND' in source
    rollback_body = _extract_shell_function(source, 'rollback_on_apply_error')
    assert 'APPLY_FAILED_ROLLBACK_START' in rollback_body
    assert 'APPLY_FAILED_ROLLBACK_DONE' in rollback_body
    assert 'APPLY_FAILED_ROLLBACK_INCOMPLETE' in rollback_body
    assert 'ROLLBACK_FAILED_DATAHUB_ENV' in rollback_body
    assert 'ROLLBACK_FAILED_HERMES_ENV' in rollback_body
    assert 'ROLLBACK_FAILED_READYZ' in rollback_body


def test_configure_dingtalk_stream_prod_scoped_gate_scan_and_replay_contracts() -> None:
    source = _read('.github/workflows/configure-dingtalk-stream-prod.yml')
    backup_body = _extract_shell_function(source, 'backup_postgres_database')
    preflight_body = _extract_shell_function(source, 'perform_apply_preflight')
    gate_body = _extract_shell_function(source, 'run_acceptance_gate')
    secret_scan_body = _extract_shell_function(source, 'scan_secret_exposure')
    replay_body = _extract_shell_function(source, 'verify_duplicate_replay')

    assert '"--format=custom"' in backup_body
    assert '"-l"' in backup_body
    assert 'subprocess.run(pg_dump_argv' in backup_body
    assert 'subprocess.run(pg_restore_argv' in backup_body
    assert 'backup_postgres_database "$raw_database_url" "$db_backup"' in preflight_body
    assert 'test -s "$db_backup"' in preflight_body
    assert 'backup_env_file "$DATAHUB_ENV_FILE" datahub.env' in preflight_body
    assert 'backup_env_file "$HERMES_ENV_FILE" hermes.env' in preflight_body
    assert '"PGPASSFILE": str(pgpass_path)' in backup_body
    assert 'env.pop("PGPASSWORD", None)' in backup_body
    assert 'env.pop("DATABASE_URL", None)' in backup_body
    assert 'pgpass_path.unlink(missing_ok=True)' in backup_body
    assert 'hide_password=False' not in backup_body
    assert 'cp -p "$DATAHUB_ENV_FILE" "$datahub_env_backup"' not in preflight_body
    assert 'cp -p "$HERMES_ENV_FILE" "$hermes_env_backup"' not in preflight_body
    assert 'stat -c %a "$DATAHUB_ENV_FILE"' in preflight_body
    assert 'stat -c %a "$datahub_env_backup"' in preflight_body
    assert 'stat -c %a "$HERMES_ENV_FILE"' in preflight_body
    assert 'stat -c %a "$hermes_env_backup"' in preflight_body
    assert 'xintai_callback_proof_ledger.json' in gate_body
    assert 'temp_dir="$(mktemp -d)"' in gate_body
    assert 'chmod 700 "$temp_dir"' in gate_body
    assert 'install -m 600 "$ledger_source" "$ledger_copy"' in gate_body
    assert 'trap cleanup_acceptance_gate RETURN' in gate_body
    assert 'check_dingtalk_stream_evidence_gate.py' in gate_body
    assert '--marker "$acceptance_marker"' in gate_body
    assert '--min-text "$min_text"' in gate_body
    assert '--min-files "$min_files"' in gate_body
    assert '--since "$acceptance_since"' in gate_body
    assert '--expected-u1-sha256 "$expected_u1_sha256"' in gate_body
    assert '--expected-u2-sha256 "$expected_u2_sha256"' in gate_body
    assert 'raw_database_url="$(read_env_value DATABASE_URL "$DATAHUB_ENV_FILE")"' in gate_body
    assert '[ -n "$raw_database_url" ]' in gate_body
    assert 'if DATABASE_URL="$raw_database_url" "$DATAHUB_REPO/backend/.venv/bin/python"' in gate_body
    assert 'else' in gate_body and 'gate_rc=$?' in gate_body
    assert 'if [ ! -s "$gate_output" ]; then' in gate_body
    assert 'ACCEPTANCE_GATE_OUTPUT=missing' in gate_body
    assert 'rm -rf "$temp_dir"' in gate_body
    assert 'subprocess.run(' in secret_scan_body
    assert "'journalctl'," in secret_scan_body or '"journalctl",' in secret_scan_body
    assert 'SECRET_SCAN_FRONTEND_MATCH=' in secret_scan_body
    assert 'SECRET_SCAN_JOURNAL_MATCH=' in secret_scan_body
    assert 'SECRET_SCAN_SECRET_PRESENT=' in secret_scan_body
    assert '[ -n "$stream_app_secret" ]' in secret_scan_body
    assert 'STREAM_APP_KEY' not in secret_scan_body
    assert 'JOURNAL_BLOB' not in secret_scan_body
    assert 'filename=' not in secret_scan_body
    assert 'downloadCode' not in replay_body
    assert 'message_text' not in replay_body
    assert 'recognized_text' not in replay_body
    assert 'raw_metadata' not in replay_body
    assert 'sessionWebhook' not in replay_body
    assert 'signed_url' not in replay_body
    assert 'umask 077' in replay_body
    assert 'os.umask(0o077)' in replay_body
    assert 'dingtalk_inbound_receipts' in replay_body
    assert 'chat_inbox' in replay_body
    assert 'multimodal_evidence' in replay_body
    assert 'agent_runs' in replay_body
    assert 'agent_outbox_messages' in replay_body
    assert 'external_message_logs' in replay_body
    assert 'download_attempt_delta' in replay_body
    assert 'mktemp' not in replay_body
    assert 'def counts(db, trace_ids):' in replay_body
    assert 'from sqlalchemy import bindparam, create_engine, text' in replay_body
    assert "WHERE trace_id IN :trace_ids" in replay_body
    assert "payload->>'trace_id' IN :trace_ids" in replay_body
    assert 'JOIN agent_outbox_messages' in replay_body
    assert 'outbox_message_id' in replay_body
    assert 'before = counts(db)' not in replay_body
    assert 'SELECT trace_id, channel, group_id, sender_external_id, text' not in replay_body
    assert '"text"' not in replay_body
    assert 'conversationType' in replay_body
    assert 'ingest_dingtalk_stream_event' in replay_body
    assert 'download_robot_message_file' in replay_body
    assert 'file_response = post_payload(file_payload)' in replay_body
    assert "text_response.get(\"status\") == \"duplicate\"" in replay_body
    assert "text_response.get(\"should_reply\") is False" in replay_body
    assert "text_response.get(\"agent_run_id\") is None" in replay_body
    assert "file_response.get(\"status\") == \"duplicate\"" in replay_body
    assert "file_response.get(\"should_reply\") is False" in replay_body
    assert "file_response.get(\"agent_run_id\") is None" in replay_body
    assert "POSITION(:marker IN COALESCE(chat_inbox.text, '')) > 0" in replay_body
    assert 'conversationType": 2 if text_row["channel"] == "dingtalk_group" else 1' in replay_body
    assert 'conversationType": 2 if file_row["channel"] == "dingtalk_group" else 1' in replay_body
    assert "COALESCE(source_payload->>'msgtype', source_payload->>'messageType', 'text')" in replay_body
    assert "COALESCE(payload->>'msgtype', payload->>'messageType', 'file')" in replay_body


def test_configure_dingtalk_restore_env_backup_preserves_protected_replacements_without_secret_leakage(
    tmp_path: Path,
) -> None:
    bash = _require_bash()
    source = _read('.github/workflows/configure-dingtalk-stream-prod.yml')
    restore_body = textwrap.dedent(_extract_shell_function(source, 'restore_env_backup'))

    datahub_env = tmp_path / 'datahub.env'
    datahub_backup = tmp_path / 'datahub.env.bak'
    hermes_env = tmp_path / 'hermes.env'
    hermes_backup = tmp_path / 'hermes.env.bak'
    script_path = tmp_path / 'restore-env.sh'
    replacement_key = 'replacement-app-key'
    replacement_secret = 'replacement-app-secret'
    replacement_relay = 'replacement-relay-token'
    old_key = 'old-app-key'
    old_secret = 'old-app-secret'
    old_relay = 'old-relay-token'
    old_client_id = 'old-client-id'
    old_client_secret = 'old-client-secret'
    old_hermes_relay = 'old-hermes-relay'
    datahub_env.write_text(
        '\n'.join(
            [
                'KEEP_ME=current-datahub',
                'DINGTALK_APP_KEY=current-key',
                'DINGTALK_APP_SECRET=current-secret',
                'HERMES_DINGTALK_STREAM_RELAY_TOKEN=current-relay',
                '',
            ]
        ),
        encoding='utf-8',
    )
    datahub_backup.write_text(
        '\n'.join(
            [
                'KEEP_ME=backup-datahub',
                f'DINGTALK_APP_KEY={old_key}',
                f'DINGTALK_APP_SECRET={old_secret}',
                f'HERMES_DINGTALK_STREAM_RELAY_TOKEN={old_relay}',
                'UNCHANGED_DATAHUB=from-backup',
                '',
            ]
        ),
        encoding='utf-8',
    )
    hermes_env.write_text(
        '\n'.join(
            [
                'KEEP_ME=current-hermes',
                'DINGTALK_CLIENT_ID=current-client-id',
                'DINGTALK_CLIENT_SECRET=current-client-secret',
                'XINTAI_DINGTALK_STREAM_RELAY_TOKEN=current-hermes-relay',
                '',
            ]
        ),
        encoding='utf-8',
    )
    hermes_backup.write_text(
        '\n'.join(
            [
                'KEEP_ME=backup-hermes',
                f'DINGTALK_CLIENT_ID={old_client_id}',
                f'DINGTALK_CLIENT_SECRET={old_client_secret}',
                f'XINTAI_DINGTALK_STREAM_RELAY_TOKEN={old_hermes_relay}',
                'UNCHANGED_HERMES=from-backup',
                '',
            ]
        ),
        encoding='utf-8',
    )
    script_path.write_text(
        '\n'.join(
            [
                '#!/usr/bin/env bash',
                'set -euo pipefail',
                'upsert_env_value() {',
                '  local file="$1" key="$2" value="$3"',
                '  if grep -q "^${key}=" "$file"; then',
                '    sed -i "s|^${key}=.*|${key}=${value}|" "$file"',
                '  else',
                '    printf "%s=%s\\n" "$key" "$value" >> "$file"',
                '  fi',
                '}',
                f'stream_app_key="{replacement_key}"',
                f'stream_app_secret="{replacement_secret}"',
                f'stream_relay_token="{replacement_relay}"',
                restore_body,
                f'restore_env_backup "{datahub_env.name}" "{datahub_backup.name}" datahub',
                f'restore_env_backup "{hermes_env.name}" "{hermes_backup.name}" hermes',
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
        cwd=tmp_path,
        timeout=15,
    )

    datahub_text = datahub_env.read_text(encoding='utf-8')
    hermes_text = hermes_env.read_text(encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr
    assert old_key not in datahub_text
    assert old_secret not in datahub_text
    assert old_relay not in datahub_text
    assert old_client_id not in hermes_text
    assert old_client_secret not in hermes_text
    assert old_hermes_relay not in hermes_text
    assert f'DINGTALK_APP_KEY={replacement_key}' in datahub_text
    assert f'DINGTALK_APP_SECRET={replacement_secret}' in datahub_text
    assert f'HERMES_DINGTALK_STREAM_RELAY_TOKEN={replacement_relay}' in datahub_text
    assert f'DINGTALK_CLIENT_ID={replacement_key}' in hermes_text
    assert f'DINGTALK_CLIENT_SECRET={replacement_secret}' in hermes_text
    assert f'XINTAI_DINGTALK_STREAM_RELAY_TOKEN={replacement_relay}' in hermes_text
    assert 'UNCHANGED_DATAHUB=from-backup' in datahub_text
    assert 'UNCHANGED_HERMES=from-backup' in hermes_text
    assert replacement_key not in result.stdout
    assert replacement_secret not in result.stdout
    assert replacement_relay not in result.stdout
    assert old_key not in result.stdout
    assert old_secret not in result.stdout
    assert old_relay not in result.stdout
    assert 'chmod --reference="$file" "$temp_file"' in restore_body


def test_configure_dingtalk_run_acceptance_gate_preserves_exit_code_and_cleans_temp_dir() -> None:
    bash = _require_bash()
    gate_body = textwrap.dedent(_extract_shell_function(_read('.github/workflows/configure-dingtalk-stream-prod.yml'), 'run_acceptance_gate'))
    tmp_root = Path(tempfile.mkdtemp(prefix='dingtalk-gate-harness-'))
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='\n', suffix='.sh', dir=tmp_root, delete=False) as handle:
        script_path = Path(handle.name)
    marker_path = script_path.with_suffix('.log')
    temp_dir = script_path.with_suffix('.tmpdir')
    try:
        script_path.write_text(
            '\n'.join(
                [
                    '#!/usr/bin/env bash',
                    'set -euo pipefail',
                    f'MARKER_PATH="{marker_path.as_posix()}"',
                    f'TEMP_DIR="{temp_dir.as_posix()}"',
                    'DATAHUB_REPO="$PWD/repo-datahub"',
                    'DATAHUB_ENV_FILE="$PWD/datahub.env"',
                    'HERMES_HOME="$PWD/repo-hermes"',
                    'acceptance_marker=XT-P1-acceptance',
                    'acceptance_since=2026-07-16T08:00:00+08:00',
                    'min_text=10',
                    'min_files=5',
                    'expected_u1_sha256=u1',
                    'expected_u2_sha256=u2',
                    'mkdir -p "$DATAHUB_REPO/backend/.venv/bin" "$HERMES_HOME/gateway"',
                    'printf "#!/usr/bin/env bash\\nexit 17\\n" > "$DATAHUB_REPO/backend/.venv/bin/python"',
                    'printf "{}\\n" > "$HERMES_HOME/gateway/xintai_callback_proof_ledger.json"',
                    'chmod +x "$DATAHUB_REPO/backend/.venv/bin/python"',
                    'mktemp() {',
                    '  if [ "$1" = "-d" ]; then',
                    '    mkdir -p "$TEMP_DIR"',
                    '    printf "%s\\n" "$TEMP_DIR"',
                    '    return 0',
                    '  fi',
                    '  return 99',
                    '}',
                    'chmod() { echo "chmod:$*" >> "$MARKER_PATH"; }',
                    'install() { echo "install:$*" >> "$MARKER_PATH"; cp "$3" "$4"; }',
                    'read_env_value() { printf "%s\\n" "postgresql+psycopg2://test:test@localhost/test"; }',
                    'python3() { echo "python3:$*" >> "$MARKER_PATH"; return 0; }',
                    'rm() {',
                    '  echo "rm:$*" >> "$MARKER_PATH"',
                    '  if [ "$1" = "-rf" ]; then',
                    '    rmdir "$2"',
                    '  fi',
                    '}',
                    gate_body,
                    'set +e',
                    'run_acceptance_gate PRE',
                    'rc="$?"',
                    'set -e',
                    'echo "rc=$rc" >> "$MARKER_PATH"',
                    'test "$rc" -eq 17',
                    '',
                ]
            ),
            encoding='utf-8',
            newline='\n',
        )
        result = subprocess.run([bash, script_path.name], capture_output=True, text=True, check=False, cwd=tmp_root, timeout=15)
        marker_lines = marker_path.read_text(encoding='utf-8').splitlines() if marker_path.exists() else []
    finally:
        if marker_path.exists():
            os.unlink(marker_path)
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        if script_path.exists():
            os.unlink(script_path)
        shutil.rmtree(tmp_root, ignore_errors=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'chmod:700' in '\n'.join(marker_lines)
    assert any(line.startswith('install:-m 600 ') and 'xintai_callback_proof_ledger.json' in line for line in marker_lines)
    assert 'rm:-rf' in '\n'.join(marker_lines)
    assert 'rc=17' in marker_lines


def test_configure_dingtalk_preflight_uses_pgpassfile_without_leaking_database_url_or_password() -> None:
    bash = _require_bash()
    source = _read('.github/workflows/configure-dingtalk-stream-prod.yml')
    backup_body = textwrap.dedent(_extract_shell_function(source, 'backup_postgres_database'))
    tmp_root = Path(tempfile.mkdtemp(prefix='dingtalk-pgpass-harness-'))
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='\n', suffix='.sh', dir=tmp_root, delete=False) as handle:
        script_path = Path(handle.name)
    marker_path = script_path.with_suffix('.log')
    bin_dir = tmp_root / 'bin'
    bin_dir.mkdir()
    if os.name == 'nt':
        pg_dump_path = bin_dir / 'pg_dump.cmd'
        pg_restore_path = bin_dir / 'pg_restore.cmd'
        pg_dump_path.write_text(
            '\n'.join(
                [
                    '@echo off',
                    'echo pg_dump_args:%*>>"%MARKER_PATH%"',
                    'echo pg_dump_pgpass:%PGPASSFILE%>>"%MARKER_PATH%"',
                    'if defined PGPASSWORD (echo pg_dump_pgpassword:present>>"%MARKER_PATH%") else (echo pg_dump_pgpassword:missing>>"%MARKER_PATH%")',
                    'if defined DATABASE_URL (echo pg_dump_database_url:present>>"%MARKER_PATH%") else (echo pg_dump_database_url:missing>>"%MARKER_PATH%")',
                    'if exist "%PGPASSFILE%" echo pg_dump_pgpass_exists:yes>>"%MARKER_PATH%"',
                    'set dump_file=',
                    ':loop',
                    'if "%~1"=="" goto done',
                    'if "%~1"=="--file" set dump_file=%~2',
                    'shift',
                    'goto loop',
                    ':done',
                    'echo dump>"%dump_file%"',
                    '',
                ]
            ),
            encoding='utf-8',
        )
        pg_restore_path.write_text('@echo off\necho pg_restore_args:%*>>"%MARKER_PATH%"\n', encoding='utf-8')
    else:
        pg_dump_path = bin_dir / 'pg_dump'
        pg_restore_path = bin_dir / 'pg_restore'
        pg_dump_path.write_text(
            '\n'.join(
                [
                    '#!/usr/bin/env bash',
                    'set -euo pipefail',
                    'printf "pg_dump_args:%s\\n" "$*" >> "$MARKER_PATH"',
                    'printf "pg_dump_pgpass:%s\\n" "${PGPASSFILE:-}" >> "$MARKER_PATH"',
                    'if [ -n "${PGPASSWORD:-}" ]; then echo pg_dump_pgpassword:present; else echo pg_dump_pgpassword:missing; fi >> "$MARKER_PATH"',
                    'if [ -n "${DATABASE_URL:-}" ]; then echo pg_dump_database_url:present; else echo pg_dump_database_url:missing; fi >> "$MARKER_PATH"',
                    'if [ -f "$PGPASSFILE" ]; then echo pg_dump_pgpass_exists:yes >> "$MARKER_PATH"; fi',
                    'while [ "$#" -gt 0 ]; do',
                    '  if [ "$1" = "--file" ]; then shift; printf dump > "$1"; fi',
                    '  shift',
                    'done',
                    '',
                ]
            ),
            encoding='utf-8',
            newline='\n',
        )
        pg_restore_path.write_text(
            '#!/usr/bin/env bash\nset -euo pipefail\nprintf "pg_restore_args:%s\\n" "$*" >> "$MARKER_PATH"\n',
            encoding='utf-8',
            newline='\n',
        )
        pg_dump_path.chmod(0o700)
        pg_restore_path.chmod(0o700)
    try:
        script_path.write_text(
            '\n'.join(
                [
                    '#!/usr/bin/env bash',
                    'set -euo pipefail',
                    f'MARKER_PATH="{marker_path.as_posix()}"',
                    'export MARKER_PATH',
                    'DATAHUB_REPO="$PWD/repo-datahub"',
                    'mkdir -p "$DATAHUB_REPO/backend/.venv/bin" "$PWD/bin"',
                    'cat > "$DATAHUB_REPO/backend/.venv/bin/python" <<\'PYTHON_STUB\'',
                    '#!/usr/bin/env bash',
                    f'"{sys.executable}" "$@"',
                    'PYTHON_STUB',
                    'chmod +x "$DATAHUB_REPO/backend/.venv/bin/python"',
                    f'PG_DUMP_BIN="{pg_dump_path.as_posix()}"',
                    f'PG_RESTORE_BIN="{pg_restore_path.as_posix()}"',
                    f'PGPASS_TMPDIR="{tmp_root.as_posix()}"',
                    'export PG_DUMP_BIN PG_RESTORE_BIN PGPASS_TMPDIR',
                    f'BACKUP_FILE="{(tmp_root / "test.dump").as_posix()}"',
                    backup_body,
                    'backup_postgres_database "postgresql+psycopg2://test_user:synthetic-test-password@example.com:5433/test_db" "$BACKUP_FILE"',
                    'test -s "$BACKUP_FILE"',
                    'if compgen -G "$PWD/aluminum-dingtalk-pgpass-*" >/dev/null; then pgpass_after=yes; else pgpass_after=no; fi',
                    'printf "pgpass_after:%s\\n" "$pgpass_after" >> "$MARKER_PATH"',
                    '',
                ]
            ),
            encoding='utf-8',
            newline='\n',
        )
        result = subprocess.run([bash, script_path.name], capture_output=True, text=True, check=False, cwd=tmp_root, timeout=15)
        marker_text = marker_path.read_text(encoding='utf-8') if marker_path.exists() else ''
    finally:
        if marker_path.exists():
            os.unlink(marker_path)
        if script_path.exists():
            os.unlink(script_path)
        for leftover in ('repo-datahub', 'bin', 'test.dump'):
            candidate = tmp_root / leftover
            if candidate.is_dir():
                shutil.rmtree(candidate, ignore_errors=True)
            elif candidate.exists():
                os.unlink(candidate)
        shutil.rmtree(tmp_root, ignore_errors=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'synthetic-test-password' not in marker_text
    assert 'postgresql+psycopg2://' not in marker_text
    assert 'pg_dump_pgpassword:missing' in marker_text
    assert 'pg_dump_database_url:missing' in marker_text
    assert 'pg_dump_pgpass_exists:yes' in marker_text
    assert 'pgpass_after:no' in marker_text


def test_configure_dingtalk_verify_input_contract_requires_thresholds_timezone_and_secrets() -> None:
    source = _read('.github/workflows/configure-dingtalk-stream-prod.yml')
    require_body = _extract_shell_function(source, 'require_verify_inputs')
    backup_body = _extract_shell_function(source, 'backup_postgres_database')

    assert "grep -Eq '^[0-9]+$'" in require_body
    assert '[ "$min_text" -ge 10 ]' in require_body
    assert '[ "$min_files" -ge 5 ]' in require_body
    assert '[ -n "$stream_app_secret" ]' in require_body
    assert '[ -n "$stream_relay_token" ]' in require_body
    assert 'datetime.fromisoformat' in require_body
    assert 'tzinfo is None' in require_body
    assert 'database_url = os.environ.pop("DATABASE_URL")' in backup_body
    assert 'pgpass_path.unlink(missing_ok=True)' in backup_body
    assert 'umask 077' in source
    assert 'restart_epoch="$(date +%s)"' in source
    restart_index = source.find('restart_epoch="$(date +%s)"')
    restart_call_index = source.find('restart_hermes_gateway', restart_index)
    assert -1 not in (restart_index, restart_call_index)
    assert restart_index < restart_call_index
    assert 'backup_dir/$(basename "$file")' not in source
    assert 'backup_dir/${label}.backup-dingtalk-stream-' in source


def test_daily_report_alignment_prod_keeps_artifacts_outside_repo_and_preserves_exit_code() -> None:
    payload = _load('.github/workflows/daily-report-alignment-prod.yml')
    source = _read('.github/workflows/daily-report-alignment-prod.yml')
    inputs = _workflow_inputs(payload)

    assert 'days' not in inputs
    assert 'reference_mode' not in inputs
    assert inputs['business_end_date']['default'] == ''
    assert "DAYS: '3'" in source
    assert 'END_DATE: ${{ github.event.inputs.business_end_date }}' in source
    assert 'REFERENCE_MODE: compare' in source
    assert 'test "$DAYS" = "3"' in source
    assert 'test "$REFERENCE_MODE" = "compare"' in source
    assert 'business_end_date must be YYYY-MM-DD' in source
    assert "/srv/aluminum-bypass/docs/superpowers/reports" not in source
    assert '/var/lib/aluminum-bypass/acceptance/daily-report-alignment-${RUN_ID}' in source
    assert 'install -d -m 700 "$artifact_dir"' in source
    assert 'chmod 700 "$artifact_dir"' in source
    assert 'find "$artifact_dir" -type f -exec chmod 600 {} +' in source
    assert 'find "$artifact_dir" -type d -exec chmod 700 {} +' in source
    assert 'uses: actions/upload-artifact@v4' in source
    assert 'if: always()' in source
    assert 'scp -i ~/.ssh/deploy_key -P "$SSH_PORT" -o StrictHostKeyChecking=yes -o UserKnownHostsFile=~/.ssh/known_hosts -r \\' in source
    assert 'echo "exit_code=$remote_status" >> "$GITHUB_OUTPUT"' in source
    assert 'exit 0' in source
    assert 'official_daily_report' not in source
    assert '--reference-mode "$REFERENCE_MODE"' in source
    assert '--output-skill-root "$output_root"' in source
    assert 'alignment_args=(' in source
    assert 'alignment_args+=(--end-date "$END_DATE")' in source
    assert '"${alignment_args[@]}"' in source
    assert "tr -d '\\r\\n'" in source
    assert 'OUTPUT_SKILL_BUNDLE_INVALID_BASE64' in source


def test_import_dingtalk_history_prod_requires_owner_confirmation_and_secret_bundle() -> None:
    payload = _load('.github/workflows/import-dingtalk-history-prod.yml')
    source = _read('.github/workflows/import-dingtalk-history-prod.yml')
    inputs = _workflow_inputs(payload)
    concurrency = _workflow_concurrency(payload)

    assert concurrency == {
        'group': 'xintai-production-ops',
        'cancel-in-progress': False,
    }
    assert inputs['confirm']['required'] is True
    assert "github.event.inputs.confirm == 'import-owner-verified-dingtalk-history'" in source
    assert 'DINGTALK_HISTORY_IMPORT_BUNDLE_B64: ${{ secrets.DINGTALK_HISTORY_IMPORT_BUNDLE_B64 }}' in source
    for suffix in ('01', '02', '03', '04'):
        assert (
            f'DINGTALK_HISTORY_IMPORT_BUNDLE_B64_{suffix}: '
            f'${{{{ secrets.DINGTALK_HISTORY_IMPORT_BUNDLE_B64_{suffix} }}}}'
        ) in source
    assert 'bundle_sha256' in inputs
    assert 'expected_rows' in inputs
    assert 'DINGTALK_HISTORY_IMPORT_BUNDLE_B64' not in source[source.find('} | ssh'):]
    assert 'if [ -n "$DINGTALK_HISTORY_IMPORT_BUNDLE_B64_01" ]; then' in source
    assert 'printf \'%s\' \\' in source
    assert '"$DINGTALK_HISTORY_IMPORT_BUNDLE_B64_04" \\' in source
    assert "| tr -d '\\r\\n' | base64 -d > \"$bundle\"" in source
    assert 'unset DINGTALK_HISTORY_IMPORT_BUNDLE_B64_04' in source
    assert 'safe_extract_zip' in source
    assert 'local_file_path_outside_files_root' not in source
    assert '--confirmation-mode owner-verified-dws-history' in source
    assert '--confirmation-run-id "github-actions:${RUN_ID}"' in source
    assert "int(payload.get('committed', 0)) != 1" in source
    assert '/var/lib/aluminum-bypass/acceptance/dingtalk-history-${RUN_ID}' in source
    assert '/srv/aluminum-bypass/docs/' not in source
    assert 'rm -rf "$remote_work_dir"' in source
    assert 'uses: actions/upload-artifact@v4' in source
    assert 'StrictHostKeyChecking=no' not in source


def test_hermes_acceptance_prod_fails_closed_without_real_owner_and_keeps_artifacts_outside_repo() -> None:
    payload = _load('.github/workflows/hermes-acceptance-prod.yml')
    source = _read('.github/workflows/hermes-acceptance-prod.yml')
    inputs = _workflow_inputs(payload)

    assert 'mode' not in inputs
    assert 'limit' not in inputs
    assert "/srv/aluminum-bypass/docs/superpowers/reports" not in source
    assert '/var/lib/aluminum-bypass/acceptance/hermes-20q-${RUN_ID}' in source
    assert 'install -d -m 700 "$artifact_dir"' in source
    assert 'find "$artifact_dir" -type f -exec chmod 600 {} +' in source
    assert 'find "$artifact_dir" -type d -exec chmod 700 {} +' in source
    assert 'uses: actions/upload-artifact@v4' in source
    assert 'if: always()' in source
    assert 'NO_OWNER_DINGTALK_USER' in source
    assert '666327013924069283' not in source
    assert 'GROUP_SECRET_PRESENT=' in source
    assert 'SELECTED_GROUP_MASKED=' in source
    assert 'GROUP_SECRET_MASKED=' not in source
    assert '.filter(User.username.in_(("root-owner", "root_owner")))' in source
    assert '.filter(User.dingtalk_user_id.is_not(None))' in source
    assert '.filter(User.is_active.is_(True))' in source
    assert '.order_by(User.id.asc())' in source
    assert '.first()' in source
    assert '.filter(User.dingtalk_user_id.is_not(None))\n                  .order_by(User.id.asc())\n                  .first()' not in source
    assert 'status=no_admin_user' in source
    assert 'test -n "$DINGTALK_ACCEPTANCE_GROUP_KEY"' in source
    assert 'target_type="production_acceptance"' in source
    assert 'target_key="hermes_20_question_production_acceptance"' in source
    assert 'limit=None' in source
    assert 'if len(outcome.snapshots) != 20:' in source
    assert 'HERMES_20Q_INCOMPLETE=' in source


def test_hermes_acceptance_always_registers_explicit_real_group_and_runs_full_gate() -> None:
    source = _read('.github/workflows/hermes-acceptance-prod.yml')

    register_index = source.find('register_channel(')
    assert register_index != -1
    assert 'EXPLICIT_GROUP_SECRET_REQUIRED_FOR_RUN_REGISTRATION' in source
    assert 'mode == "preflight"' not in source
    assert 'AMBIGUOUS_DINGTALK_GROUP_CANDIDATE' not in source
    assert 'NO_APPROVED_DINGTALK_GROUP_CANDIDATE' not in source
    assert 'acceptance_test' not in source
    assert 'append_remote_assignment DINGTALK_ACCEPTANCE_GROUP_KEY "$DINGTALK_ACCEPTANCE_GROUP_KEY"' in source
    assert "printf -v REMOTE_PREAMBLE '%sexport %s=%q\\n'" in source
    assert "DINGTALK_ACCEPTANCE_GROUP_KEY='$DINGTALK_ACCEPTANCE_GROUP_KEY'" not in source
    assert '} | ssh -i ~/.ssh/deploy_key -p "$SSH_PORT" -o StrictHostKeyChecking=yes -o UserKnownHostsFile=~/.ssh/known_hosts "$SSH_USER@$SSH_HOST" "bash -s"' in source


def test_hermes_acceptance_uploads_redacted_per_question_diagnostics() -> None:
    source = _read('.github/workflows/hermes-acceptance-prod.yml')

    assert 'build_acceptance_diagnostics' in source
    assert 'hermes-20-question-real-acceptance-production.json' in source
    assert 'json.dumps(diagnostics, ensure_ascii=False, indent=2)' in source
    assert 'write_local_preflight_failure' in source
    assert 'build_preflight_acceptance_diagnostics' in source
    assert '"status": "preflight_failed"' in source
    assert '"failure_reason": reason' in source
    for summary_field in (
        '"core_passed": False',
        '"delivery_passed": False',
        '"core_pass_count": 0',
        '"delivery_success_count": 0',
        '"environment_failure_count": 0',
        '"total": 20',
        '"results": []',
    ):
        assert summary_field in source
    assert 'echo "exit_code=2" >> "$GITHUB_OUTPUT"' in source
    assert 'def write_diagnostics(payload: dict[str, object]) -> Path:' in source
    assert source.count('write_diagnostics(') >= 5
    assert source.index('diagnostics = build_acceptance_diagnostics(outcome)') < source.index(
        'if len(outcome.snapshots) != 20:'
    )


def test_archive_prod_untracked_checks_runtime_references_before_any_move() -> None:
    payload = _load('.github/workflows/archive-prod-untracked.yml')
    source = _read('.github/workflows/archive-prod-untracked.yml')
    inputs = _workflow_inputs(payload)

    assert inputs['mode']['default'] == 'dry-run'
    assert '/srv/aluminum-bypass-archive/untracked' not in source
    assert '/var/backups/aluminum-bypass' in source
    assert 'untracked-${timestamp}-run-${RUN_ID}' in source
    assert '/etc/systemd/system' in source
    assert 'systemctl cat ' in source
    assert 'systemctl list-timers' in source
    assert '/etc/cron' in source
    assert 'crontab -l' in source
    assert 'referenced' in source
    assert 'clear' in source
    assert 'RUNTIME_REFERENCE_FOUND' in source
    assert 'find "$archive_dir" -type d -exec chmod 700 {} +' in source
    assert 'chmod 600 "$archive_dir/manifest.tsv"' in source
    assert 'curl -fsS http://127.0.0.1:8000/readyz' in source
    assert 'git status --short --branch' in source
    assert 'git fetch origin main' not in source
    assert 'git checkout main' not in source
    assert 'git pull --ff-only origin main' not in source
    assert 'head_before="$(git rev-parse HEAD)"' in source
    assert 'head_after="$(git rev-parse HEAD)"' in source
    assert 'ARCHIVE_CHANGED_HEAD' in source
    assert 'ARCHIVE_HEAD_UNCHANGED' in source


def test_production_workflows_pin_ssh_host_keys() -> None:
    paths = (
        '.github/workflows/production-sync-status.yml',
        '.github/workflows/configure-dingtalk-stream-prod.yml',
        '.github/workflows/configure-hermes-codex-prod.yml',
        '.github/workflows/configure-hermes-openrouter-prod.yml',
        '.github/workflows/read-hermes-codex-handoff-prod.yml',
        '.github/workflows/import-dingtalk-history-prod.yml',
        '.github/workflows/hermes-acceptance-prod.yml',
        '.github/workflows/daily-report-alignment-prod.yml',
        '.github/workflows/archive-prod-untracked.yml',
    )

    for path in paths:
        source = _read(path)
        assert 'SSH_KNOWN_HOSTS: ${{ secrets.PROD_SSH_KNOWN_HOSTS }}' in source
        assert 'test -n "$SSH_KNOWN_HOSTS"' in source
        assert 'printf \'%s\\n\' "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts' in source
        assert 'chmod 600 ~/.ssh/known_hosts' in source
        assert 'StrictHostKeyChecking=yes' in source
        assert 'UserKnownHostsFile=~/.ssh/known_hosts' in source
        assert 'StrictHostKeyChecking=no' not in source


def test_configure_hermes_codex_prod_is_redacted_exact_sha_and_reversible() -> None:
    path = '.github/workflows/configure-hermes-codex-prod.yml'
    payload = _load(path)
    source = _read(path)
    inputs = _workflow_inputs(payload)
    concurrency = _workflow_concurrency(payload)
    job = payload['jobs']['configure-hermes-codex-production']

    assert concurrency == {
        'group': 'xintai-production-ops',
        'cancel-in-progress': False,
    }
    assert inputs['confirm']['required'] is True
    assert inputs['mode']['options'] == ['status', 'configure', 'inference', 'login']
    assert 'status|configure|inference|login' in source
    assert inputs['model']['default'] == 'gpt-5.6-luna'
    assert inputs['model']['options'] == ['gpt-5.6-luna', 'gpt-5.6-sol']
    assert 'expected_hermes_sha' in inputs
    assert inputs['device_code_public_key_b64']['required'] is False
    assert job['if'] == "github.event.inputs.confirm == 'prod-hermes-codex'"
    assert job['environment'] == 'production'
    assert 'HERMES_REPO="/srv/hermes-cloud/runtime/.hermes/hermes-agent"' in source
    assert "grep -Eq '^[0-9a-f]{40}$'" in source
    assert 'git -C "$HERMES_REPO" rev-parse HEAD' in source
    assert '[ "$actual_hermes_sha" = "$expected_hermes_sha" ]' in source
    assert 'systemctl show -p MainPID --value hermes-gateway' in source
    assert '/proc/${runtime_pid}/cmdline' in source
    assert '/proc/${runtime_pid}/environ' in source
    assert 'auth add openai-codex --type oauth --label xintai-production' in source
    assert 'DEVICE_CODE_PUBLIC_KEY_B64' in source
    assert 'openssl pkey -pubin -in "$device_code_public_key" -noout' in source
    assert 'openssl pkeyutl -encrypt -pubin' in source
    assert 'rsa_padding_mode:oaep' in source
    assert 'rsa_oaep_md:sha256' in source
    assert 'HERMES_CODEX_DEVICE_CODE_CIPHERTEXT=' in source
    assert 'HERMES_CODEX_HANDOFF_FILE=' in source
    assert 'handoff_file="$handoff_dir/${RUN_ID}.ciphertext"' in source
    assert 'chmod 600 "$handoff_file"' in source
    assert '::notice title=Hermes Codex device authorization::' in source
    assert 'HERMES_CODEX_DEVICE_CODE=' not in source
    assert 'cat "$oauth_log"' not in source
    assert 'rm -f "$oauth_log" "$device_code_public_key"' in source
    assert 'get_codex_auth_status' in source
    assert '"api_key"' not in source
    assert 'OPENAI_API_KEY' not in source
    assert 'CODEX_ACCESS_TOKEN' not in source
    assert '~/.codex/auth.json' not in source
    assert 'HERMES_CODEX_AUTH_LOGGED_IN=' in source
    assert 'HERMES_CODEX_AUTH_RATE_LIMITED=' in source
    assert 'HERMES_MODEL_PROVIDER=' in source
    assert 'HERMES_MODEL_DEFAULT=' in source
    assert 'HERMES_REASONING_EFFORT=' in source
    assert 'REASONING_EFFORT: max' in source
    assert 'test "$REASONING_EFFORT" = "max"' in source
    assert 'agent_config["reasoning_effort"] = reasoning_effort' in source
    assert 'FAST_REASONING_EFFORT: high' in source
    assert 'agent_config["adaptive_reasoning"]' in source
    assert 'agent_config["disabled_toolsets"] = []' in source
    assert 'platform_toolsets["dingtalk"] = ["hermes-dingtalk"]' in source
    assert 'approvals_config["mode"] = "off"' in source
    assert 'HERMES_FULL_ACCESS_READY=' in source
    assert 'HERMES_CODEX_FALLBACK_READY=' in source
    assert 'config["fallback_providers"]' in source
    assert '"gpt-5.6-sol" if model == "gpt-5.6-luna" else "gpt-5.6-luna"' in source
    assert 'HERMES_CODEX_CONFIG_VERIFIED' in source
    assert 'run_as_service_with_timeout 240s' in source
    assert '--provider openai-codex --model "$MODEL" -z "$inference_prompt"' in source
    assert 'HERMES_CODEX_INFERENCE_ANSWER=' in source
    assert 'HERMES_CODEX_INFERENCE_VERIFIED' in source
    assert 'HERMES_CODEX_INFERENCE_FAILED' in source
    assert '鑫泰铝业智能大脑' in source
    assert 'required_identity_terms = ("鑫泰铝业", "智能", "大脑")' in source
    assert 'HERMES_CODEX_INFERENCE_FORBIDDEN_IDENTITY' in source
    assert 'cp -p "$auth_file" "$backup_dir/auth.json"' in source
    assert 'cp -p "$config_file" "$backup_dir/config.yaml"' in source
    assert 'rollback_on_operation_error' in source
    assert 'restore_optional_file "$backup_dir/auth.json" "$auth_file"' in source
    assert 'restore_optional_file "$backup_dir/config.yaml" "$config_file"' in source
    assert 'restart_hermes_gateway' in source
    assert 'HERMES_CODEX_LOGIN_VERIFIED' in source
    assert 'DINGTALK_STREAM_CONNECTION=connected' in source
    assert 'set -x' not in source
    assert 'printenv' not in source


def test_configure_hermes_openrouter_prod_keeps_primary_stable_and_secret_out_of_git() -> None:
    path = '.github/workflows/configure-hermes-openrouter-prod.yml'
    payload = _load(path)
    source = _read(path)
    inputs = _workflow_inputs(payload)
    job = payload['jobs']['configure-hermes-openrouter-production']

    assert inputs['mode']['options'] == [
        'status',
        'configure',
        'inference',
        'fallback-inference',
    ]
    assert inputs['model']['default'] == 'stealth/ox-alpha'
    assert inputs['fallback_model']['default'] == 'none'
    assert inputs['fallback_model']['options'] == ['none', 'gpt-5.6-luna', 'gpt-5.6-sol']
    assert job['environment'] == 'production'
    assert 'OPENROUTER_API_KEY: ${{ secrets.PROD_OPENROUTER_API_KEY }}' in source
    assert 'model_config.update({"provider": "openrouter"' in source
    assert 'fallback_model != "none"' in source
    assert 'CODEX_FALLBACK_DISABLED_FOR_FALLBACK_INFERENCE' in source
    assert 'HERMES_CODEX_FALLBACK_INFERENCE=skipped_disabled' in source
    assert 'store["active_provider"] = "openrouter"' in source
    assert 'robot/oToMessages' not in source
    assert 'HERMES_OPENROUTER_INFERENCE_VERIFIED=yes' not in source
    assert 'verify_inference openrouter "$MODEL" OPENROUTER' in source
    assert 'verify_inference openai-codex "$FALLBACK_MODEL" CODEX_FALLBACK' in source
    assert 'zz-openrouter-direct.conf' in source
    assert 'resolver 127.0.0.53 ipv6=off valid=30s;' in source
    assert 'rewrite ^/v1/(.*)$ /api/v1/$1 break;' in source
    assert 'proxy_buffer_size 64k;' in source
    assert 'proxy_buffers 4 64k;' in source
    assert 'proxy_busy_buffers_size 64k;' in source
    assert 'HERMES_OPENROUTER_OPERATION_VERIFIED=yes' in source
    assert 'cp -p "$target" "$backup_dir/$name"' in source
    assert 'rollback()' in source
    assert 'set -x' not in source


def test_read_hermes_codex_handoff_prod_is_concurrent_exact_and_ciphertext_only() -> None:
    path = '.github/workflows/read-hermes-codex-handoff-prod.yml'
    payload = _load(path)
    source = _read(path)
    inputs = _workflow_inputs(payload)
    concurrency = _workflow_concurrency(payload)
    job = payload['jobs']['read-hermes-codex-handoff-production']

    assert concurrency == {
        'group': 'xintai-production-oauth-handoff-read',
        'cancel-in-progress': False,
    }
    assert inputs['confirm']['required'] is True
    assert inputs['login_run_id']['required'] is True
    assert inputs['expected_hermes_sha']['required'] is True
    assert job['if'] == "github.event.inputs.confirm == 'read-prod-hermes-codex-handoff'"
    assert job['environment'] == 'production'
    assert 'HERMES_REPO="/srv/hermes-cloud/runtime/.hermes/hermes-agent"' in source
    assert 'HERMES_HOME="/srv/hermes-cloud/runtime/.hermes"' in source
    assert "grep -Eq '^[0-9]+$'" in source
    assert "grep -Eq '^[0-9a-f]{40}$'" in source
    assert 'git -C "$HERMES_REPO" rev-parse HEAD' in source
    assert '[ "$actual_hermes_sha" = "$EXPECTED_HERMES_SHA" ]' in source
    assert 'oauth-handoffs/${LOGIN_RUN_ID}.ciphertext' in source
    assert 'test "$(stat -c %a "$handoff_file")" = "600"' in source
    assert "grep -Eq '^[A-Za-z0-9+/]+={0,2}$'" in source
    assert 'HERMES_CODEX_DEVICE_CODE_CIPHERTEXT=' in source
    assert 'HERMES_CODEX_DEVICE_CODE=' not in source
    assert 'rm -f "$handoff_file"' in source
    assert 'set -x' not in source
    assert 'printenv' not in source


def test_legacy_deploy_production_workflow_is_removed_in_favor_of_exact_sha_gate() -> None:
    assert not (REPO_ROOT / '.github/workflows/deploy-prod.yml').exists()
    source = _read('.github/workflows/production-sync-status.yml')

    assert 'DATAHUB_REPO="/srv/aluminum-bypass"' in source
    assert 'require_trusted_head "$DATAHUB_REPO" "$DATAHUB_SHA"' in source
    assert 'git -C "$DATAHUB_REPO" checkout --detach "$DATAHUB_SHA"' in source


def test_configure_stream_uses_separate_relay_secret_for_real_stream_events() -> None:
    source = _read('.github/workflows/configure-dingtalk-stream-prod.yml')

    assert 'HERMES_DINGTALK_STREAM_RELAY_TOKEN' in source
    assert 'XINTAI_DINGTALK_STREAM_RELAY_TOKEN' in source
    assert 'openssl rand -hex 32' in source
    assert 'upsert_env_value "$HERMES_ENV_FILE" "XINTAI_DINGTALK_INBOUND_TOKEN"' not in source
    assert 'DATAHUB_INBOUND_TOKEN_MISSING' not in source

def test_production_sync_status_trusted_head_probe_blocks_unmerged_targets() -> None:
    bash = _require_bash()
    tmp_dir = tempfile.mkdtemp(dir=REPO_ROOT)
    tmp_path = Path(tmp_dir)
    try:
        script_path = tmp_path / 'trusted-ancestor.sh'
        script_path.write_text(
            "\n".join(
                [
                    '#!/usr/bin/env bash',
                    'set -euo pipefail',
                    'DATAHUB_TRUSTED_REF="origin/main"',
                    'HERMES_TRUSTED_REF="refs/heads/main"',
                    'require_trusted_head() {',
                    '  local repo="$1"',
                    '  local sha="$2"',
                    '  local trusted_ref="$3"',
                    '  local label="$4"',
                    '  local trusted_head',
                    '  trusted_head="$(git -C "$repo" rev-parse "$trusted_ref")"',
                    '  if [ "$sha" != "$trusted_head" ]; then',
                    '    echo "${label}_SHA_NOT_TRUSTED_HEAD"',
                    '    exit 91',
                    '  fi',
                    '}',
                    'repo="$PWD/repo"',
                    'mkdir "$repo"',
                    'git -C "$repo" init -q',
                    'git -C "$repo" config user.email test@example.com',
                    'git -C "$repo" config user.name test',
                    'printf "base\n" > "$repo/file.txt"',
                    'git -C "$repo" add file.txt',
                    'git -C "$repo" commit -q -m base',
                    'git -C "$repo" branch -M main',
                    'git -C "$repo" remote add origin "$repo"',
                    'git -C "$repo" update-ref refs/remotes/origin/main "$(git -C "$repo" rev-parse HEAD)"',
                    'git -C "$repo" branch feature/xintai-single-ingress-fact-closure',
                    'trusted_sha="$(git -C "$repo" rev-parse HEAD)"',
                    'printf "side\n" >> "$repo/file.txt"',
                    'git -C "$repo" commit -qam side',
                    'untrusted_sha="$(git -C "$repo" rev-parse HEAD)"',
                    'git -C "$repo" checkout -q "$trusted_sha"',
                    'require_trusted_head "$repo" "$trusted_sha" "$DATAHUB_TRUSTED_REF" DATAHUB',
                    'if require_trusted_head "$repo" "$untrusted_sha" "$DATAHUB_TRUSTED_REF" DATAHUB; then',
                    '  exit 92',
                    'fi',
                    '',
                ]
            ),
            encoding='utf-8',
            newline='\n',
        )
        result = subprocess.run([bash, script_path.name], capture_output=True, text=True, check=False, cwd=tmp_path, timeout=15)
    finally:
        _remove_test_tree(tmp_path)

    assert result.returncode == 91
    assert 'DATAHUB_SHA_NOT_TRUSTED' in result.stdout


def test_production_sync_status_hermes_cloud_ref_probe_ignores_evil_local_branch() -> None:
    bash = _require_bash()
    tmp_dir = tempfile.mkdtemp(dir=REPO_ROOT)
    tmp_path = Path(tmp_dir)
    try:
        script_path = tmp_path / 'hermes-cloud-ref.sh'
        script_path.write_text(
            "\n".join(
                [
                    '#!/usr/bin/env bash',
                    'set -euo pipefail',
                    'HERMES_TRUSTED_REMOTE_URL="$PWD/cloud.git"',
                    'HERMES_TRUSTED_BRANCH="refs/heads/main"',
                    'HERMES_TRUSTED_REF="refs/remotes/xintai_cloud/main"',
                    'update_trusted_refs() {',
                    '  local repo="$1"',
                    '  if ! git -C "$repo" fetch --prune "$HERMES_TRUSTED_REMOTE_URL" "+$HERMES_TRUSTED_BRANCH:$HERMES_TRUSTED_REF"; then',
                    '    echo "HERMES_TRUSTED_REF_UNAVAILABLE"',
                    '    exit 90',
                    '  fi',
                    '}',
                    'require_trusted_head() {',
                    '  local repo="$1"',
                    '  local sha="$2"',
                    '  local trusted_ref="$3"',
                    '  local label="$4"',
                    '  local trusted_head',
                    '  trusted_head="$(git -C "$repo" rev-parse "$trusted_ref")"',
                    '  if [ "$sha" != "$trusted_head" ]; then',
                    '    echo "${label}_SHA_NOT_TRUSTED_HEAD"',
                    '    exit 91',
                    '  fi',
                    '}',
                    'work="$PWD/work"',
                    'seed="$PWD/seed"',
                    'cloud="$PWD/cloud.git"',
                    'git init --bare -q "$cloud"',
                    'mkdir "$seed"',
                    'git -C "$seed" init -q',
                    'git -C "$seed" config user.email test@example.com',
                    'git -C "$seed" config user.name test',
                    'printf "base\n" > "$seed/file.txt"',
                    'git -C "$seed" add file.txt',
                    'git -C "$seed" commit -q -m base',
                    'git -C "$seed" branch -M main',
                    'git -C "$seed" remote add origin "$cloud"',
                    'git -C "$seed" push -q origin main',
                    'mkdir "$work"',
                    'git -C "$work" init -q',
                    'git -C "$work" config user.email test@example.com',
                    'git -C "$work" config user.name test',
                    'git -C "$work" remote add origin "$cloud"',
                    'git -C "$work" fetch -q origin main:refs/remotes/origin/main',
                    'git -C "$work" checkout -q -b feature/xintai-single-ingress-fact-closure refs/remotes/origin/main',
                    'checked_out_before="$(git -C "$work" branch --show-current)"',
                    'printf "evil\n" >> "$work/file.txt"',
                    'git -C "$work" commit -qam evil',
                    'evil_local_sha="$(git -C "$work" rev-parse HEAD)"',
                    'printf "trusted\n" >> "$seed/file.txt"',
                    'git -C "$seed" commit -qam trusted',
                    'trusted_sha="$(git -C "$seed" rev-parse HEAD)"',
                    'git -C "$seed" push -q origin main',
                    'if git -C "$work" cat-file -e "${trusted_sha}^{commit}" 2>/dev/null; then',
                    '  exit 93',
                    'fi',
                    'update_trusted_refs "$work"',
                    'fetched_ref_sha="$(git -C "$work" rev-parse "$HERMES_TRUSTED_REF")"',
                    'checked_out_after_fetch="$(git -C "$work" branch --show-current)"',
                    'git -C "$work" cat-file -e "${trusted_sha}^{commit}"',
                    'if ( require_trusted_head "$work" "$trusted_sha" "$HERMES_TRUSTED_REF" HERMES ); then',
                    '  trusted_rc=0',
                    'else',
                    '  trusted_rc="$?"',
                    'fi',
                    'if ( require_trusted_head "$work" "$evil_local_sha" "$HERMES_TRUSTED_REF" HERMES ); then',
                    '  evil_rc=0',
                    '  exit 92',
                    'else',
                    '  evil_rc="$?"',
                    'fi',
                    'printf "checked_out_before=%s\nchecked_out_after_fetch=%s\ntrusted_sha=%s\nfetched_ref_sha=%s\nevil_local_sha=%s\ntrusted_rc=%s\nevil_rc=%s\n" "$checked_out_before" "$checked_out_after_fetch" "$trusted_sha" "$fetched_ref_sha" "$evil_local_sha" "$trusted_rc" "$evil_rc"',
                    '',
                ]
            ),
            encoding='utf-8',
            newline='\n',
        )
        result = subprocess.run([bash, script_path.name], capture_output=True, text=True, check=False, cwd=tmp_path, timeout=15)
    finally:
        _remove_test_tree(tmp_path)

    assert result.returncode == 0
    assert 'HERMES_SHA_NOT_TRUSTED' in result.stdout
    assert 'checked_out_before=feature/xintai-single-ingress-fact-closure' in result.stdout
    assert 'checked_out_after_fetch=feature/xintai-single-ingress-fact-closure' in result.stdout
    assert 'trusted_sha=' in result.stdout
    assert 'fetched_ref_sha=' in result.stdout
    assert 'trusted_rc=0' in result.stdout
    assert 'evil_rc=91' in result.stdout


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
            timeout=15,
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


def test_production_sync_status_revision_change_failure_triggers_db_restore_marker() -> None:
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
                    'DATAHUB_CHECKOUT_DONE=1',
                    'HERMES_CHECKOUT_DONE=1',
                    'DB_BACKUP=/tmp/fake.dump',
                    'DATABASE_LIBPQ_URL=postgresql://ignored',
                    'NEEDS_DB_RESTORE=0',
                    'PRE_MIGRATION_REVISIONS=rev-before',
                    'rollback_on_error() {',
                    '  local exit_code="${1:-1}"',
                    '  trap - EXIT ERR',
                    '  local rollback_failed=0',
                    '  echo "DEPLOY_FAILED_ROLLBACK_START"',
                    '  if [ "$NEEDS_DB_RESTORE" = "1" ]; then',
                    '    echo "ROLLBACK_DATABASE_FROM=$DB_BACKUP"',
                    '    echo "db_restore" >> "$MARKER_PATH"',
                    '  fi',
                    '  if [ "$rollback_failed" -eq 0 ]; then',
                    '    echo "DEPLOY_FAILED_ROLLBACK_DONE"',
                    '    exit "$exit_code"',
                    '  fi',
                    '  exit 97',
                    '}',
                    trap_line,
                    'NEEDS_DB_RESTORE=1',
                    'POST_MIGRATION_REVISIONS=rev-after',
                    'if [ "$PRE_MIGRATION_REVISIONS" = "$POST_MIGRATION_REVISIONS" ]; then',
                    '  NEEDS_DB_RESTORE=0',
                    'fi',
                    'exit 43',
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
            timeout=15,
        )
        marker_text = marker_path.read_text(encoding='utf-8').strip() if marker_path.exists() else ''
    finally:
        if marker_path.exists():
            os.unlink(marker_path)
        if script_path.exists():
            os.unlink(script_path)

    assert result.returncode == 43
    assert 'ROLLBACK_DATABASE_FROM=/tmp/fake.dump' in result.stdout
    assert 'DEPLOY_FAILED_ROLLBACK_DONE' in result.stdout
    assert marker_text == 'db_restore'


@pytest.mark.parametrize(
    ('pg_restore_exit_code', 'expected_returncode'),
    ((0, 43), (1, 97)),
)
def test_production_sync_status_db_restore_harness_stops_services_before_restore(
    pg_restore_exit_code: int,
    expected_returncode: int,
) -> None:
    bash = _require_bash()
    rollback_body = _extract_shell_function(_read('.github/workflows/production-sync-status.yml'), 'rollback_on_error')
    tmp_root = REPO_ROOT
    datahub_repo_path = REPO_ROOT / 'repo-datahub'
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='\n', suffix='.sh', dir=tmp_root, delete=False) as handle:
        script_path = Path(handle.name)
    marker_path = script_path.with_suffix('.log')
    try:
        script_path.write_text(
            "\n".join(
                [
                    '#!/usr/bin/env bash',
                    'set -euo pipefail',
                    f'MARKER_PATH="{marker_path.as_posix()}"',
                    'DATAHUB_REPO="$PWD/repo-datahub"',
                    'HERMES_REPO=/repo-hermes',
                    'HERMES_HOME=/hermes-home',
                    'DATAHUB_ENV_FILE="$PWD/env-datahub"',
                    'HERMES_ENV_FILE="$PWD/env-hermes"',
                    'HERMES_CONFIG_FILE="$PWD/config-hermes"',
                    'DATAHUB_CHECKOUT_DONE=1',
                    'HERMES_CHECKOUT_DONE=1',
                    'NEEDS_DB_RESTORE=1',
                    'PRE_MIGRATION_REVISIONS=0052_hermes_factory_brain',
                    'RAW_DATABASE_URL=postgresql+psycopg2://ignored',
                    f'PG_RESTORE_EXIT_CODE={pg_restore_exit_code}',
                    'DB_BACKUP=/tmp/fake.dump',
                    'DATABASE_LIBPQ_URL=postgresql://ignored',
                    'PREVIOUS_DATAHUB_HEAD=old-datahub',
                    'PREVIOUS_HERMES_HEAD=old-hermes',
                    'DATAHUB_ENV_BACKUP="$PWD/datahub.env.bak"',
                    'HERMES_ENV_BACKUP="$PWD/hermes.env.bak"',
                    'HERMES_CONFIG_BACKUP="$PWD/hermes.config.bak"',
                    'mkdir -p "$DATAHUB_REPO/backend/.venv/bin" "$DATAHUB_REPO/frontend"',
                    'touch "$DB_BACKUP"',
                    'export MARKER_PATH',
                    'cat > "$DATAHUB_REPO/backend/.venv/bin/python" <<\'PYTHON_STUB\'',
                    '#!/usr/bin/env bash',
                    'echo "python:$*" >> "$MARKER_PATH"',
                    'PYTHON_STUB',
                    'chmod +x "$DATAHUB_REPO/backend/.venv/bin/python"',
                    'get_alembic_revisions() { echo "0054_dingtalk_inbound_receipts"; }',
                    'alembic_revisions_valid() { return 0; }',
                    'alembic_single_revision_valid() { return 0; }',
                    'restore_env_backup() { echo "env_restore:$1" >> "$MARKER_PATH"; }',
                    'restore_hermes_runtime_dropin() { echo "runtime_restore" >> "$MARKER_PATH"; }',
                    'reload_or_restart_nginx() { echo "nginx_reload" >> "$MARKER_PATH"; }',
                    'stop_hermes_gateway() { return 0; }',
                    'git() { echo "git:$*" >> "$MARKER_PATH"; }',
                    'systemctl() { echo "systemctl:$*" >> "$MARKER_PATH"; }',
                    'pg_restore() { echo "pg_restore:$*" >> "$MARKER_PATH"; return "$PG_RESTORE_EXIT_CODE"; }',
                    'npm() { echo "npm:$*" >> "$MARKER_PATH"; }',
                    'curl() { echo "curl:$*" >> "$MARKER_PATH"; }',
                    'cd() { builtin cd "$@"; }',
                    rollback_body,
                    'rollback_on_error 43 >/tmp/rollback-harness.out',
                    '',
                ]
            ),
            encoding='utf-8',
            newline='\n',
        )
        result = subprocess.run([bash, script_path.name], capture_output=True, text=True, check=False, cwd=tmp_root, timeout=15)
        marker_lines = marker_path.read_text(encoding='utf-8').splitlines() if marker_path.exists() else []
    finally:
        _remove_test_tree(datahub_repo_path)
        if marker_path.exists():
            os.unlink(marker_path)
        if script_path.exists():
            os.unlink(script_path)

    assert result.returncode == expected_returncode
    assert marker_lines[0] == 'systemctl:stop aluminum-bypass'
    downgrade_index = marker_lines.index(
        'python:-m alembic downgrade 0052_hermes_factory_brain'
    )
    datahub_restore_index = next(
        index
        for index, line in enumerate(marker_lines)
        if line.startswith('git:-C ')
        and line.replace('\\', '/').endswith('/repo-datahub checkout --detach old-datahub')
    )
    assert any(line.startswith('pg_restore:--single-transaction --exit-on-error --clean --if-exists --no-owner --no-privileges') for line in marker_lines)
    db_restore_index = next(index for index, line in enumerate(marker_lines) if line.startswith('pg_restore:'))
    assert marker_lines.index('systemctl:stop aluminum-bypass') < downgrade_index
    assert downgrade_index < datahub_restore_index < db_restore_index
    if pg_restore_exit_code:
        assert not any(line.startswith('npm:') for line in marker_lines)
        assert 'systemctl:restart aluminum-bypass' not in marker_lines
        assert 'systemctl:start hermes-gateway' not in marker_lines
    else:
        assert 'systemctl:restart aluminum-bypass' in marker_lines
        assert 'systemctl:start hermes-gateway' in marker_lines


def test_production_sync_status_rollback_requires_readyz_recovery() -> None:
    bash = _require_bash()
    rollback_body = _extract_shell_function(_read('.github/workflows/production-sync-status.yml'), 'rollback_on_error')
    tmp_root = REPO_ROOT
    datahub_repo_path = REPO_ROOT / 'repo-datahub'
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='\n', suffix='.sh', dir=tmp_root, delete=False) as handle:
        script_path = Path(handle.name)
    try:
        script_path.write_text(
            "\n".join(
                [
                    '#!/usr/bin/env bash',
                    'set -euo pipefail',
                    'DATAHUB_REPO="$PWD/repo-datahub"',
                    'HERMES_REPO=/repo-hermes',
                    'HERMES_HOME=/hermes-home',
                    'DATAHUB_ENV_FILE="$PWD/env-datahub"',
                    'HERMES_ENV_FILE="$PWD/env-hermes"',
                    'HERMES_CONFIG_FILE="$PWD/config-hermes"',
                    'DATAHUB_CHECKOUT_DONE=0',
                    'HERMES_CHECKOUT_DONE=0',
                    'NEEDS_DB_RESTORE=0',
                    'DB_BACKUP=' ,
                    'DATABASE_LIBPQ_URL=postgresql://ignored',
                    'DATAHUB_ENV_BACKUP=' ,
                    'HERMES_ENV_BACKUP=' ,
                    'HERMES_CONFIG_BACKUP=' ,
                    'mkdir -p "$DATAHUB_REPO/backend/.venv/bin" "$DATAHUB_REPO/frontend"',
                    'printf "#!/usr/bin/env bash\nexit 0\n" > "$DATAHUB_REPO/backend/.venv/bin/python"',
                    'chmod +x "$DATAHUB_REPO/backend/.venv/bin/python"',
                    'restore_env_backup() { return 0; }',
                    'restore_hermes_runtime_dropin() { return 0; }',
                    'reload_or_restart_nginx() { return 0; }',
                    'stop_hermes_gateway() { return 0; }',
                    'systemctl() { return 0; }',
                    'pg_restore() { return 0; }',
                    'npm() { return 0; }',
                    'curl() { return 1; }',
                    'sleep() { return 0; }',
                    'git() { return 0; }',
                    'cd() { builtin cd "$@"; }',
                    rollback_body,
                    'rollback_on_error 43',
                    '',
                ]
            ),
            encoding='utf-8',
            newline='\n',
        )
        result = subprocess.run([bash, script_path.name], capture_output=True, text=True, check=False, cwd=tmp_root, timeout=15)
    finally:
        _remove_test_tree(datahub_repo_path)
        if script_path.exists():
            os.unlink(script_path)

    assert result.returncode == 97
    assert 'ROLLBACK_FAILED_READYZ' in result.stdout
    assert 'DEPLOY_FAILED_ROLLBACK_DONE' not in result.stdout


def test_configure_dingtalk_apply_failure_restores_env_backups() -> None:
    bash = _require_bash()
    source = _read('.github/workflows/configure-dingtalk-stream-prod.yml')
    trap_line = _find_rollback_trap_line(source, 'rollback_on_apply_error')
    rollback_body = _extract_shell_function(source, 'rollback_on_apply_error')
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
                    'DATAHUB_ENV_FILE=datahub.env',
                    'HERMES_ENV_FILE=hermes.env',
                    'HERMES_CONFIG_FILE=hermes.config',
                    'HERMES_HOME=/hermes-home',
                    'datahub_env_backup=datahub.env.bak',
                    'hermes_env_backup=hermes.env.bak',
                    'hermes_config_backup=hermes.config.bak',
                    'restore_env_backup() { echo "restore:$1:$2:$3" >> "$MARKER_PATH"; }',
                    'reload_or_restart_nginx() { echo "nginx" >> "$MARKER_PATH"; }',
                    'restart_hermes_gateway() { systemctl restart hermes-gateway; }',
                    'systemctl() { echo "systemctl:$*" >> "$MARKER_PATH"; }',
                    'curl() { echo "curl:$*" >> "$MARKER_PATH"; }',
                    rollback_body,
                    trap_line,
                    'echo mutate >> "$MARKER_PATH"',
                    'exit 52',
                    '',
                ]
            ),
            encoding='utf-8',
            newline='\n',
        )
        result = subprocess.run([bash, script_path.name], capture_output=True, text=True, check=False, cwd=tmp_root, timeout=15)
        marker_lines = marker_path.read_text(encoding='utf-8').splitlines() if marker_path.exists() else []
    finally:
        if marker_path.exists():
            os.unlink(marker_path)
        if script_path.exists():
            os.unlink(script_path)

    assert result.returncode == 52
    assert 'APPLY_FAILED_ROLLBACK_START' in result.stdout
    assert 'APPLY_FAILED_ROLLBACK_DONE' in result.stdout
    assert 'restore:datahub.env:datahub.env.bak:datahub' in marker_lines
    assert 'restore:hermes.env:hermes.env.bak:hermes' in marker_lines


def test_configure_dingtalk_secret_preamble_reaches_remote_bash_without_echoing_values() -> None:
    bash = _require_bash()
    tmp_root = REPO_ROOT
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='\n', suffix='.sh', dir=tmp_root, delete=False) as handle:
        script_path = Path(handle.name)
    try:
        script_path.write_text(
            "\n".join(
                [
                    '#!/usr/bin/env bash',
                    'set -euo pipefail',
                    'append_remote_assignment() {',
                    '  local name="$1"',
                    '  local value="$2"',
                    '  printf -v REMOTE_PREAMBLE "%s%s=%q\\n" "$REMOTE_PREAMBLE" "$name" "$value"',
                    '}',
                    'REMOTE_PREAMBLE=""',
                    'append_remote_assignment STREAM_APP_KEY_B64 "secret-app-key"',
                    'append_remote_assignment MODE "apply"',
                    '{',
                    '  printf "%s" "$REMOTE_PREAMBLE"',
                    "  cat <<'REMOTE'",
                    'printf "mode=%s\\n" "$MODE"',
                    'printf "len=%s\\n" "${#STREAM_APP_KEY_B64}"',
                    "REMOTE",
                    '} | bash -s',
                    '',
                ]
            ),
            encoding='utf-8',
            newline='\n',
        )
        result = subprocess.run([bash, script_path.name], capture_output=True, text=True, check=False, cwd=tmp_root, timeout=15)
    finally:
        if script_path.exists():
            os.unlink(script_path)

    assert result.returncode == 0
    assert 'mode=apply' in result.stdout
    assert 'len=14' in result.stdout
    assert 'secret-app-key' not in result.stdout


def test_production_sync_status_pre_revision_detection_failure_triggers_db_restore_marker() -> None:
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
                    'DATAHUB_CHECKOUT_DONE=1',
                    'HERMES_CHECKOUT_DONE=1',
                    'DB_BACKUP=/tmp/fake.dump',
                    'DATABASE_LIBPQ_URL=postgresql://ignored',
                    'NEEDS_DB_RESTORE=1',
                    'rollback_on_error() {',
                    '  local exit_code="${1:-1}"',
                    '  trap - EXIT ERR',
                    '  echo "DEPLOY_FAILED_ROLLBACK_START"',
                    '  if [ "$NEEDS_DB_RESTORE" = "1" ]; then',
                    '    echo "ROLLBACK_DATABASE_FROM=$DB_BACKUP"',
                    '    echo "db_restore" >> "$MARKER_PATH"',
                    '  fi',
                    '  echo "DEPLOY_FAILED_ROLLBACK_DONE"',
                    '  exit "$exit_code"',
                    '}',
                    trap_line,
                    'echo PRE_MIGRATION_REVISION_DETECTION_FAILED',
                    'exit 45',
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
            timeout=15,
        )
        marker_text = marker_path.read_text(encoding='utf-8').strip() if marker_path.exists() else ''
    finally:
        if marker_path.exists():
            os.unlink(marker_path)
        if script_path.exists():
            os.unlink(script_path)

    assert result.returncode == 45
    assert 'PRE_MIGRATION_REVISION_DETECTION_FAILED' in result.stdout
    assert 'ROLLBACK_DATABASE_FROM=/tmp/fake.dump' in result.stdout
    assert marker_text == 'db_restore'


def test_production_sync_status_post_revision_detection_failure_triggers_db_restore_marker() -> None:
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
                    'DATAHUB_CHECKOUT_DONE=1',
                    'HERMES_CHECKOUT_DONE=1',
                    'DB_BACKUP=/tmp/fake.dump',
                    'DATABASE_LIBPQ_URL=postgresql://ignored',
                    'NEEDS_DB_RESTORE=1',
                    'PRE_MIGRATION_REVISIONS=rev-before',
                    'rollback_on_error() {',
                    '  local exit_code="${1:-1}"',
                    '  trap - EXIT ERR',
                    '  echo "DEPLOY_FAILED_ROLLBACK_START"',
                    '  if [ "$NEEDS_DB_RESTORE" = "1" ]; then',
                    '    echo "ROLLBACK_DATABASE_FROM=$DB_BACKUP"',
                    '    echo "db_restore" >> "$MARKER_PATH"',
                    '  fi',
                    '  echo "DEPLOY_FAILED_ROLLBACK_DONE"',
                    '  exit "$exit_code"',
                    '}',
                    trap_line,
                    'echo POST_MIGRATION_REVISION_DETECTION_FAILED',
                    'exit 46',
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
            timeout=15,
        )
        marker_text = marker_path.read_text(encoding='utf-8').strip() if marker_path.exists() else ''
    finally:
        if marker_path.exists():
            os.unlink(marker_path)
        if script_path.exists():
            os.unlink(script_path)

    assert result.returncode == 46
    assert 'POST_MIGRATION_REVISION_DETECTION_FAILED' in result.stdout
    assert 'ROLLBACK_DATABASE_FROM=/tmp/fake.dump' in result.stdout
    assert marker_text == 'db_restore'


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
                    timeout=15,
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
