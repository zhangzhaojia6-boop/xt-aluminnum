from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path


REPO_ROOT = (
    Path(os.environ['ALUMINUM_BYPASS_REPO_ROOT'])
    if os.environ.get('ALUMINUM_BYPASS_REPO_ROOT')
    else Path(__file__).resolve().parents[2]
)
MODULE_PATH = REPO_ROOT / 'scripts' / 'generate_env.py'
SPEC = spec_from_file_location('generate_env', MODULE_PATH)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)
build_env_content = MODULE.build_env_content


def test_build_env_content_for_quick_trial_production() -> None:
    content = build_env_content(
        postgres_password='pw',
        secret_key='secret',
        admin_password='adminpw',
        dingtalk_corp_id='',
        dingtalk_app_key='',
        dingtalk_app_secret='',
        dingtalk_agent_id='',
        app_env='production',
        cors_origins='https://trial.example.com',
    )

    assert 'APP_ENV=production' in content
    assert 'CORS_ORIGINS=https://trial.example.com' in content
    assert 'WECOM_APP_ENABLED=false' in content
    assert 'AUTO_PUBLISH_ENABLED=true' in content
