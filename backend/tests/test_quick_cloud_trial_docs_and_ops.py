import importlib.util
import os
from pathlib import Path

import pytest


REPO_ROOT = (
    Path(os.environ['ALUMINUM_BYPASS_REPO_ROOT'])
    if os.environ.get('ALUMINUM_BYPASS_REPO_ROOT')
    else Path(__file__).resolve().parents[2]
)


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding='utf-8-sig')


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


def test_full_deploy_script_requires_external_secret_values() -> None:
    source = _read('backend/scripts/deploy_production.py')

    assert "DEPLOY_SSH_PASSWORD" in source
    assert "DEPLOY_DATABASE_URL" in source
    assert "DEPLOY_SECRET_KEY" in source
    assert "DEPLOY_INIT_ADMIN_PASSWORD" in source
    assert "password=ssh_password" in source
    assert "PASS =" not in source
    assert "DB_URL =" not in source
    assert "admin123" not in source
    assert "prod-secret-key" not in source


def test_full_deploy_script_require_env_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_deploy_production_module()

    monkeypatch.delenv('DEPLOY_SSH_PASSWORD', raising=False)
    with pytest.raises(RuntimeError, match='DEPLOY_SSH_PASSWORD is required'):
        module.require_env('DEPLOY_SSH_PASSWORD')

    monkeypatch.setenv('DEPLOY_SSH_PASSWORD', 'from-env')
    assert module.require_env('DEPLOY_SSH_PASSWORD') == 'from-env'


def test_release_freeze_checklist_requires_clean_worktree_and_github_remote() -> None:
    source = _read('docs/发布冻结基线清单.md')

    assert '`git status --short` 不再包含测试缓存、临时截图和误生成目录' in source
    assert 'GitHub 远端已接入，云主机可直接拉代码' in source


def test_quick_trial_docs_require_github_and_single_workshop_rollout() -> None:
    deployment = _read('docs/部署文档.md')
    readme = _read('README.md')
    uat = _read('docs/现场UAT清单.md')
    ops = _read('docs/快速试跑运维手册.md')

    assert 'GitHub' in deployment
    assert 'git pull' in deployment
    assert '一个车间' in deployment
    assert '企业微信正式入口先不接' in deployment
    assert '1 个管理员' in uat
    assert '1 个车间的主操或机台账号 1 人' in uat
    assert '专项 owner' in uat
    assert 'GitHub / 上云前封装准备' in readme
    assert './scripts/deploy_trial.sh' in ops
    assert './scripts/check_trial_stack.sh' in ops
    assert '默认检查 `https://localhost`' in ops
    assert 'TRIAL_BASE_URL=https://你的域名 ./scripts/deploy_trial.sh' in ops
    assert './scripts/backup_db.sh' in ops
    assert '备份文件不存在或 `db` 未运行' in ops
    assert 'hard_gate_passed=true' in ops
    assert '若失败会自动输出关键容器状态与后端/nginx日志片段' in ops
    assert './scripts/go_live_gate.sh' in ops
    assert '一键上线闸门' in ops
    assert '--skip-ai' in ops
    assert '--skip-role-smoke' in ops


def test_quick_trial_ops_scripts_exist_with_expected_commands() -> None:
    deploy = _read('scripts/deploy_trial.sh')
    check = _read('scripts/check_trial_stack.sh')
    gate = _read('scripts/go_live_gate.sh')

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
    assert 'READY_PAYLOAD="$(curl -kfsS --max-time 10 "$BASE_URL/readyz" 2>/dev/null)"' in check
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
    assert '--skip-ai' in gate
    assert '--skip-role-smoke' in gate
    assert './scripts/check_trial_stack.sh "$BASE_URL"' in gate
    assert 'docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python scripts/check_pilot_config.py --date "$TARGET_DATE" --json' in gate
    assert 'check_ai_runtime_live' in gate
    assert 'run_role_smoke_tests' in gate
    assert './scripts/backup_db.sh --dry-run' in gate
    assert 'LATEST_BACKUP_FILE="$(ls -1t backups/*.dump 2>/dev/null | head -n 1 || true)"' in gate
    assert './scripts/restore_db.sh --dry-run "$latest_backup_file"' in gate
    assert 'GO_LIVE_READY=true' in gate
    assert 'GO_LIVE_READY=false' in gate


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
