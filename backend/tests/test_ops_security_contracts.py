from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding='utf-8')


def test_legacy_password_deploy_script_is_removed() -> None:
    assert not (REPO_ROOT / 'deploy.sh').exists()


def test_ops_scripts_do_not_embed_production_secrets() -> None:
    forbidden = [
        'xt_' + 'bypass_2026',
        'zzj' + '200123',
        'postgresql://bypass_user:',
    ]
    files = [
        'backend/scripts/generate_qrcodes.py',
        'backend/scripts/smoke_test_qrcodes.py',
        'scripts/remove_shift_leader_accounts.py',
        'scripts/reset_admin.py',
    ]

    for file in files:
        source = _read(file)
        for token in forbidden:
            assert token not in source, f'{file} must read secrets from environment variables'


def test_ops_scripts_require_explicit_secret_environment() -> None:
    assert 'PROD_DB_PASSWORD' in _read('backend/scripts/generate_qrcodes.py')
    assert 'PROD_DB_PASSWORD' in _read('backend/scripts/smoke_test_qrcodes.py')
    assert 'DATABASE_URL' in _read('scripts/remove_shift_leader_accounts.py')
    assert 'ADMIN_NEW_PASSWORD' in _read('scripts/reset_admin.py')
