import importlib.util
import os
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = (
    Path(os.environ['ALUMINUM_BYPASS_REPO_ROOT'])
    if os.environ.get('ALUMINUM_BYPASS_REPO_ROOT')
    else Path(__file__).resolve().parents[2]
)


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding='utf-8-sig')


DEPLOYMENT_SHELL_SCRIPTS = [
    'scripts/backup_db.sh',
    'scripts/check_trial_stack.sh',
    'scripts/deploy_trial.sh',
    'scripts/deploy_systemd_host.sh',
    'scripts/go_live_gate.sh',
    'scripts/launch_cloud_trial.sh',
    'scripts/restore_db.sh',
]


def test_deployment_shell_scripts_are_executable_in_git_index() -> None:
    output = subprocess.check_output(
        ['git', 'ls-files', '-s', *DEPLOYMENT_SHELL_SCRIPTS],
        cwd=REPO_ROOT,
        text=True,
    )

    modes = {
        parts[3]: parts[0]
        for line in output.splitlines()
        if (parts := line.split(maxsplit=3))
    }

    assert modes == {path: '100755' for path in DEPLOYMENT_SHELL_SCRIPTS}


def test_systemd_host_deploy_script_matches_current_ecs_topology() -> None:
    script = _read('scripts/deploy_systemd_host.sh')
    state = _read('docs/deploy/current-state.md')

    assert 'HOST-SYSTEMD ONLY' in script
    assert 'docker compose' not in script
    assert 'SERVICE_NAME="${SERVICE_NAME:-aluminum-bypass}"' in script
    assert 'NGINX_SERVICE_NAME="${NGINX_SERVICE_NAME:-nginx}"' in script
    assert 'BACKEND_DIR="$REPO_ROOT/backend"' in script
    assert 'FRONTEND_DIR="$REPO_ROOT/frontend"' in script
    assert 'BACKEND_ENV_FILE="$BACKEND_DIR/.env"' in script
    assert 'BACKUP_FILE="${BACKUP_FILE:-$BACKUP_DIR/systemd-predeploy-$TIMESTAMP.dump}"' in script
    assert 'SQLALCHEMY_DB_URL="${DATABASE_URL:-$(get_env_value DATABASE_URL)}"' in script
    assert 'normalize_pg_dump_url()' in script
    assert 'postgresql+*://*)' in script
    assert 'DB_URL="$(normalize_pg_dump_url "$SQLALCHEMY_DB_URL")"' in script
    assert 'pg_dump "$DB_URL" -Fc -f "$BACKUP_FILE"' in script
    assert 'pg_restore -l "$BACKUP_FILE"' in script
    assert 'APP_ENV_VALUE="$(get_env_value APP_ENV | tr -d' in script
    assert '部署 systemd host 前必须设置 APP_ENV=production' in script
    assert 'require_env_value SECRET_KEY' in script
    assert 'require_env_value INIT_ADMIN_PASSWORD' in script
    assert 'if is_weak_secret_key "$SECRET_KEY_VALUE"; then' in script
    assert 'if is_weak_admin_password "$INIT_ADMIN_PASSWORD_VALUE"; then' in script
    assert '.venv/bin/python -m pip install -r requirements.txt' in script
    assert '.venv/bin/alembic upgrade head' in script
    assert '.venv/bin/python scripts/init_master_data.py' in script
    assert '.venv/bin/python scripts/init_real_master_data.py' in script
    assert '.venv/bin/python scripts/create_admin.py' in script
    assert 'npm ci --include=dev' in script
    assert 'npm rebuild' in script
    assert 'VITE_API_BASE_URL="${VITE_API_BASE_URL:-/api/v1}" npm run build' in script
    assert 'systemctl restart "$SERVICE_NAME"' in script
    assert 'systemctl is-active --quiet "$SERVICE_NAME"' in script
    assert 'systemctl is-active --quiet "$NGINX_SERVICE_NAME"' in script
    assert 'READY_RESPONSE="$(curl -sS --max-time 10 -w \'\\n%{http_code}\' "$BACKEND_BASE_URL/readyz" 2>/dev/null || true)"' in script
    assert '"hard_gate_passed"[[:space:]]*:[[:space:]]*true' in script
    assert '--dry-run|--check-only' in script
    assert '--pull' in script
    assert '--require-external' in script
    assert 'REQUIRE_EXTERNAL=0' in script
    assert 'REQUIRE_EXTERNAL=1' in script
    assert 'if [ "$REQUIRE_EXTERNAL" -eq 1 ]; then' in script
    assert '.venv/bin/python scripts/check_statistics_module_ready.py --json' in script
    assert 'git pull --ff-only origin main' in script
    assert '当前 ECS systemd 形态的临时更新命令' not in state
    assert './scripts/deploy_systemd_host.sh --pull http://8.140.218.13' in state
    assert './scripts/deploy_systemd_host.sh --pull --require-external https://你的域名' in state
    assert 'systemctl is-active aluminum-bypass' in state
    assert 'systemctl is-active nginx' in state


def test_backend_registers_daily_default_schedule_seed_job() -> None:
    source = _read('backend/app/main.py')

    assert 'def _run_schedule_seed():' in source
    assert 'seed_default_pilot_schedule(session)' in source
    assert '\n        _run_schedule_seed()\n' in source
    assert "id='default_schedule_seed'" in source
    assert "'cron'" in source
    assert 'hour=0' in source
    assert 'minute=5' in source
    assert 'replace_existing=True' in source
    assert 'coalesce=True' in source
    assert 'max_instances=1' in source
    assert source.index('\n        _run_schedule_seed()\n') < source.index('        scheduler.start()')


