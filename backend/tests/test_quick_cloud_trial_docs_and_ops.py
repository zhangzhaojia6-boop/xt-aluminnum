from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding='utf-8-sig')


def test_gitignore_covers_quick_trial_artifacts() -> None:
    source = _read('.gitignore')

    assert '.tmp-pytest/' in source
    assert 'backend/.pytest-cache/' in source
    assert 'backend/.pytest-cache-2/' in source
    assert 'backend/pytest-cache-files-*/' in source
    assert 'frontend/tmp-review-home.png' in source
    assert 'frontend/frontend/' in source


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
    assert './scripts/backup_db.sh' in ops


def test_quick_trial_ops_scripts_exist_with_expected_commands() -> None:
    deploy = _read('scripts/deploy_trial.sh')
    check = _read('scripts/check_trial_stack.sh')

    assert 'docker compose -f docker-compose.yml -f docker-compose.prod.yml config' in deploy
    assert 'docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build' in deploy
    assert 'docker compose -f docker-compose.yml -f docker-compose.prod.yml ps' in deploy
    assert 'curl -kfsS "$BASE_URL/healthz"' in check
    assert 'curl -kfsS "$BASE_URL/readyz"' in check


def test_backup_and_restore_scripts_default_to_prod_overlay() -> None:
    backup = _read('scripts/backup_db.sh')
    restore = _read('scripts/restore_db.sh')

    assert 'COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.yml docker-compose.prod.yml}"' in backup
    assert 'COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.yml docker-compose.prod.yml}"' in restore
