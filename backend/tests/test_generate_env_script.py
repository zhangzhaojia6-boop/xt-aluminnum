from importlib.util import module_from_spec, spec_from_file_location

from tests.path_helpers import REPO_ROOT

SCRIPT_PATH = REPO_ROOT / 'scripts' / 'generate_env.py'


def _load_script_module():
    spec = spec_from_file_location('generate_env_script', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_env_content_includes_security_warnings_and_required_values() -> None:
    module = _load_script_module()

    env_content = module.build_env_content(
        postgres_password='postgres-secret',
        secret_key='secret-key-value',
        admin_password='admin-secret',
        dingtalk_corp_id='corp-id',
        dingtalk_app_key='app-key',
        dingtalk_app_secret='app-secret',
        dingtalk_agent_id='agent-id',
    )

    assert '# ⚠ NEVER commit .env to version control' in env_content
    assert 'POSTGRES_PASSWORD=postgres-secret' in env_content
    assert 'SECRET_KEY=secret-key-value' in env_content
    assert 'INIT_ADMIN_PASSWORD=admin-secret' in env_content
    assert 'MES_ADAPTER=null' in env_content
    assert 'MES_API_BASE=' in env_content
    assert 'MES_API_TRACKING_CARD_INFO_PATH=/tracking-cards/{card_no}' in env_content
    assert 'MES_API_COIL_SNAPSHOTS_PATH=/coil-snapshots' in env_content
    assert 'MES_SYNC_POLL_MINUTES=1' in env_content
    assert 'DINGTALK_CORP_ID=corp-id' in env_content
    assert 'WORKFLOW_ENABLED=false' in env_content
    assert 'AUTO_PUBLISH_ENABLED=true' in env_content
    assert 'AUTO_PUSH_ENABLED=true' in env_content
    assert 'AUTO_PIPELINE_REQUIRE_READY=true' in env_content
    assert 'WECOM_BOT_ENABLED=false' in env_content
    assert 'WECOM_BOT_DRY_RUN=false' in env_content
    assert 'WECOM_BOT_WEBHOOK_URL=' in env_content
    assert 'WECOM_BOT_MANAGEMENT_WEBHOOK_URL=' in env_content
    assert 'WECOM_BOT_WORKSHOP_WEBHOOK_MAP={}' in env_content
    assert 'WECOM_BOT_TEAM_WEBHOOK_MAP={}' in env_content
    assert 'WECOM_APP_ENABLED=false' in env_content
    assert 'WECOM_CORP_ID=' in env_content
    assert 'WECOM_AGENT_ID=' in env_content
    assert 'WECOM_APP_SECRET=' in env_content
    assert 'LLM_ENABLED=false' in env_content
    assert 'LLM_API_BASE=' in env_content
    assert 'LLM_API_KEY=' in env_content
    assert 'LLM_MODEL=' in env_content
    assert 'LLM_TIMEOUT_SECONDS=20' in env_content
    assert 'APP_CONNECTION_ENABLED=false' in env_content
    assert 'APP_CONNECTION_API_BASE=' in env_content
    assert 'APP_CONNECTION_API_KEY=' in env_content
    assert 'APP_CONNECTION_TIMEOUT_SECONDS=8' in env_content
    assert 'APP_CONNECTION_PUSH_MODE=disabled' in env_content
    assert 'MANAGEMENT_ESTIMATE_REVENUE_PER_TON=' in env_content
    assert 'MANAGEMENT_ESTIMATE_ELECTRICITY_COST_PER_UNIT=' in env_content
    assert 'MANAGEMENT_ESTIMATE_GAS_COST_PER_UNIT=' in env_content
    assert 'MANAGEMENT_ESTIMATE_LABOR_COST_PER_ATTENDANCE=' in env_content
    assert env_content.endswith('\n')
