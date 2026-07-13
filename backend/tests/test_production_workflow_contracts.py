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


def _workflow_concurrency(payload: dict) -> dict:
    concurrency = payload.get('concurrency')
    assert isinstance(concurrency, dict)
    return concurrency


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
    assert 'sync' not in mode_options
    assert 'datahub_sha' in inputs
    assert 'hermes_sha' in inputs
    assert "git merge --ff-only origin/main" not in source
    assert "backend/scripts/hermes_dingtalk_stream_gateway.py --health" not in source
    assert "^[0-9a-f]{40}$" in source
    assert 'checkout --detach "$DATAHUB_SHA"' in source
    assert 'checkout --detach "$HERMES_SHA"' in source
    assert 'pg_restore -l "$DB_BACKUP"' in source or 'pg_restore -l "$db_backup"' in source
    assert 'DATAHUB_TRUSTED_REF="origin/main"' in source
    assert 'HERMES_TRUSTED_REF="refs/heads/feature/xintai-single-ingress-fact-closure"' in source
    assert 'merge-base --is-ancestor "$sha" "$trusted_ref"' in source
    assert 'require_trusted_ancestor "$DATAHUB_REPO" "$DATAHUB_SHA" "$DATAHUB_TRUSTED_REF" DATAHUB' in source
    assert 'require_trusted_ancestor "$HERMES_REPO" "$HERMES_SHA" "$HERMES_TRUSTED_REF" HERMES' in source
    assert "trap 'rc=$?; if [ \"$rc\" -ne 0 ]; then rollback_on_error \"$rc\"; fi' EXIT" in source
    assert 'trap rollback_on_error ERR' not in source
    assert 'get_alembic_revisions()' in source
    assert 'alembic_revisions_valid()' in source
    assert 'PRE_MIGRATION_REVISIONS' in source
    assert 'POST_MIGRATION_REVISIONS' in source
    assert 'PRE_MIGRATION_REVISION_DETECTION_FAILED' in source
    assert 'POST_MIGRATION_REVISION_DETECTION_FAILED' in source
    assert 'NEEDS_DB_RESTORE=1' in source
    assert 'if alembic_revisions_valid "$PRE_MIGRATION_REVISIONS" && alembic_revisions_valid "$POST_MIGRATION_REVISIONS" && [ "$PRE_MIGRATION_REVISIONS" = "$POST_MIGRATION_REVISIONS" ]; then' in source
    assert 'NEEDS_DB_RESTORE=0' in source
    pre_index = source.find('if PRE_MIGRATION_REVISIONS="$(get_alembic_revisions "$RAW_DATABASE_URL")"; then')
    set_restore_index = source.find('NEEDS_DB_RESTORE=1')
    alembic_index = source.find('alembic upgrade head')
    post_index = source.find('if POST_MIGRATION_REVISIONS="$(get_alembic_revisions "$RAW_DATABASE_URL")"; then')
    reset_restore_index = source.find('NEEDS_DB_RESTORE=0', post_index)
    assert -1 not in (pre_index, set_restore_index, alembic_index, post_index, reset_restore_index)
    assert set_restore_index < pre_index < alembic_index < post_index < reset_restore_index
    rollback_body = _extract_shell_function(source, 'rollback_on_error')
    assert 'systemctl stop aluminum-bypass hermes-gateway' in rollback_body
    assert 'pg_restore --single-transaction --exit-on-error --clean --if-exists --no-owner --no-privileges -d "$DATABASE_LIBPQ_URL" "$DB_BACKUP"' in rollback_body
    assert '"$DATAHUB_REPO/backend/.venv/bin/python" -m pip install -r "$DATAHUB_REPO/backend/requirements.txt"' in rollback_body
    assert 'npm ci --no-audit --no-fund &&' in rollback_body
    assert 'npm run build' in rollback_body
    assert 'ROLLBACK_HERMES_DEPENDENCY_SYNC_SKIPPED=deploy_did_not_mutate_hermes_dependencies' in rollback_body
    assert 'ROLLBACK_FAILED_' in rollback_body
    assert '|| true' not in rollback_body
    assert 'DEPLOY_FAILED_ROLLBACK_DONE' in rollback_body
    stop_index = rollback_body.find('systemctl stop aluminum-bypass hermes-gateway')
    repo_restore_index = rollback_body.find('checkout --detach "$PREVIOUS_DATAHUB_HEAD"')
    db_restore_index = rollback_body.find('pg_restore --single-transaction --exit-on-error --clean --if-exists --no-owner --no-privileges -d "$DATABASE_LIBPQ_URL" "$DB_BACKUP"')
    deps_restore_index = rollback_body.find('"$DATAHUB_REPO/backend/.venv/bin/python" -m pip install -r "$DATAHUB_REPO/backend/requirements.txt"')
    frontend_restore_index = rollback_body.find('npm run build')
    restart_index = rollback_body.find('systemctl restart aluminum-bypass')
    assert -1 not in (stop_index, repo_restore_index, db_restore_index, deps_restore_index, frontend_restore_index, restart_index)
    assert stop_index < repo_restore_index < db_restore_index < deps_restore_index < frontend_restore_index < restart_index
    assert source.rfind('trap - EXIT') > source.find('report_status "yes"')
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
    concurrency = _workflow_concurrency(payload)

    assert concurrency == {
        'group': 'xintai-production-ops',
        'cancel-in-progress': False,
    }
    assert inputs['authorized_group_ids']['default'] == '*'
    assert "backend/scripts/hermes_dingtalk_stream_gateway.py --health" not in source
    assert 'rollback_on_apply_error()' in source
    assert "trap 'rc=$?; if [ \"$rc\" -ne 0 ]; then rollback_on_apply_error \"$rc\"; fi' EXIT" in source
    assert 'trap - EXIT' in source
    apply_trap_index = source.find("trap 'rc=$?; if [ \"$rc\" -ne 0 ]; then rollback_on_apply_error \"$rc\"; fi' EXIT")
    first_mutation_index = source.find('upsert_env_value "$DATAHUB_ENV_FILE" "DINGTALK_STREAM_ENABLED" "true"')
    assert -1 not in (apply_trap_index, first_mutation_index)
    assert apply_trap_index < first_mutation_index
    assert 'systemctl restart hermes-gateway' in source
    assert '/readyz' in source
    assert 'journalctl -u hermes-gateway' in source
    assert 'Connected via Stream Mode' in source
    assert 'systemctl show -p ActiveEnterTimestamp' in source
    assert 'multimodal_evidence' in source
    assert 'chat_inbox' in source
    assert 'external_message_logs' in source
    rollback_body = _extract_shell_function(source, 'rollback_on_apply_error')
    assert 'APPLY_FAILED_ROLLBACK_START' in rollback_body
    assert 'APPLY_FAILED_ROLLBACK_DONE' in rollback_body
    assert 'APPLY_FAILED_ROLLBACK_INCOMPLETE' in rollback_body
    assert 'ROLLBACK_FAILED_DATAHUB_ENV' in rollback_body
    assert 'ROLLBACK_FAILED_HERMES_ENV' in rollback_body
    assert 'ROLLBACK_FAILED_READYZ' in rollback_body


