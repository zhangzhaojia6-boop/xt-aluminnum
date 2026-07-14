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
    '.github/workflows/daily-report-alignment-prod.yml',
    '.github/workflows/hermes-acceptance-prod.yml',
    '.github/workflows/archive-prod-untracked.yml',
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
    assert 'ROLLBACK_FAILED_READYZ' in rollback_body
    assert source.rfind('trap - EXIT') > source.find('report_status "yes"')
    assert '/versionz' in source
    assert 'BUILD_SHA' in source
    assert 'HERMES_BUILD_SHA' in source
    assert '/srv/aluminum-bypass' in source
    assert '/srv/hermes-cloud/runtime/.hermes/hermes-agent' in source


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
    assert 'Connected via Stream Mode' in source
    assert 'systemctl show -p ActiveEnterTimestamp' in source
    assert 'local attempts="${2:-1}"' in source
    assert 'local delay_seconds="${3:-0}"' in source
    assert 'for attempt in $(seq 1 "$attempts")' in source
    assert 'sleep "$delay_seconds"' in source
    assert 'report_stream_connection "yes" 40 3' in source


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
    assert 'append_remote_assignment()' in source
    assert 'printf -v REMOTE_PREAMBLE' in source
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
    assert 'systemctl restart hermes-gateway' in source
    assert '/readyz' in source
    assert 'journalctl -u hermes-gateway' in source
    assert 'Connected via Stream Mode' in source
    assert 'systemctl show -p ActiveEnterTimestamp' in source
    assert 'multimodal_evidence' in source
    assert 'chat_inbox' in source
    assert 'external_message_logs' in source
    assert "source_payload->>'source_transport' = 'dingtalk_stream'" in source
    assert "payload->>'source_transport' = 'dingtalk_stream'" in source
    assert "LIKE 'dingtalk-stream-sha256:%'" not in source
    assert "- verify" in source
    assert 'verify_fresh_stream_evidence()' in source
    assert 'FRESH_STREAM_EVIDENCE_VERIFIED=yes' in source
    assert "evidence_type = 'text'" in source
    assert "evidence_type = 'attachment'" in source
    assert "payload->>'message_text'" in source
    assert "payload->>'file_text'" in source
    assert "payload->>'attachment_text'" in source
    assert 'WHERE created_at >= :since' in source
    assert 'report_stream_connection "yes" 40 3' in source
    assert 'DATAHUB_STREAM_RELAY_TOKEN_PRESENT=' in source
    assert 'HERMES_STREAM_RELAY_TOKEN_PRESENT=' in source
    rollback_body = _extract_shell_function(source, 'rollback_on_apply_error')
    assert 'APPLY_FAILED_ROLLBACK_START' in rollback_body
    assert 'APPLY_FAILED_ROLLBACK_DONE' in rollback_body
    assert 'APPLY_FAILED_ROLLBACK_INCOMPLETE' in rollback_body
    assert 'ROLLBACK_FAILED_DATAHUB_ENV' in rollback_body
    assert 'ROLLBACK_FAILED_HERMES_ENV' in rollback_body
    assert 'ROLLBACK_FAILED_READYZ' in rollback_body


def test_daily_report_alignment_prod_keeps_artifacts_outside_repo_and_preserves_exit_code() -> None:
    payload = _load('.github/workflows/daily-report-alignment-prod.yml')
    source = _read('.github/workflows/daily-report-alignment-prod.yml')
    inputs = _workflow_inputs(payload)

    assert 'days' not in inputs
    assert 'reference_mode' not in inputs
    assert "DAYS: '3'" in source
    assert 'REFERENCE_MODE: compare' in source
    assert 'test "$DAYS" = "3"' in source
    assert 'test "$REFERENCE_MODE" = "compare"' in source
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
    assert "DINGTALK_ACCEPTANCE_GROUP_KEY='$DINGTALK_ACCEPTANCE_GROUP_KEY'" not in source
    assert '} | ssh -i ~/.ssh/deploy_key -p "$SSH_PORT" -o StrictHostKeyChecking=yes -o UserKnownHostsFile=~/.ssh/known_hosts "$SSH_USER@$SSH_HOST" "bash -s"' in source


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
        shutil.rmtree(tmp_path, ignore_errors=True)

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
        shutil.rmtree(tmp_path, ignore_errors=True)

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


def test_production_sync_status_rollback_requires_readyz_recovery() -> None:
    bash = _require_bash()
    rollback_body = _extract_shell_function(_read('.github/workflows/production-sync-status.yml'), 'rollback_on_error')
    tmp_root = REPO_ROOT
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
                    'DATAHUB_ENV_FILE="$PWD/env-datahub"',
                    'HERMES_ENV_FILE="$PWD/env-hermes"',
                    'DATAHUB_CHECKOUT_DONE=0',
                    'HERMES_CHECKOUT_DONE=0',
                    'NEEDS_DB_RESTORE=0',
                    'DB_BACKUP=' ,
                    'DATABASE_LIBPQ_URL=postgresql://ignored',
                    'DATAHUB_ENV_BACKUP=' ,
                    'HERMES_ENV_BACKUP=' ,
                    'mkdir -p "$DATAHUB_REPO/backend/.venv/bin" "$DATAHUB_REPO/frontend"',
                    'printf "#!/usr/bin/env bash\nexit 0\n" > "$DATAHUB_REPO/backend/.venv/bin/python"',
                    'chmod +x "$DATAHUB_REPO/backend/.venv/bin/python"',
                    'restore_env_backup() { return 0; }',
                    'reload_or_restart_nginx() { return 0; }',
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
    assert 'restore:datahub.env:datahub.env.bak' in marker_lines
    assert 'restore:hermes.env:hermes.env.bak' in marker_lines


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