def _load_deploy_production_module():
    module_path = REPO_ROOT / 'backend/scripts/deploy_production.py'
    spec = importlib.util.spec_from_file_location('deploy_production_under_test', module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gitignore_covers_quick_trial_artifacts() -> None:
    source = _read('.gitignore')

    assert '.tmp-pytest/' in source
    assert 'backend/.pytest-cache/' in source
    assert 'backend/.pytest-cache-2/' in source
    assert 'backend/pytest-cache-files-*/' in source
    assert 'backend/.pytest-run-*/' in source
    assert 'frontend/tmp-review-home.png' in source
    assert 'frontend/frontend/' in source


def test_backend_dockerignore_excludes_pytest_runtime_artifacts() -> None:
    source = _read('backend/.dockerignore')

    assert '.env' in source
    assert '.env.*' in source
    assert '!.env.example' in source
    assert '*.pem' in source
    assert '*.key' in source
    assert '.pytest-run-*/' in source
    assert '.pytest-cache/' in source
    assert '.pytest-cache-2/' in source
    assert 'pytest-cache-files-*/' in source
    assert '.pytest_cache/' in source
    assert 'uploads/' in source
    assert 'local-dev.db' in source


def test_root_dockerignore_covers_backend_pytest_runtime_dirs() -> None:
    source = _read('.dockerignore')

    assert '.env' in source
    assert '.env.*' in source
    assert '!.env.example' in source
    assert 'ssl/' in source
    assert 'backups/' in source
    assert '.vercel/' in source
    assert '*.pem' in source
    assert '*.key' in source
    assert 'backend/.pytest-run-*/' in source
    assert 'backend/.pytest_cache' in source


def test_vercel_preview_uses_current_manage_smoke_paths() -> None:
    source = _read('docs/VERCEL_PREVIEW.md')

    for current_token in [
        '- `main`',
        '- `/login`',
        '- `/entry`',
        '- `/manage/overview`',
        '- `/manage/ai-assistant`',
        '- `/manage/reports`',
        '- `/manage/quality`',
        '- `/manage/factory/cost`',
        '- `/manage/ingestion`',
        '- `/manage/admin/settings`',
        '- `/manage/admin/governance`',
        '- `/manage/master`',
    ]:
        assert current_token in source

    for stale_token in [
        '- `ui重构`',
        '- 暂不 merge `main`。',
        '- `/review/brain`',
        '- `/review/cost-accounting`',
        '- `/admin/ingestion`',
        '- `/admin/ops`',
        '- `/admin/governance`',
        '- `/admin/master`',
    ]:
        assert stale_token not in source


def test_full_deploy_script_requires_external_secret_values() -> None:
    source = _read('backend/scripts/deploy_production.py')

    assert "DEPLOY_SSH_KEY_PATH" in source
    assert "DEPLOY_KNOWN_HOSTS" in source
    assert "DEPLOY_DATABASE_URL" in source
    assert "DEPLOY_SECRET_KEY" in source
    assert "DEPLOY_INIT_ADMIN_PASSWORD" in source
    assert "DEPLOY_SSH_PASSWORD" not in source
    assert "password=ssh_password" not in source
    assert "PASS =" not in source
    assert "DB_URL =" not in source
    assert "admin123" not in source
    assert "prod-secret-key" not in source


def test_full_deploy_script_uses_key_based_known_hosts_non_root_ssh() -> None:
    source = _read('backend/scripts/deploy_production.py')
    audit = _read('docs/audits/2026-05-02-cleanup-round2-test-audit.md')

    assert 'DEPLOY_SSH_PASSWORD' not in source
    assert 'DEPLOY_SSH_KEY_PATH' in source
    assert 'DEPLOY_KNOWN_HOSTS' in source
    assert 'DEPLOY_USER' in source
    assert "DEPLOY_USER must be a least-privilege non-root user" in source
    assert 'paramiko.RejectPolicy()' in source
    assert 'AutoAddPolicy' not in source
    assert 'key_filename=ssh_key_path' in source
    assert 'password=ssh_password' not in source
    assert 'allow_agent=False' in source
    assert 'look_for_keys=False' in source
    assert '| S01 |' not in audit
    assert '| R75 |' in audit


def test_full_deploy_script_require_env_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_deploy_production_module()

    monkeypatch.delenv('DEPLOY_DATABASE_URL', raising=False)
    with pytest.raises(RuntimeError, match='DEPLOY_DATABASE_URL is required'):
        module.require_env('DEPLOY_DATABASE_URL')

    monkeypatch.setenv('DEPLOY_DATABASE_URL', 'from-env')
    assert module.require_env('DEPLOY_DATABASE_URL') == 'from-env'


def test_full_deploy_script_rejects_missing_known_hosts_and_root_user(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_deploy_production_module()

    monkeypatch.delenv('DEPLOY_USER', raising=False)
    with pytest.raises(RuntimeError, match='DEPLOY_USER is required'):
        module.require_deploy_user()

    monkeypatch.setenv('DEPLOY_USER', 'root')
    with pytest.raises(RuntimeError, match='least-privilege non-root'):
        module.require_deploy_user()

    monkeypatch.setenv('DEPLOY_USER', 'deploy;rm')
    with pytest.raises(RuntimeError, match='safe Linux username'):
        module.require_deploy_user()

    monkeypatch.setenv('DEPLOY_USER', 'deploy')
    assert module.require_deploy_user() == 'deploy'

    monkeypatch.setenv('DEPLOY_KNOWN_HOSTS', str(tmp_path / 'missing_known_hosts'))
    with pytest.raises(RuntimeError, match='DEPLOY_KNOWN_HOSTS must point to an existing file'):
        module.require_existing_file_env('DEPLOY_KNOWN_HOSTS')


def test_incremental_deploy_script_uses_key_based_known_hosts_non_root_ssh() -> None:
    source = _read('backend/scripts/deploy_zxtf_update.py')

    assert 'ZXTF_DEPLOY_PASSWORD' not in source
    assert 'ZXTF_DEPLOY_SSH_KEY_PATH' in source
    assert 'ZXTF_DEPLOY_KNOWN_HOSTS' in source
    assert 'ZXTF_DEPLOY_USER' in source
    assert 'least-privilege non-root' in source
    assert 'paramiko.RejectPolicy()' in source
    assert 'AutoAddPolicy' not in source
    assert 'key_filename=ssh_key_path' in source
    assert 'password=' not in source
    assert 'allow_agent=False' in source
    assert 'look_for_keys=False' in source


@pytest.mark.frontend_contract
def test_e2e_helpers_use_mocked_login_flow_instead_of_storage_token_seed() -> None:
    helper_paths = [
        'frontend/e2e/helpers/review-mocks.js',
        'frontend/e2e/helpers/unified-entry-mocks.js',
    ]
    for helper_path in helper_paths:
        source = _read(helper_path)
        assert "localStorage.setItem('aluminum_bypass_token'" not in source
        assert "sessionStorage.setItem('aluminum_bypass_token'" not in source
        assert "page.evaluate(({ token" not in source
        assert "addInitScript(({ token" not in source

    login_helper = _read('frontend/e2e/helpers/mock-login.js')
    audit = _read('docs/audits/2026-05-02-cleanup-round2-test-audit.md')

    assert "**/api/v1/auth/login" in login_helper
    assert 'login-username' in login_helper
    assert 'login-password' in login_helper
    assert 'login-submit' in login_helper
    assert '| S10 |' not in audit
    assert '| R76 |' in audit


def test_frontend_source_contract_tests_are_marker_isolated_from_backend_suite() -> None:
    pytest_ini = _read('backend/pytest.ini')
    audit = _read('docs/audits/2026-05-02-cleanup-round2-test-audit.md')

    assert 'addopts = -m "not frontend_contract"' in pytest_ini
    assert 'frontend_contract: frontend source contract checks kept out of the default backend suite' in pytest_ini
    assert '| B01 |' not in audit
    assert '| R77 |' in audit

    file_level_contracts = [
        'backend/tests/test_mobile_entry_copy_consistency.py',
        'backend/tests/test_reference_command_center_spec.py',
        'backend/tests/test_frontend_refactor_blueprint.py',
    ]
    for path in file_level_contracts:
        source = _read(path)
        assert 'import pytest' in source
        assert 'pytestmark = pytest.mark.frontend_contract' in source

    rebranding_source = _read('backend/tests/test_rebranding.py')
    assert '@pytest.mark.frontend_contract\ndef test_user_facing_brand_strings_are_updated' in rebranding_source

    quick_docs_source = _read('backend/tests/test_quick_cloud_trial_docs_and_ops.py')
    assert '@pytest.mark.frontend_contract\ndef test_e2e_helpers_use_mocked_login_flow_instead_of_storage_token_seed' in quick_docs_source


def test_compose_passes_external_runtime_flags_to_backend() -> None:
    source = _read('docker-compose.yml')

    required_backend_env = [
        'MOBILE_DATA_ENTRY_MODE: ${MOBILE_DATA_ENTRY_MODE:-manual_only}',
        'MOBILE_SCAN_ASSIST_ENABLED: ${MOBILE_SCAN_ASSIST_ENABLED:-false}',
        'MOBILE_MES_DISPLAY_ENABLED: ${MOBILE_MES_DISPLAY_ENABLED:-false}',
        'MES_MVC_BASE_URL: ${MES_MVC_BASE_URL:-}',
        'MES_MVC_USERNAME: ${MES_MVC_USERNAME:-}',
        'MES_MVC_PASSWORD: ${MES_MVC_PASSWORD:-}',
        'MES_MVC_TIMEOUT_SECONDS: ${MES_MVC_TIMEOUT_SECONDS:-8}',
        'DINGTALK_ENABLED: ${DINGTALK_ENABLED:-false}',
        'LLM_ENDPOINT_ID: ${LLM_ENDPOINT_ID:-}',
        'LLM_IMAGE_MODEL: ${LLM_IMAGE_MODEL:-}',
        'LLM_IMAGE_ENDPOINT_ID: ${LLM_IMAGE_ENDPOINT_ID:-}',
        'APP_CONNECTION_PUSH_MODE: ${APP_CONNECTION_PUSH_MODE:-disabled}',
    ]
    for expected in required_backend_env:
        assert expected in source


def test_ci_workflow_generates_ephemeral_secrets_and_scoped_upload_permissions() -> None:
    source = _read('.github/workflows/ci.yml')

    assert 'Round10CiAdmin!2026' not in source
    assert 'ci-very-strong-secret-key-0123456789abcdef' not in source
    assert 'chmod 777' not in source
    assert 'openssl rand -hex 32' in source
    assert 'CI_ADMIN_PASSWORD="CiAdmin-$(openssl rand -hex 12)!"' in source
    assert '::add-mask::$CI_SECRET_KEY' in source
    assert '::add-mask::$CI_ADMIN_PASSWORD' in source
    assert 'PLAYWRIGHT_PASSWORD=$CI_ADMIN_PASSWORD' in source
    assert 'docker compose build backend' in source
    assert 'backend_uid="$(docker compose run --rm --no-deps --entrypoint id backend -u)"' in source
    assert 'sudo install -d -m 0770 -o "$backend_uid" -g "$backend_gid" backend/uploads' in source


def test_cleanup_audit_marks_deterministic_orchestration_boundary_resolved() -> None:
    source = _read('docs/audits/2026-05-02-cleanup-round2-test-audit.md')

    assert '| B21 |' not in source
    assert '| R71 |' in source
    assert '`backend/app/services/deterministic_orchestration_service.py`' in source
    assert '`backend/tests/test_deterministic_orchestration_service.py`' in source
    assert '无引用无测试' not in source


def test_backend_smoke_scripts_are_replaced_by_testclient_coverage() -> None:
    scripts_dir = REPO_ROOT / 'backend/scripts'
    audit = _read('docs/audits/2026-05-02-cleanup-round2-test-audit.md')

    assert list(scripts_dir.glob('test_*.py')) == []
    assert not (scripts_dir / 'smoke_entry_fields.py').exists()
    assert not (scripts_dir / 'smoke_shift.py').exists()
    assert '| S12 |' not in audit
    assert '| R72 |' in audit
    assert '`backend/tests/test_qr_login.py`' in audit
    assert '后端手工测试脚本打固定 localhost 和 live token' not in audit


def test_qr_pdf_artifacts_are_not_tracked_in_repository() -> None:
    audit = _read('docs/audits/2026-05-02-cleanup-round2-test-audit.md')
    gitignore = _read('.gitignore')
    ops = _read('docs/快速试跑运维手册.md')

    assert not (REPO_ROOT / 'docs/role_qr_codes.pdf').exists()
    assert not (REPO_ROOT / 'docs/workshop_qr_codes.pdf').exists()
    assert 'docs/*qr_codes.pdf' in gitignore
    assert '/manage/admin/qr-print' in ops
    assert '二维码打印制品不提交到 Git' in ops
    assert '| S14 |' not in audit
    assert '| R73 |' in audit
    assert '`docs/role_qr_codes.pdf`' in audit
    assert '`docs/workshop_qr_codes.pdf`' in audit


def test_highres_reference_images_have_size_budget_and_audit_record() -> None:
    audit = _read('docs/audits/2026-05-02-cleanup-round2-test-audit.md')
    manifest = _read('docs/ui-reference/REFERENCE_MANIFEST.md')

    assert '| S15 |' not in audit
    assert '| R74 |' in audit
    assert '`docs/ui-reference/highres/*.png`' in audit
    assert '`backend/tests/test_reference_command_center_spec.py`' in audit
    assert '尺寸门槛' in manifest
    assert '1672 x 941' in manifest
    assert '体积门槛' in manifest
    assert '<= 5.6 MB' in manifest


def test_release_freeze_checklist_requires_clean_worktree_and_github_remote() -> None:
    source = _read('docs/发布冻结基线清单.md')

    assert '`git status --short` 不再包含测试缓存、临时截图和误生成目录' in source
    assert 'GitHub 远端已接入，云主机可直接拉代码' in source
    assert '以 `2026-04-20` 本地最新验证为准' not in source
    assert '387 passed' not in source
    assert '→ `4 passed`' not in source
    assert '`python -m pytest backend/tests -q --durations=10` → `675 passed，124 deselected，30 warnings`' in source
    assert '`python -m pytest backend/tests -m frontend_contract -q` → `124 passed，675 deselected`' in source
    assert '`npm --prefix frontend test` → `119 passed`' in source
    assert '`npm --prefix frontend run build` → 通过' in source
    assert '`git diff --check` → 通过' in source


def test_quick_trial_docs_require_github_and_single_workshop_rollout() -> None:
    deployment = _read('docs/部署文档.md')
    readme = _read('README.md')
    uat = _read('docs/现场UAT清单.md')
    ops = _read('docs/快速试跑运维手册.md')

    assert 'GitHub' in deployment
    assert 'git pull' in deployment
    assert '一个车间' in deployment
    assert '企业微信正式入口先不接' in deployment
    assert '工作区仍有较多未提交改动' not in deployment
    assert '发布冻结以 `main == origin/main` 且 `git status --short` 为空为前提' in deployment
    assert '现场主数据已完成' not in deployment
    assert '现场主数据已具备初始化脚本与 `/readyz` 闸门' in deployment
    assert '正式试跑前需按目标车间复核车间、班次、角色、模板、专项 owner、管理员账号' in deployment
    assert '现场主数据和试点账号尚需最终过一遍' in deployment
    assert '1 个管理员' in uat
    assert '1 个车间的主操或机台账号 1 人' in uat
    assert '专项 owner' in uat
    assert 'GitHub / 上云前封装准备' in readme
    assert 'UI 语义收口施工' not in readme
    assert '本地可运行 + 关键验证基线已通过 + 可进入发布冻结与单车间试跑准备' in readme
    assert './scripts/deploy_trial.sh' in ops
    assert './scripts/check_trial_stack.sh' in ops
    assert '默认检查 `https://localhost`' in ops
    assert 'TRIAL_BASE_URL=https://你的域名 ./scripts/deploy_trial.sh' in ops
    assert './scripts/backup_db.sh' in ops
    assert '备份文件不存在或 `db` 未运行' in ops
    assert 'hard_gate_passed=true' in ops
    assert '若失败会自动输出关键容器状态与后端/nginx日志片段' in ops
    assert '若 `/readyz` 未通过，会输出最后一次 readyz 响应' in ops
    assert '容器状态和后端/nginx 日志由 `deploy_trial.sh` 包裹失败时输出' in ops
    assert './scripts/go_live_gate.sh' in ops
    assert '一键上线闸门' in ops
    assert '--skip-ai' in ops
    assert '--skip-role-smoke' in ops
    assert '--require-external' in ops
    assert 'docker compose exec -T backend python scripts/check_statistics_module_ready.py' in ops
    assert 'MES_ADAPTER=mvc' in ops
    assert 'DINGTALK_ENABLED=true' in ops
    assert 'APP_CONNECTION_PUSH_MODE=enabled' in ops
    assert '不要把上述真实值写入文档或提交到 GitHub' in ops


def test_current_deploy_state_tracks_current_head_and_validation_evidence() -> None:
    state = _read('docs/deploy/current-state.md')
    audit = _read('docs/audits/2026-05-02-cleanup-round2-test-audit.md')

    assert '当前记录基准：当前 `main` HEAD' in state
    assert '`python -m pytest backend/tests -q`：723 passed，124 deselected，31 warnings' in state
    assert '`python -m pytest backend/tests/test_coil_entry_auto_calc.py -q`：6 passed' in state
    assert '`python -m pytest backend/tests/test_coil_entry_auto_calc.py backend/tests/test_realtime_service.py backend/tests/test_factory_command_service.py backend/tests/test_workshop_reporting_status.py -q`：32 passed' in state
    assert '`python -m pytest backend/tests/test_daily_production_canonical_service.py backend/tests/test_legacy_data_profile_service.py -q`：23 passed' in state
    assert '`python -m pytest backend/tests/test_import_service_daily_production.py backend/tests/test_daily_production_canonical_service.py -q`：8 passed' in state
    assert '`python -m pytest backend/tests/test_import_service_contract_report.py backend/tests/test_import_service_yield_matrix.py -q`：2 passed' in state
    assert '`python -m pytest backend/tests/test_dingtalk_cli.py backend/tests/test_statistics_module_ready_script.py backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_current_deploy_state_tracks_current_head_and_validation_evidence backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_exec_plan_tracks_phase_progress_without_hiding_external_gates -q`：17 passed' in state
    assert '`python -m pytest backend/tests/test_mobile_shift_report_machine_binding.py backend/tests/test_coil_entry_auto_calc.py backend/tests/test_factory_command_service.py backend/tests/test_realtime_service.py -q`：31 passed' in state
    assert '`python -m pytest backend/tests/test_mobile_shift_report_machine_binding.py backend/tests/test_factory_command_routes.py backend/tests/test_factory_command_service.py backend/tests/test_realtime_service.py -q`：36 passed' in state
    assert '`python -m pytest backend/tests/test_aggregator_agent.py -q`：7 passed' in state
    assert '`python -m pytest backend/tests/test_mes_sync_service.py backend/tests/test_mes_mvc_preflight_script.py -q`：11 passed' in state
    assert '`python -m pytest backend/tests/test_mes_sync_service.py backend/tests/test_mes_mvc_preflight_script.py backend/tests/test_mvc_mes_adapter.py -q`：19 passed' in state
    assert '`python -m pytest backend/tests/test_factory_command_service.py -q`：20 passed' in state
    assert '`python -m pytest backend/tests/test_reconciliation_granularity.py -q`：3 passed' in state
    assert '`python -m pytest backend/tests -m frontend_contract -q`：124 passed，675 deselected' in state
    assert '工厂指挥中心已上线混合来源消费' in state
    assert '`overview`、`workshops`、`machine-lines` 仍会叠加当天 `mobile_coil_agg` 本地卷级直录' in state
    assert '普通移动班次报表同步管理端数据时也会读取机列绑定' in state
    assert '`ShiftProductionData.equipment_id`' in state
    assert '工厂指挥 `machine-lines` API 响应模型已保留 `machine_binding_status`' in state
    assert '外部联通 readiness 已显式提示钉钉人员绑定缺口' in state
    assert '`DINGTALK_NO_BOUND_USERS` warning' in state
    assert 'MES 同步批内重复投影已收口' in state
    assert '`mes_follow_cards` / `mes_dispatch` 按投影后的 `coil_id` 去重' in state
    assert 'MES MVC 会话恢复已增强' in state
    assert '会清理 cookie/token 后重新登录并重放请求' in state
    assert 'MES 投影同步已隔离非数据库单源失败' in state
    assert '单个外部接口失败返回该源 `failed` stats' in state
    assert '历史 `每日产量` 工作簿已接入只读 canonical 预览' in state
    assert '超过 `10000t` 的日产量标为疑似 kg 口径' in state
    assert '真实日报导入门禁' in state
    assert '`import_type=daily_production_report`' in state
    assert '`daily_output_tons=1935.649`' in state
    assert '`shift_production_data_rows=0`' in state
    assert '`batch_no=IMP-20260506130735-d4f557`' in state
    assert '`shift_rows_delta=0`' in state
    assert '生产环境暂未安装 `xlrd`' in state
    assert '历史 `每日产量` 映射门禁已接入只读预览' in state
    assert '`ready_rows=7`' in state
    assert '`needs_equipment_mapping_rows=0`' in state
    assert '`unresolved_rows=9`' in state
    assert '`冷轧/1650`' in state
    assert '`在线退火/园区北线`' in state
    assert '`GET /api/v1/imports/daily-production/mapping-preview`' in state
    assert '每日产量/映射门禁' in state
    assert '映射门禁未解析行已增加只读候选主数据提示' in state
    assert '`DAILY_PRODUCTION_MAPPING_RULES`' in state
    assert '`冷轧/1650`、`冷轧/1850` 暂无直接 active 机列' in state
    assert '管理端实时态势已增加“填报接入”只读条' in state
    assert '`formal_entry_count`' in state
    assert '`draft_entry_count`' in state
    assert '`draft_count`' in state
    assert '按卷填报提交口径已收紧' in state
    assert '`mobile_coil_agg` 只聚合 `submitted/verified/approved` 卷明细' in state
    assert '重算时没有合格源卷会 void 旧聚合' in state
    assert '28 行来源卷全为 draft 的 `mobile_coil_agg` 置为 `voided`' in state
    assert '`active_mobile_coil_agg=0`' in state
    assert '`draft_only_candidate_count=0`' in state
    assert '管理端未显示当前测试填报的直接原因已复核' in state
    assert '`work_order_entries` 仍为 `draft=156`' in state
    assert '`mobile_shift_reports` 为 `draft=3`' in state
    assert '`ShiftProductionData` 仅有 `mobile_coil_agg/voided=28`' in state
    assert "当前代码已包含 `entry_status='submitted'`" in state
    assert '管理端实时聚合已支持“填报事实 + MES 归属”配对' in state
    assert '`npm --prefix frontend test`：124 passed' in state
    assert '`npm --prefix frontend run build`：通过' in state
    assert '`git diff --check HEAD~1..HEAD`：通过' in state
    assert '最近一次 ECS 修复验证：2026-05-06 23:16 左右。' in state
    assert '本轮已部署 `main@c880265`' in state
    assert '本轮已部署 `main@e97f5ee`' in state
    assert '管理端实时态势新增“车间填报接入”三段图和“草稿待归属”汇总' in state
    assert '`LiveDashboard-0fQW5w4R.js` / `LiveDashboard-BwV9nvGm.css` 已包含 `fill-workshop-flow`、`车间填报接入` 和 `pending_assignment`' in state
    assert '`pending_assignment.entry_count=17`' in state
    assert '`missing_machine_count=17`' in state
    assert '`missing_shift_count=0`' in state
    assert '`factory_output=0.0`' in state
    assert '当前车间填报接入分布为 `铸三车间 0/4/4`、`2050冷轧车间 0/9/9`、`精整车间 0/4/4`' in state
    assert '2026-05-07 08:50 左右跨业务日巡检发现 `/readyz` 被 `SCHEDULE_EMPTY` 阻断' in state
    assert '目标日 `2026-05-07` 的 `schedule_row_count=0`，但 `mes_sync.last_run_status=success`' in state
    assert '已在生产机执行 `PYTHONPATH=. .venv/bin/python scripts/init_real_master_data.py`' in state
    assert '`default pilot schedule synced: 195`' in state
    assert '复验 `/readyz` 返回 `status=ready`、`target_date=2026-05-07`、`schedule_row_count=195`' in state
    assert '`node node_modules/vite/bin/vite.js build --configLoader native`' in state
    assert '`formal_entry_count=0`' in state
    assert '`draft_entry_count=17`' in state
    assert '`total_entry_count=17`' in state
    assert '不进入机列产量吨数' in state
    assert '管理端实时态势第一屏新增“班次产量节奏”' in state
    assert '`LiveDashboard-BvJspizJ.js` / `LiveDashboard-CtQL3H_9.css` 已包含 `班次产量节奏` 和 `live-shift-rhythm`' in state
    assert '管理端实时态势第一屏新增“卷级直录分布”' in state
    assert '`LiveDashboard-CO0mybtJ.js` / `LiveDashboard-BHO0nfza.css` 已包含 `卷级直录分布`、`live-output-distribution` 和 `未绑定`' in state
    assert '管理端实时态势第一屏新增“未绑定填报归属”' in state
    assert '`LiveDashboard-BSehAJcz.js` / `LiveDashboard-DYSwQp49.css` 已包含 `未绑定填报归属`、`live-unbound-fill` 和 `绑定账号`' in state
    assert '生产 Playwright 视觉验证已覆盖 `http://8.140.218.13/manage/admin/settings?desktop=1`' in state
    assert '桌面 `1440x900` 与手机 `390x844` 均显示“未绑定填报归属”、`120460.00`、`2 个车间`、`3 条机列` 与“绑定账号”' in state
    assert '页面无横向溢出' in state
    assert '管理端实时态势主聚合接入 `mobile_coil_agg` 卷级直录 fallback' in state
    assert '`LiveDashboard-CeSbJ94X.js` 已包含 `卷级直录` 和 `local_shift_data`' in state
    assert '管理端实时态势页新增“外部联通闸门”卡' in state
    assert '`LiveDashboard-BXTGpXX4.js` / `dashboard-D6EhilfF.js` 已包含 `外部联通闸门`、`接口待返回`、`external-readiness` 和 `hard_issues`' in state
    assert '管理端外部 MES 状态条显示运行配置缺口' in state
    assert '`LiveDashboard-BNcHeouG.js` 已包含 `required_env`、`缺少配置` 和 `MES_MVC_BASE_URL`' in state
    assert '管理端车间机列页支持把未绑定 `mobile_coil_agg` 实时填报按车间/班次归入“未绑定机列”' in state
    assert '`MachineLineScreen-DL7qgGJc.js` / `MachineLineScreen-FDnJ2hSk.css` 已包含 `未绑定机列`、`machine_binding_status` 和 `fc-line__bar`' in state
    assert '管理端用户管理页支持绑定机列' in state
    assert '`UserManagement-CvyvNRYK.js` 已包含 `绑定机列` 和 `bound_machine_id`' in state
    assert '管理端用户管理页支持按机列绑定状态和具体机列筛选账号' in state
    assert '`UserManagement-B4GmUedd.js` 已包含 `绑定状态`、`machine_binding` 和 `boundMachineId`' in state
    assert '`machine_binding=bound total=136`、`machine_binding=unbound total=198`、`bound_machine_id=<已绑定机列> total=1`' in state
    assert '管理端“未绑定填报归属”面板的“绑定账号”入口会带 `machine_binding=unbound` 进入用户管理' in state
    assert '`LiveDashboard-CiAkZ4yu.js` / `UserManagement-97qO9yGl.js` 已包含 `machine_binding` 和 `bound_machine_id`' in state
    assert '`/manage/admin/users?machine_binding=unbound&desktop=1`' in state
    assert '`/api/v1/users/?machine_binding=unbound&skip=0&limit=10` 返回 `total=198`' in state
    assert '新增 `backend/scripts/check_mes_mvc_preflight.py`' in state
    assert '不回显密钥地检查 MES MVC 配置、登录页 token 与可选登录链路' in state
    assert '`missing_env=MES_ADAPTER,MES_MVC_BASE_URL,MES_MVC_USERNAME,MES_MVC_PASSWORD`' in state
    assert '`login_page.status=skipped`、`login.status=skipped`' in state
    assert '管理端实时态势第一屏新增“机列归属率”动态视图' in state
    assert '`LiveDashboard-CCWtW8qw.js` / `LiveDashboard-DxaRmkzM.css` 已包含 `机列归属率`、`live-machine-ownership` 和 `buildMachineOwnershipSummary`' in state
    assert '`0 已归属 · 3 待归属`、`120460.00`、`3 产出机列`' in state
    assert '管理端实时聚合 API 显式返回 `machine_binding_status`' in state
    assert '`all_positive_rows_have_binding_status=true`' in state
    assert '前端与 AI 分析不再需要从负数 `machine_id` 反推归属状态' in state
    assert '管理端运维页新增外部 MES 状态条' in state
    assert '`mes-connection-strip`、`外部 MES` 和 `MES_MVC_BASE_URL`' in state
    assert 'MES 同步批内重复投影修复已上线' in state
    assert '本轮已部署 `main@f2350d6`' in state
    assert '`overview_source=mixed`、`overview_total_input=149510.0`、`overview_total_output=120460.0`' in state
    assert '`machine_lines_len=56`、`unbound_machine_lines_len=5`、`unbound_output_total=120460.0`' in state
    assert '本轮已部署 `main@bff456b`' in state
    assert '`raw_mobile_coil_agg_output_kg=120460.0`' in state
    assert '`overview_total_input_tons=149.51`、`overview_total_output_tons=120.46`' in state
    assert '`unbound_output_tons=120.46`、`live_factory_output=120.46`' in state
    assert '本轮已部署 `main@182508f`' in state
    assert '`reconciliation_output_total_tons=120.46`' in state
    assert '`JZ/NIGHT=37.25`、`LZ2050/DAY=9.1`、`LZ2050/NIGHT=74.11`' in state
    assert '本轮已部署 `main@fd96768`' in state
    assert '`aggregator_output_tons=250.0`、`aggregator_input_tons=260.0`' in state
    assert '本轮已部署 `main@1a1139c`' in state
    assert '`schema_preserves_machine_binding_status=true`' in state
    assert '`checked_equipment_id=12`、`rollback_mobile_shift_report_equipment_id=12`' in state
    assert '`mobile_shift_report_binding_ok=true`' in state
    assert '本轮已拉取 `main@8678dc7`' in state
    assert '`scripts/dingtalk_cli.py contacts --department-id 1 --json` 只读诊断' in state
    assert '`department_access=false`、`dry_run_only=true`' in state
    assert '本轮已部署 `main@180d84d`' in state
    assert '`warning_issues=DINGTALK_NO_BOUND_USERS`' in state
    assert '`active_dingtalk_user_count=0`、`active_dingtalk_employee_count=0`' in state
    assert '本轮已部署 `main@f137662`' in state
    assert '`warning_issues=DINGTALK_NO_BOUND_USERS,DINGTALK_CONTACTS_PERMISSION_MISSING`' in state
    assert '`dingtalk_contacts_missing_scope=qyapi_get_department_member`' in state
    assert '本轮已部署 `main@d5da2ca`' in state
    assert '`valid_business_date=2026-05-03`' in state
    assert '`missing_business_date=null`' in state
    assert '普通小数 `1.14` 不会再被当作日期' in state
    assert '本轮已部署 `main@cc22abd`' in state
    assert '`sync_mes_projection` 逐来源返回 `success/failed`' in state
    assert '`mes_sync.upserted_count=50`' in state
    assert '本轮已部署 `main@1aa32bf`' in state
    assert '历史 `每日产量` 映射预览已上线' in state
    assert '`ImportBatch id=1` 返回 `total_rows=16`、`ready_rows=7`' in state
    assert '`coil_snapshots fetched=50 upserted=50`' in state
    assert '`mes_follow_cards fetched=50 upserted=50`' in state
    assert '`mes_dispatch fetched=50 upserted=50`' in state
    assert '生产 MES MVC 预检已通过' in state
    assert '`adapter=mvc`、`mvc_configured=true`、`missing_env=[]`' in state
    assert '`login_page.status=reachable`、`token_present=true`、`login.status=success`' in state
    assert '`mes_coil_snapshots_count=52`' in state
    assert '`mes_machine_line_snapshots_count=50`' in state
    assert '生产内部 workflow 开关已启用' in state
    assert '`backups/.env.workflow-backup-20260506-170534`' in state
    assert '`WORKFLOW_ENABLED=true`' in state
    assert '`NullWorkflowPublisher` 接收 workflow 事件' in state
    assert '生产钉钉配置已启用' in state
    assert '`backups/.env.dingtalk-backup-20260506-171247`' in state
    assert '`DINGTALK_ENABLED=true`' in state
    assert '`token_received=true`' in state
    assert '`active_users_with_dingtalk_id=0`' in state
    assert '生产只读拉取钉钉部门用户失败' in state
    assert '`qyapi_get_department_member` 权限' in state
    assert '命令只输出统计和权限状态，不回显成员姓名、手机号、userid 或 token' in state
    assert '还不能宣称工作通知已送达' in state
    assert 'SSH：`root@8.140.218.13` key 登录可用。' in state
    assert '远端仓库：`/srv/aluminum-bypass` 已快进到当前 `main` HEAD' in state
    assert '宿主机 nginx + `aluminum-bypass.service` + 宿主机 PostgreSQL' in state
    assert '`http://8.140.218.13/readyz`：HTTP 200，返回后端 readyz JSON。' in state
    assert '`http://8.140.218.13/manage/factory/machine-lines`：HTTP 200，返回前端 SPA。' in state
    assert '`mobile_coil_entries=17` 历史明细仍保留' in state
    assert '`active_mobile_coil_agg=0`、`draft_only_candidate_count=0`' in state
    assert '`overview_source=mes_projection`' in state
    assert '`factory_command_total_output_tons=0`' in state
    assert '`overview_workshop_summary_len=0`' in state
    assert '`machine_lines_len=51`' in state
    assert '`local_source_line_count=0`' in state
    assert '`/api/v1/aggregation/live?business_date=2026-05-06` 当前服务探针返回 `data_source=work_order_runtime`' in state
    assert '`factory_output=0.0`、`positive_live_cell_count=0`' in state
    assert '不再显示历史 draft-only 临时机列产量' in state
    assert '历史 `120460.0kg -> 120.46t` 只作为已验证过的折吨行为证据' in state
    assert '未在生产库触发自动日报生成或写入新日报' in state
    assert '2026-05-06 14:50 左右刷新 MES 前置核对时' in state
    assert '耗时约 `0.268s`' in state
    assert '当时生产运行配置中 `MES_ADAPTER` 等效为 `null`' in state
    assert '2026-05-06 16:55 左右生产 MES 已切到 MVC 配置并完成同步' in state
    assert '`MES_ADAPTER=mvc`、`mes_ready=true`' in state
    assert '`hard_issue_codes=LLM_DISABLED,APP_CONNECTION_DISABLED`' in state
    assert '钉钉人员绑定阻塞已定位到外部应用权限' in state
    assert '`environment=production`' in state
    assert '`hard_gate_passed=true`' in state
    assert '`mes_sync=idle`' in state
    assert '`mes_sync.configured=true`' in state
    assert '`mes_sync.last_run_status=success`' in state
    assert '`mes_sync.fetched_count=50`' in state
    assert '`mes_sync.upserted_count=50`' in state
    assert '`mes_sync.action_required=none`' in state
    assert '`workflow_enabled=true`' in state
    assert '`dingtalk_enabled=true`' in state
    assert '`active_mobile_user_count=329`' in state
    assert '`active_workshop_count=12`' in state
    assert '`active_equipment_count=136`' in state
    assert '`FACTORY-UM`、`FACTORY-IK`、`FACTORY-CT` 绑定到 `CPK`' in state
    assert '`virtual_role_qr_active=96`，`virtual_role_qr_bound=96`' in state
    assert '`xtmijd.com` 当前只返回 SOA，无 A 记录' in state
    assert '`www.xtmijd.com` 已解析到 `8.140.218.13`' in state
    assert '`Non-compliance ICP Filing` 403' in state
    assert '阻塞在域名备案/接入合规层' in state
    assert '`LLM_DISABLED`' in state
    assert '但 `MES_UNCONFIGURED`、`WORKFLOW_DISABLED` 与 `DINGTALK_DISABLED` 已解除' in state
    assert '2026-05-06 08:07 左右从本机探测 `xt-aluminnum.vercel.app:443` TCP 不通' in state
    assert 'Vercel 当前只能作为前端静态部署证据' in state
    assert '9130fb3 docs: 记录 Vercel 主线部署状态' not in state
    assert '678 passed，124 deselected，30 warnings' not in state
    assert '671 passed' not in state
    assert '82 passed' not in state
    assert '本轮后续只做 workflow 运行日志措辞收口' not in state
    assert '待处理问题清单当前为空' in audit
    assert '669 passed，124 deselected，30 warnings' in audit
    assert '124 passed，669 deselected' in audit
    assert '114 passed' in audit
    assert '513 passed / 5 failed' not in audit


def test_external_readiness_docs_expose_env_template_command() -> None:
    state = _read('docs/deploy/current-state.md')
    ops = _read('docs/快速试跑运维手册.md')
    script = _read('backend/scripts/check_statistics_module_ready.py')

    assert '--env-template' in script
    assert 'python scripts/check_statistics_module_ready.py --env-template' in state
    assert 'python scripts/check_statistics_module_ready.py --env-template' in ops
    assert '不回显现有密钥' in state
    assert '不要把包含密钥的 `.env` 提交到 Git' in ops
    for expected in [
        'LLM_ENABLED=true',
        'LLM_API_BASE=...',
        'LLM_API_KEY=...',
        'LLM_MODEL=...',
        '`hard_gate_passed=false`',
        '`module_usable=false`',
        '`external_connection_enabled=false`',
        '`mes_adapter=mvc`、`mes_ready=true`',
        '`warning_issues=DINGTALK_NO_BOUND_USERS`',
        '`active_dingtalk_user_count=0`、`active_dingtalk_employee_count=0`',
    ]:
        assert expected in state


def test_quick_trial_ops_scripts_exist_with_expected_commands() -> None:
    deploy = _read('scripts/deploy_trial.sh')
    check = _read('scripts/check_trial_stack.sh')
    gate = _read('scripts/go_live_gate.sh')
    launcher = _read('scripts/launch_cloud_trial.sh')

    assert 'for compose_file in docker-compose.yml docker-compose.prod.yml; do' in deploy
    assert 'DRY_RUN=0' in deploy
    assert '未检测到 ${compose_file}，请在项目根目录执行部署脚本并确保 compose 文件存在。' in deploy
    assert 'command -v docker' in deploy
    assert 'docker compose version' in deploy
    assert 'docker info' in deploy
    assert 'command -v curl' in deploy
    assert '未检测到 docker 命令，请先安装 Docker 后再执行部署脚本。' in deploy
    assert 'docker compose 不可用，请先安装并启用 Docker Compose Plugin（docker compose）。' in deploy
    assert 'Docker daemon 未启动，请先启动 Docker 服务后再执行部署脚本。' in deploy
    assert '未检测到 curl 命令。请先安装 curl（健康检查脚本依赖）后再执行部署脚本。' in deploy
    assert deploy.find('command -v docker') < deploy.find('if [ ! -f ".env" ];')
    assert deploy.find('command -v docker') < deploy.find('if [ ! -s "ssl/cert.pem" ];')
    assert "if [ ! -f \".env\" ];" in deploy
    assert 'if [ ! -s "ssl/cert.pem" ];' in deploy
    assert 'if [ ! -s "ssl/key.pem" ];' in deploy
    assert 'ssl/cert.pem（文件不存在或为空）' in deploy
    assert 'ssl/key.pem（文件不存在或为空）' in deploy
    assert 'grep -q "BEGIN CERTIFICATE" "ssl/cert.pem"' in deploy
    assert 'grep -q "BEGIN" "ssl/key.pem"' in deploy
    assert 'grep -q "PRIVATE KEY" "ssl/key.pem"' in deploy
    assert 'BEGIN CERTIFICATE' in deploy
    assert 'ssl/cert.pem 内容可能错误' in deploy
    assert 'ssl/key.pem 内容可能错误' in deploy
    assert 'get_env_value()' in deploy
    assert 'require_env_value()' in deploy
    assert 'APP_ENV=production' in deploy
    assert 'APP_ENV_VALUE="$(get_env_value APP_ENV' in deploy
    assert 'require_env_value POSTGRES_PASSWORD' in deploy
    assert 'require_env_value SECRET_KEY' in deploy
    assert 'require_env_value INIT_ADMIN_PASSWORD' in deploy
    assert 'require_env_value CORS_ORIGINS' in deploy
    assert 'is_weak_secret_key()' in deploy
    assert 'is_weak_admin_password()' in deploy
    assert 'if is_weak_secret_key "$SECRET_KEY_VALUE"; then' in deploy
    assert 'if is_weak_admin_password "$INIT_ADMIN_PASSWORD_VALUE"; then' in deploy
    assert 'SECRET_KEY 过弱：长度必须 >= 32' in deploy
    assert 'INIT_ADMIN_PASSWORD 过弱：长度必须 >= 12' in deploy
    assert 'CHANGE_ME' in deploy
    assert 'grep -q "CHANGE_ME"' in deploy
    assert 'python scripts/generate_env.py --app-env production --domain <your-domain>' in deploy
    assert 'docker compose -f docker-compose.yml -f docker-compose.prod.yml config' in deploy
    assert 'docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build' in deploy
    assert 'docker compose -f docker-compose.yml -f docker-compose.prod.yml ps' in deploy
    assert 'TRIAL_BASE_URL="${TRIAL_BASE_URL:-${BASE_URL:-https://localhost}}"' in deploy
    assert './scripts/check_trial_stack.sh "$TRIAL_BASE_URL"' in deploy
    assert 'if ! ./scripts/check_trial_stack.sh "$TRIAL_BASE_URL"; then' in deploy
    assert '--dry-run|--check-only' in deploy
    assert 'DRY RUN：仅做预检，不执行发布动作。' in deploy
    assert '健康检查失败，输出关键诊断信息' in deploy
    assert 'docker compose -f docker-compose.yml -f docker-compose.prod.yml logs backend --tail 160' in deploy
    assert 'docker compose -f docker-compose.yml -f docker-compose.prod.yml logs nginx --tail 160' in deploy
    assert '快速试跑健康检查通过' in deploy
    assert 'PARSED_BASE_URL=""' in check
    assert 'BASE_URL="${PARSED_BASE_URL:-${BASE_URL:-https://localhost}}"' in check
    assert 'READY_RETRIES="${READY_RETRIES:-24}"' in check
    assert 'READY_INTERVAL_SECONDS="${READY_INTERVAL_SECONDS:-5}"' in check
    assert 'DRY_RUN=0' in check
    assert 'case "$arg" in' in check
    assert '--dry-run|--check-only' in check
    assert 'DRY RUN：仅做预检，不发起网络探测。' in check
    assert 'exit 1\n      ;;\n      fi' not in check
    assert 'for compose_file in docker-compose.yml docker-compose.prod.yml; do' in check
    assert '未检测到 ${compose_file}，请在项目根目录执行健康检查脚本并确保 compose 文件存在。' in check
    assert 'if [ ! -f ".env" ]; then' in check
    assert '未检测到 .env，请先在项目根目录准备 .env 后再执行健康检查脚本。' in check
    assert 'command -v docker' in check
    assert 'docker compose version' in check
    assert 'docker info' in check
    assert '未检测到 docker 命令，请先安装 Docker 后再执行健康检查脚本。' in check
    assert 'docker compose 不可用，请先安装并启用 Docker Compose Plugin（docker compose）后再执行健康检查脚本。' in check
    assert 'Docker daemon 未启动，请先启动 Docker 服务后再执行健康检查脚本。' in check
    assert 'command -v curl' in check
    assert '未检测到 curl 命令，请先安装 curl 后再执行健康检查脚本。' in check
    assert 'ATTEMPT=1' in check
    assert 'while :; do' in check
    assert 'curl -kfsS --max-time 10 "$BASE_URL/healthz"' in check
    assert 'READY_RESPONSE="$(curl -ksS --max-time 10 -w \'\\n%{http_code}\' "$BASE_URL/readyz" 2>/dev/null || true)"' in check
    assert 'READY_STATUS="$(printf \'%s\\n\' "$READY_RESPONSE" | tail -n 1)"' in check
    assert 'READY_PAYLOAD="$(printf \'%s\\n\' "$READY_RESPONSE" | sed \'$d\')"' in check
    assert '[ "$READY_STATUS" = "200" ]' in check
    assert 'curl -kfsS --max-time 10 "$BASE_URL/readyz"' not in check
    assert '"hard_gate_passed"[[:space:]]*:[[:space:]]*true' in check
    assert '健康检查失败：在 ${READY_RETRIES} 次重试后仍未就绪（/healthz 或 /readyz 未通过 hard_gate_passed=true）' in check
    assert '最后一次 readyz 响应: $READY_PAYLOAD' in check
    assert '等待服务就绪（第 ${ATTEMPT}/${READY_RETRIES} 次未通过，${READY_INTERVAL_SECONDS}s 后重试）...' in check
    assert 'HOME_PAYLOAD="$(curl -kfsSL --max-time 15 "$BASE_URL/")"' in check
    assert 'id="app"' in check
    assert '首页可访问性检查失败：返回内容未包含前端挂载锚点（id=\\"app\\"）' in check
    assert 'for ROUTE in entry manage/factory;' in check
    assert 'ROUTE_URL="${BASE_URL}/${ROUTE}"' in check
    assert 'if ! ROUTE_PAYLOAD="$(curl -kfsSL --max-time 15 "$ROUTE_URL" 2>/dev/null)"; then' in check
    assert '路由可访问性检查失败：无法访问 ${ROUTE_URL}，请检查前端服务是否可达' in check
    assert '路由可访问性检查失败：${ROUTE_URL} 返回内容未包含前端挂载锚点（id=\\"app\\"）' in check
    assert '${ROUTE} 响应内容: $ROUTE_PAYLOAD' in check
    assert 'AUTH_LOGIN_STATUS="$(curl -ks --max-time 10 -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/auth/login")"' in check
    assert 'if [ "$AUTH_LOGIN_STATUS" = "404" ] || [ "$AUTH_LOGIN_STATUS" = "000" ] || [ "$AUTH_LOGIN_STATUS" -ge 500 ]; then' in check
    assert 'API 入口可达性检查失败：/api/v1/auth/login 返回 ${AUTH_LOGIN_STATUS}，请检查 API 入口是否可达或服务异常' in check
    assert 'ps --services --status running' in check
    assert 'for service in db backend nginx; do' in check
    assert '服务未处于运行状态' in check
    assert 'DRY_RUN=0' in gate
    assert 'SKIP_AI=0' in gate
    assert 'SKIP_ROLE_SMOKE=0' in gate
    assert 'REQUIRE_EXTERNAL=0' in gate
    assert '--skip-ai' in gate
    assert '--skip-role-smoke' in gate
    assert '--require-external' in gate
    assert './scripts/check_trial_stack.sh "$BASE_URL"' in gate
    assert 'docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python scripts/check_pilot_config.py --date "$TARGET_DATE" --json' in gate
    assert 'docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python scripts/check_statistics_module_ready.py --json' in gate
    assert 'GATE_EXTERNAL' in gate
    assert 'check_ai_runtime_live' in gate
    assert 'run_role_smoke_tests' in gate
    assert './scripts/backup_db.sh --dry-run' in gate
    assert 'LATEST_BACKUP_FILE="$(ls -1t backups/*.dump 2>/dev/null | head -n 1 || true)"' in gate
    assert './scripts/restore_db.sh --dry-run "$latest_backup_file"' in gate
    assert 'GO_LIVE_READY=true' in gate
    assert 'GO_LIVE_READY=false' in gate
    assert 'SKIP_PULL=1' in launcher
    assert '--pull' in launcher
    assert '--skip-pull' in launcher
    assert '--require-external' in launcher
    assert './scripts/deploy_trial.sh' in launcher
    assert './scripts/go_live_gate.sh "$BASE_URL" $DATE_ARG $EXTRA_GATE_ARGS' in launcher


def test_quick_trial_ops_docs_note_required_running_services() -> None:
    ops = _read('docs/快速试跑运维手册.md')

    assert '检查基础文件与运行环境' in ops
    assert 'curl' in ops
    assert 'docker` 命令存在' in ops
    assert 'docker-compose.yml' in ops
    assert 'docker-compose.prod.yml' in ops
    assert '.env` 已准备' in ops
    assert 'docker compose' in ops
    assert 'docker daemon' in ops
    assert 'db / backend / nginx' in ops
    assert 'APP_ENV' in ops
    assert 'CHANGE_ME' in ops
    assert 'SECRET_KEY` 长度需 >= 32' in ops
    assert 'INIT_ADMIN_PASSWORD` 长度需 >= 12' in ops
    assert 'ssl/cert.pem' in ops
    assert 'ssl/key.pem' in ops
    assert 'READY_RETRIES' in ops
    assert 'READY_INTERVAL_SECONDS' in ops
    assert '/` 首页可访问' in ops
    assert 'id="app"' in ops
    assert '单次请求超时 `15` 秒' in ops


def test_backup_and_restore_scripts_default_to_prod_overlay() -> None:
    backup = _read('scripts/backup_db.sh')
    restore = _read('scripts/restore_db.sh')

    assert 'COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.yml docker-compose.prod.yml}"' in backup
    assert 'for compose_file in $COMPOSE_FILES; do' in backup
    assert '未检测到 ${compose_file}，请在项目根目录执行备份脚本并确保 compose 文件存在。' in backup
    assert 'if [ ! -f ".env" ]; then' in backup
    assert '未检测到 .env，请先在项目根目录准备 .env 后再执行备份脚本。' in backup
    assert 'command -v docker' in backup
    assert 'docker compose version' in backup
    assert 'docker info' in backup
    assert 'OUTPUT_DIR="$(dirname "$OUTPUT_FILE")"' in backup
    assert 'mkdir -p "$OUTPUT_DIR"' in backup
    assert 'if ! mkdir -p "$OUTPUT_DIR"; then' in backup
    assert 'if [ "$DRY_RUN" -eq 1 ]; then' in backup
    assert backup.find('if [ "$DRY_RUN" -eq 1 ]; then') < backup.find('if ! mkdir -p "$OUTPUT_DIR"; then')
    assert 'cleanup_backup_tmp()' in backup
    assert 'trap cleanup_backup_tmp EXIT' in backup
    assert 'pg_restore -l' in backup
    assert 'CONTAINER_FILE' in backup
    assert '备份格式校验失败，无法读取新生成的备份文件。' in backup
    assert 'if [ ! -s "$OUTPUT_FILE" ]; then' in backup
    assert '备份文件为空或写入失败' in backup
    assert 'if [ -z "$CONTAINER_ID" ]; then' in backup
    assert '数据库服务未运行' in backup
    assert 'DRY_RUN=0' in backup
    assert 'for arg in "$@"; do' in backup
    assert '--dry-run|--check-only' in backup
    assert 'DRY RUN：仅做备份前置预检，不执行数据库导出与拉取。' in backup
    assert 'COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.yml docker-compose.prod.yml}"' in restore
    assert 'for compose_file in $COMPOSE_FILES; do' in restore
    assert '未检测到 ${compose_file}，请在项目根目录执行恢复脚本并确保 compose 文件存在。' in restore
    assert 'if [ ! -f ".env" ]; then' in restore
    assert '未检测到 .env，请先在项目根目录准备 .env 后再执行恢复脚本。' in restore
    assert 'command -v docker' in restore
    assert 'docker compose version' in restore
    assert 'docker info' in restore
    assert 'cleanup_restore_tmp()' in restore
    assert 'trap cleanup_restore_tmp EXIT' in restore
    assert 'printenv POSTGRES_DB' in restore
    assert '恢复目标库不能与生产库同名' in restore
    assert 'postgres | template0 | template1' in restore
    assert '恢复目标库不能使用系统保留库名' in restore
    assert 'if [ ! -f "$BACKUP_FILE" ]; then' in restore
    assert 'if [ ! -s "$BACKUP_FILE" ]; then' in restore
    assert 'pg_restore -l' in restore
    assert 'CONTAINER_FILE' in restore
    assert '备份文件格式校验失败，无法读取' in restore
    assert '备份文件为空' in restore
    assert '备份文件不存在' in restore
    assert 'if [ -z "$CONTAINER_ID" ]; then' in restore
    assert 'DRY_RUN=0' in restore
    assert 'for arg in "$@"; do' in restore
    assert '--dry-run|--check-only' in restore
    assert 'DRY RUN：仅做恢复前置预检，不执行数据库恢复。' in restore


def test_quick_trial_ops_docs_includes_entry_and_manage_factory_routes() -> None:
    ops = _read('docs/快速试跑运维手册.md')

    assert '`/entry` 可访问' in ops
    assert '`/manage/factory` 可访问' in ops
    assert 'compose 文件存在、`.env` 已准备、docker/compose/daemon 可用' in ops
    assert '自定义备份路径' in ops
    assert '自动创建对应目录' in ops
    assert '备份产物为空' in ops
    assert '备份文件不存在/为空' in ops
    assert '备份格式可读性校验' in ops
    assert '备份完成后会立即做一次备份格式可读性校验' in ops
    assert '自动清理容器内临时备份文件' in ops
    assert '自动清理容器内临时恢复文件' in ops
    assert '不能与生产库同名' in ops
    assert 'postgres/template0/template1' in ops


def test_quick_trial_ops_docs_include_auth_login_api_route_probe() -> None:
    ops = _read('docs/快速试跑运维手册.md')

    assert '`/api/v1/auth/login` 入口可达' in ops
    assert '不为 404、000 或 5xx' in ops
    assert '5xx' in ops
    assert '服务异常' in ops
    assert '不校验登录结果' in ops


def test_quick_trial_docs_include_dry_run_mode() -> None:
    deploy = _read('docs/快速试跑运维手册.md')
    scripts = _read('scripts/deploy_trial.sh')
    checks = _read('scripts/check_trial_stack.sh')
    backup = _read('scripts/backup_db.sh')
    restore = _read('scripts/restore_db.sh')

    assert './scripts/deploy_trial.sh --dry-run' in deploy
    assert './scripts/check_trial_stack.sh --dry-run' in deploy
    assert './scripts/backup_db.sh --dry-run' in deploy
    assert './scripts/restore_db.sh --dry-run backups/你的备份文件.dump' in deploy
    assert '--dry-run|--check-only' in scripts
    assert '--dry-run|--check-only' in checks
    assert '--dry-run|--check-only' in backup
    assert '--dry-run|--check-only' in restore


def test_known_gaps_describes_schedule_gate_with_configured_timezone() -> None:
    gaps = _read('docs/known-gaps-and-todos.md')
    health = _read('backend/app/core/health.py')
    schedule_seed = _read('backend/app/services/pilot_schedule_seed.py')
    compose = _read('docker-compose.yml')
    prod_compose = _read('docker-compose.prod.yml')

    assert 'datetime.now(ZoneInfo(settings.DEFAULT_TIMEZONE)).date()' in health
    assert 'datetime.now(ZoneInfo(settings.DEFAULT_TIMEZONE)).date()' in schedule_seed
    assert 'python scripts/init_real_master_data.py &&' in compose
    assert 'python scripts/init_real_master_data.py &&' in prod_compose
    assert 'UTC 自然日' not in gaps
    assert 'DEFAULT_TIMEZONE=Asia/Shanghai' in gaps
    assert 'compose 启动链路已自动执行 `python scripts/init_real_master_data.py`' in gaps
    assert '后端启动时会先运行一次 `seed_default_pilot_schedule()`' in gaps
    assert 'APScheduler 每天 `00:05` 自动补种目标业务日应报清单' in gaps
    assert '手工执行 `python scripts/init_real_master_data.py` 仍作为应急兜底' in gaps
    assert 'target_date_schedule_available' in gaps
    assert 'SCHEDULE_EMPTY' in gaps


def test_known_gaps_e2e_baseline_reflects_current_playwright_specs() -> None:
    gaps = _read('docs/known-gaps-and-todos.md')
    e2e_specs = sorted((REPO_ROOT / 'frontend/e2e').glob('*.spec.js'))

    assert '13 条前端 e2e' not in gaps
    assert f'{len(e2e_specs)} 个 Playwright spec 文件' in gaps
    assert 'quality-center.spec.js' in gaps
    assert 'reconciliation-center.spec.js' in gaps
    assert 'reports-center.spec.js' in gaps


def test_known_gaps_master_runtime_scope_matches_workshop_page() -> None:
    gaps = _read('docs/known-gaps-and-todos.md')
    workshop = _read('frontend/src/views/master/Workshop.vue')

    assert 'title="车间主数据"' in workshop
    assert '/manage/master` 运行页已标为 `车间主数据`' in gaps
    assert '一站式主数据中心' in gaps


def test_exec_plan_tracks_phase_progress_without_hiding_external_gates() -> None:
    plan = _read('PLANS.md')

    for token in [
        '### 阶段进度审计（2026-05-06）',
        '- [x] Phase 1 代码闭环已验证',
        '- [x] Phase 2 代码闭环已验证',
        '- [x] Phase 3 代码闭环已验证',
        '- [ ] 真实外部联通闸门通过',
        '- [ ] 试点车间一周，工人-班长-管理者三端零人工中转运转',
        'MES MVC 联通阻塞已解除并补强会话恢复',
        '`coil_snapshots fetched=50 upserted=50`',
        '`mes_coil_snapshots_count=52`',
        '表格请求被打回登录页时会清 session 后重登重试',
        '单个非数据库源失败会返回该源 failed stats',
        '管理端工厂指挥中心已验证混合来源',
        '`overview_source=mixed`',
        '`overview_source=mes_projection`',
        '`factory_command_total_output_tons=0`',
        '`machine_lines_len=51`',
        '`local_source_line_count=0`',
        '机列绑定贯通到管理端',
        '`ShiftProductionData.equipment_id`',
        '`machine_binding_status`',
        '`mobile_shift_report_binding_ok=true`',
        '对账服务已验证卷级吨口径',
        '`reconciliation_output_total_tons=120.46`',
        '`production_vs_mes` 与 `energy_vs_production`',
        '自动汇总 Agent 已验证卷级吨口径',
        '`aggregator_output_tons=250.0`',
        '`aggregator_input_tons=260.0`',
        '内部 workflow 开关已启用',
        '`WORKFLOW_ENABLED=true`',
        '`NullWorkflowPublisher`',
        '钉钉应用配置已启用并完成 token 预检',
        '`DINGTALK_ENABLED=true`',
        '`token_received=true`',
        '钉钉通讯录同步阻塞已定位',
        '`qyapi_get_department_member`',
        '钉钉通讯录权限已具备可重复只读诊断',
        '`scripts/dingtalk_cli.py contacts --department-id 1 --json`',
        '不会写用户表或回显成员明细',
        '外部联通 readiness 已支持可选通讯录权限核验',
        '`DINGTALK_CONTACTS_PERMISSION_MISSING`',
        '`dingtalk_contacts_missing_scope=qyapi_get_department_member`',
        '`DINGTALK_NO_BOUND_USERS`',
        '`active_dingtalk_user_count=0`',
        '`active_dingtalk_employee_count=0`',
        '生产 synthetic 验证 `valid_business_date=2026-05-03`',
        '无日期样本保持 `missing_business_date=null`',
        '历史 `每日产量` 导入闸门已接入 import staging',
        '`first_daily_output_tons=1935.649`',
        '`batch_no=IMP-20260506130735-d4f557`',
        '`shift_rows_delta=0`',
        '`LLM_DISABLED`',
        '`APP_CONNECTION_DISABLED`',
        '通讯录成员读取权限、真实钉钉用户绑定/UAT、LLM/应用连接 API 与正式域名联通',
    ]:
        assert token in plan

    for stale_token in [
        '- [ ] Phase 1 全部 success criteria 达成',
        '- [ ] Phase 2 全部 success criteria 达成',
        '- [ ] Phase 3 全部 success criteria 达成',
    ]:
        assert stale_token not in plan


def test_launch_readiness_uses_current_ai_assistant_runtime_name() -> None:
    checklist = _read('docs/launch-readiness-checklist.md')
    router = _read('frontend/src/router/index.js')

    assert 'AI 大脑' not in checklist
    assert 'Brain Center' not in checklist
    assert 'AI 助手' in checklist
    assert '/manage/ai-assistant' in checklist
    assert "path: 'ai-assistant', name: 'factory-ai-assistant', component: AiWorkstation" in router


def test_operational_docs_use_current_entry_and_manage_routes() -> None:
    launch = _read('docs/launch-readiness-checklist.md')
    identity = _read('docs/企业微信生产入口准备清单.md')
    supplier = _read('docs/供应商对接手册-前端重构版.md')

    for token in [
        '`/manage/overview` 可访问',
        '`/manage/factory`、`/manage/workshop` 可访问',
    ]:
        assert token in launch

    for token in [
        '浏览器可直接访问 `/entry` 与 `/manage/factory`',
        '手机填报入口：`https://<你的正式域名>/entry`',
        '审阅入口：`https://<你的正式域名>/manage/factory`',
        '旧 `/mobile` 可兼容跳转到 `/entry`',
    ]:
        assert token in identity

    for token in [
        '审阅端：`/manage/overview`',
        '厂级看板：`/manage/factory`',
        '车间看板：`/manage/workshop`',
        '`/review/*` 与 `/admin/*` 保留兼容 redirect 到 `/manage/*`',
        '先联通登录、`/manage/factory` 与 `/entry`',
    ]:
        assert token in supplier

    for stale_token in [
        '`/review/overview` 可访问',
        '`/review/factory`、`/review/workshop` 可访问',
        '浏览器可直接访问 `/mobile` 与 `/review/factory`',
        '手机填报入口：`https://<你的正式域名>/mobile`',
        '审阅入口：`https://<你的正式域名>/review/factory`',
        '浏览器访问 `/mobile` 与 `/review/factory` 已通过',
        '审阅端：`/review/overview`',
        '厂级看板：`/review/factory`',
        '车间看板：`/review/workshop`',
        '先联通登录、`/review/factory` 与 `/entry`',
    ]:
        assert stale_token not in launch
        assert stale_token not in identity
        assert stale_token not in supplier


def test_api_and_cli_lane_docs_match_current_identity_boundaries() -> None:
    api = _read('docs/api-system-lane-spec.md')
    cli = _read('docs/cli-rollout-lane-spec.md')

    for token in [
        '`/api/v1/auth/*`、`/api/v1/dingtalk/*`',
        '统一用户/设备/钉钉 H5 / 浏览器进入系统',
        '`backend/app/routers/dingtalk.py`：钉钉 H5 身份入口',
        '`backend/app/adapters/wecom/group_bot.py`：workflow publisher 的企业微信群机器人',
        '企业微信用户登录路径已下线',
        '企业微信群机器人不属于身份入口',
        '| User / Session | `auth.py`、`dingtalk.py`、`users.py` |',
    ]:
        assert token in api

    for stale_token in [
        '`/api/v1/wecom/*`',
        '`backend/app/routers/wecom.py`',
        '`wecom.py`、`users.py`',
        '企业微信兼容登录',
        '企业微信兼容保留',
        '钉钉/企业微信登录都属于“身份入口”',
    ]:
        assert stale_token not in api

    for token in [
        '> 日期：当前 main 基线',
        'python scripts/check_pilot_config.py --date <目标日期> --json',
        'python scripts/check_owner_account_bindings.py --target-workshop-code <车间编码> --json',
        'python scripts/dingtalk_cli.py status --json',
        '669 passed，124 deselected，30 warnings',
        '浏览器 / 钉钉',
        'WECOM_BOT_ENABLED=false',
    ]:
        assert token in cli

    for stale_token in [
        '2026-04-06',
        'check_wecom_account_mapping.py',
        'check_wecom_*',
        'WECOM_APP_ENABLED=false',
        '当前 503 blocked',
        'EQUIPMENT_USER_BINDING_INVALID',
        'SCHEDULE_EMPTY',
        'hard_gate_passed=false',
    ]:
        assert stale_token not in cli