def test_production_sync_status_trusted_ancestor_probe_blocks_unmerged_targets() -> None:
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
                    'HERMES_TRUSTED_REF="refs/heads/feature/xintai-single-ingress-fact-closure"',
                    'require_trusted_ancestor() {',
                    '  local repo="$1"',
                    '  local sha="$2"',
                    '  local trusted_ref="$3"',
                    '  local label="$4"',
                    '  if ! git -C "$repo" merge-base --is-ancestor "$sha" "$trusted_ref"; then',
                    '    echo "${label}_SHA_NOT_TRUSTED"',
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
                    'require_trusted_ancestor "$repo" "$trusted_sha" "$DATAHUB_TRUSTED_REF" DATAHUB',
                    'if require_trusted_ancestor "$repo" "$untrusted_sha" "$DATAHUB_TRUSTED_REF" DATAHUB; then',
                    '  exit 92',
                    'fi',
                    '',
                ]
            ),
            encoding='utf-8',
            newline='\n',
        )
        result = subprocess.run([bash, script_path.name], capture_output=True, text=True, check=False, cwd=tmp_path)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)

    assert result.returncode == 91
    assert 'DATAHUB_SHA_NOT_TRUSTED' in result.stdout


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


def test_production_sync_status_db_restore_harness_stops_services_before_restore() -> None:
    bash = _require_bash()
    rollback_body = _extract_shell_function(_read('.github/workflows/production-sync-status.yml'), 'rollback_on_error')
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
                    'DATAHUB_REPO="$PWD/repo-datahub"',
                    'HERMES_REPO=/repo-hermes',
                    'DATAHUB_ENV_FILE="$PWD/env-datahub"',
                    'HERMES_ENV_FILE="$PWD/env-hermes"',
                    'DATAHUB_CHECKOUT_DONE=1',
                    'HERMES_CHECKOUT_DONE=1',
                    'NEEDS_DB_RESTORE=1',
                    'DB_BACKUP=/tmp/fake.dump',
                    'DATABASE_LIBPQ_URL=postgresql://ignored',
                    'PREVIOUS_DATAHUB_HEAD=old-datahub',
                    'PREVIOUS_HERMES_HEAD=old-hermes',
                    'DATAHUB_ENV_BACKUP="$PWD/datahub.env.bak"',
                    'HERMES_ENV_BACKUP="$PWD/hermes.env.bak"',
                    'mkdir -p "$DATAHUB_REPO/backend/.venv/bin" "$DATAHUB_REPO/frontend"',
                    'touch "$DB_BACKUP"',
                    'printf "#!/usr/bin/env bash\necho python:$* >> \\"$MARKER_PATH\\"\n" > "$DATAHUB_REPO/backend/.venv/bin/python"',
                    'chmod +x "$DATAHUB_REPO/backend/.venv/bin/python"',
                    'restore_env_backup() { echo "env_restore:$1" >> "$MARKER_PATH"; }',
                    'reload_or_restart_nginx() { echo "nginx_reload" >> "$MARKER_PATH"; }',
                    'git() { echo "git:$*" >> "$MARKER_PATH"; }',
                    'systemctl() { echo "systemctl:$*" >> "$MARKER_PATH"; }',
                    'pg_restore() { echo "pg_restore:$*" >> "$MARKER_PATH"; }',
                    'npm() { echo "npm:$*" >> "$MARKER_PATH"; }',
                    'cd() { builtin cd "$@"; }',
                    rollback_body,
                    'rollback_on_error 43 >/tmp/rollback-harness.out',
                    '',
                ]
            ),
            encoding='utf-8',
            newline='\n',
        )
        result = subprocess.run([bash, script_path.name], capture_output=True, text=True, check=False, cwd=tmp_root)
        marker_lines = marker_path.read_text(encoding='utf-8').splitlines() if marker_path.exists() else []
    finally:
        if marker_path.exists():
            os.unlink(marker_path)
        if script_path.exists():
            os.unlink(script_path)

    assert result.returncode == 43
    assert marker_lines[0] == 'systemctl:stop aluminum-bypass hermes-gateway'
    assert any(line.startswith('pg_restore:--single-transaction --exit-on-error --clean --if-exists --no-owner --no-privileges') for line in marker_lines)
    assert marker_lines.index('systemctl:stop aluminum-bypass hermes-gateway') < next(
        index for index, line in enumerate(marker_lines) if line.startswith('pg_restore:')
    )


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
                    'datahub_env_backup=datahub.env.bak',
                    'hermes_env_backup=hermes.env.bak',
                    'restore_env_backup() { echo "restore:$1:$2" >> "$MARKER_PATH"; }',
                    'reload_or_restart_nginx() { echo "nginx" >> "$MARKER_PATH"; }',
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
        result = subprocess.run([bash, script_path.name], capture_output=True, text=True, check=False, cwd=tmp_root)
        marker_lines = marker_path.read_text(encoding='utf-8').splitlines() if marker_path.exists() else []
    finally:
        if marker_path.exists():
            os.unlink(marker_path)
        if script_path.exists():
            os.unlink(script_path)

    assert result.returncode == 52
    assert 'APPLY_FAILED_ROLLBACK_START' in result.stdout
    assert 'APPLY_FAILED_ROLLBACK_DONE' in result.stdout
    assert 'restore:datahub.env:datahub.env.bak' in marker_lines
    assert 'restore:hermes.env:hermes.env.bak' in marker_lines


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
