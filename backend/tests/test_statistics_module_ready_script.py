from importlib.util import module_from_spec, spec_from_file_location

from app.config import Settings
from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'check_statistics_module_ready.py'


def _load_script_module():
    spec = spec_from_file_location('check_statistics_module_ready_script', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_settings(**overrides) -> Settings:
    values = {
        'APP_ENV': 'development',
        'DATABASE_URL': 'postgresql+psycopg2://user:pass@localhost:5432/test',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        'WORKFLOW_ENABLED': True,
        'AUTO_PUBLISH_ENABLED': True,
        'AUTO_PUSH_ENABLED': True,
        'DINGTALK_ENABLED': True,
        'DINGTALK_CORP_ID': 'corp-id',
        'DINGTALK_APP_KEY': 'app-key',
        'DINGTALK_APP_SECRET': 'secret',
        'DINGTALK_AGENT_ID': '1000002',
        'LLM_ENABLED': True,
        'LLM_API_BASE': 'https://example.invalid/llm',
        'LLM_API_KEY': 'llm-key',
        'LLM_MODEL': 'gpt-5.4-mini',
        'MES_ADAPTER': 'rest_api',
        'MES_API_BASE': 'https://example.invalid/mes',
        'APP_CONNECTION_ENABLED': True,
        'APP_CONNECTION_PUSH_MODE': 'enabled',
        'APP_CONNECTION_API_BASE': 'https://example.invalid/app-connection',
        'APP_CONNECTION_API_KEY': 'app-key',
    }
    values.update(overrides)
    return Settings(**values)


class _DummySession:
    def __init__(self, *, dingtalk_user_count: int = 1, dingtalk_employee_count: int = 1):
        self.dingtalk_user_count = dingtalk_user_count
        self.dingtalk_employee_count = dingtalk_employee_count

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query):
        sql = str(query)
        if 'FROM users' in sql:
            return _DummyResult(self.dingtalk_user_count)
        if 'FROM employees' in sql:
            return _DummyResult(self.dingtalk_employee_count)
        return _DummyResult(1)


class _DummyResult:
    def __init__(self, value: int):
        self.value = value

    def scalar(self):
        return self.value


def _sessionmaker_ok():
    return _DummySession()


def _sessionmaker_with_dingtalk_counts(*, user_count: int, employee_count: int):
    return lambda: _DummySession(dingtalk_user_count=user_count, dingtalk_employee_count=employee_count)


def test_inspect_statistics_module_ready_passes_with_minimum_valid_setup() -> None:
    module = _load_script_module()

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(),
        sessionmaker_factory=_sessionmaker_ok,
    )

    assert payload['local_runnable'] is True
    assert payload['module_usable'] is True
    assert payload['external_connection_enabled'] is True
    assert payload['hard_gate_passed'] is True
    assert payload['hard_issues'] == []
    assert payload['warning_issues'] == []
    assert payload['stats']['llm_model_ref_set'] is True
    assert payload['stats']['active_dingtalk_user_count'] == 1
    assert payload['stats']['active_dingtalk_employee_count'] == 1


def test_inspect_statistics_module_ready_warns_when_dingtalk_has_no_bound_users() -> None:
    module = _load_script_module()

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(),
        sessionmaker_factory=_sessionmaker_with_dingtalk_counts(user_count=0, employee_count=0),
    )

    assert payload['hard_gate_passed'] is True
    assert payload['hard_issues'] == []
    assert payload['stats']['active_dingtalk_user_count'] == 0
    assert payload['stats']['active_dingtalk_employee_count'] == 0
    warning = next(item for item in payload['warning_issues'] if item['code'] == 'DINGTALK_NO_BOUND_USERS')
    assert warning['level'] == 'warning'
    assert '工作通知无法送达真实人员' in warning['message']


def test_inspect_statistics_module_ready_does_not_check_dingtalk_contacts_by_default() -> None:
    module = _load_script_module()

    def fail_if_called(*args, **kwargs):
        raise AssertionError('contacts check should be opt-in')

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(),
        sessionmaker_factory=_sessionmaker_ok,
        dingtalk_contacts_checker=fail_if_called,
    )

    assert payload['hard_gate_passed'] is True
    assert payload['stats']['dingtalk_department_access'] is None


def test_inspect_statistics_module_ready_can_check_dingtalk_contact_permission() -> None:
    module = _load_script_module()

    def contacts_checker(*, department_id):
        assert department_id == 1
        return {
            'ok': False,
            'configured': True,
            'department_id': department_id,
            'department_access': False,
            'dry_run_only': True,
            'missing_scope': 'qyapi_get_department_member',
        }

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(),
        sessionmaker_factory=_sessionmaker_ok,
        check_dingtalk_contacts=True,
        dingtalk_contacts_checker=contacts_checker,
    )

    warning = next(item for item in payload['warning_issues'] if item['code'] == 'DINGTALK_CONTACTS_PERMISSION_MISSING')
    assert warning['level'] == 'warning'
    assert 'qyapi_get_department_member' in warning['message']
    assert payload['stats']['dingtalk_department_access'] is False
    assert payload['stats']['dingtalk_contacts_missing_scope'] == 'qyapi_get_department_member'


def test_inspect_statistics_module_ready_accepts_llm_endpoint_id_without_model() -> None:
    module = _load_script_module()

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(LLM_MODEL='', LLM_ENDPOINT_ID='ep-20260505-test'),
        sessionmaker_factory=_sessionmaker_ok,
    )

    assert payload['module_usable'] is True
    assert payload['hard_gate_passed'] is True
    assert payload['hard_issues'] == []
    assert payload['stats']['llm_model_ref_set'] is True


def test_inspect_statistics_module_ready_blocks_dry_run_app_connection() -> None:
    module = _load_script_module()

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(
            APP_CONNECTION_PUSH_MODE='dry_run',
            APP_CONNECTION_API_BASE=None,
            APP_CONNECTION_API_KEY=None,
        ),
        sessionmaker_factory=_sessionmaker_ok,
    )

    assert payload['module_usable'] is False
    assert payload['external_connection_enabled'] is False
    assert payload['hard_gate_passed'] is False
    assert any(item['code'] == 'APP_CONNECTION_DRY_RUN_ONLY' for item in payload['hard_issues'])


def test_inspect_statistics_module_ready_reports_hard_issues_when_required_integrations_are_disabled() -> None:
    module = _load_script_module()

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(
            WORKFLOW_ENABLED=False,
            LLM_ENABLED=False,
            DINGTALK_ENABLED=False,
            APP_CONNECTION_ENABLED=False,
        ),
        sessionmaker_factory=_sessionmaker_ok,
    )

    assert payload['module_usable'] is False
    assert any(item['code'] == 'WORKFLOW_DISABLED' for item in payload['hard_issues'])
    assert any(item['code'] == 'LLM_DISABLED' for item in payload['hard_issues'])
    assert any(item['code'] == 'DINGTALK_DISABLED' for item in payload['hard_issues'])
    assert any(item['code'] == 'APP_CONNECTION_DISABLED' for item in payload['hard_issues'])
    dingtalk_issue = next(item for item in payload['hard_issues'] if item['code'] == 'DINGTALK_DISABLED')
    assert dingtalk_issue['required_env'] == [
        'DINGTALK_ENABLED',
        'DINGTALK_CORP_ID',
        'DINGTALK_APP_KEY',
        'DINGTALK_APP_SECRET',
        'DINGTALK_AGENT_ID',
    ]
    app_connection_issue = next(item for item in payload['hard_issues'] if item['code'] == 'APP_CONNECTION_DISABLED')
    assert app_connection_issue['required_env'] == [
        'APP_CONNECTION_ENABLED',
        'APP_CONNECTION_PUSH_MODE',
        'APP_CONNECTION_API_BASE',
        'APP_CONNECTION_API_KEY',
    ]
    purposes = {item['purpose'] for item in payload['missing_inputs']}
    assert 'LLM/AI 摘要增强' in purposes
    assert '应用连接外发' in purposes
    assert '钉钉日报触达' in purposes
    llm_input = next(item for item in payload['missing_inputs'] if item['issue_code'] == 'LLM_DISABLED')
    assert llm_input['location'] == '服务器 backend/.env'
    assert 'LLM_API_KEY' in llm_input['missing_fields']
    assert 'LLM_ENABLED=true' in llm_input['suggested_value']


def test_missing_inputs_markdown_uses_operator_columns_without_secret_values() -> None:
    module = _load_script_module()

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(
            LLM_ENABLED=False,
            APP_CONNECTION_ENABLED=False,
        ),
        sessionmaker_factory=_sessionmaker_with_dingtalk_counts(user_count=0, employee_count=0),
    )

    markdown = module.format_missing_inputs_markdown(payload['missing_inputs'])

    assert '| 用途 | 所在位置 | 缺失字段 | 影响范围 | 建议取值 |' in markdown
    assert 'LLM/AI 摘要增强' in markdown
    assert '应用连接外发' in markdown
    assert '钉钉真实人员触达' in markdown
    assert '<现场提供>' in markdown
    assert 'llm-key' not in markdown
    assert 'app-key' not in markdown


def test_inspect_statistics_module_ready_reports_mes_when_not_configured() -> None:
    module = _load_script_module()

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(MES_ADAPTER='null', MES_API_BASE=None),
        sessionmaker_factory=_sessionmaker_ok,
    )

    assert payload['module_usable'] is False
    assert payload['hard_gate_passed'] is False
    assert payload['stats']['mes_adapter'] == 'null'
    assert payload['stats']['mes_ready'] is False
    mes_issue = next(item for item in payload['hard_issues'] if item['code'] == 'MES_UNCONFIGURED')
    assert mes_issue['required_env'] == [
        'MES_ADAPTER',
        'MES_API_BASE',
        'MES_MVC_BASE_URL',
        'MES_MVC_USERNAME',
        'MES_MVC_PASSWORD',
    ]


def test_external_env_template_defaults_to_mvc_without_leaking_existing_secret_values() -> None:
    module = _load_script_module()

    template = module.build_external_env_template(
        runtime_settings=_build_settings(
            MES_ADAPTER='null',
            LLM_API_KEY='real-llm-secret',
            DINGTALK_APP_SECRET='real-dingtalk-secret',
            APP_CONNECTION_API_KEY='real-app-secret',
        )
    )

    for token in [
        'MES_ADAPTER=mvc',
        'MES_MVC_BASE_URL=',
        'MES_MVC_USERNAME=',
        'MES_MVC_PASSWORD=',
        'WORKFLOW_ENABLED=true',
        'AUTO_PUBLISH_ENABLED=true',
        'AUTO_PUSH_ENABLED=true',
        'LLM_ENABLED=true',
        'LLM_API_BASE=',
        'LLM_API_KEY=',
        'DINGTALK_ENABLED=true',
        'DINGTALK_CORP_ID=',
        'DINGTALK_APP_KEY=',
        'DINGTALK_APP_SECRET=',
        'DINGTALK_AGENT_ID=',
        'APP_CONNECTION_ENABLED=true',
        'APP_CONNECTION_PUSH_MODE=enabled',
        'APP_CONNECTION_API_BASE=',
        'APP_CONNECTION_API_KEY=',
        '# 如果现场使用 REST MES',
        '# MES_ADAPTER=rest_api',
        '# MES_API_BASE=',
        '# MES_API_KEY=',
    ]:
        assert token in template

    for secret_value in ['real-llm-secret', 'real-dingtalk-secret', 'real-app-secret']:
        assert secret_value not in template


def test_external_env_template_can_target_rest_api_mes() -> None:
    module = _load_script_module()

    template = module.build_external_env_template(runtime_settings=_build_settings(MES_ADAPTER='rest_api'))

    assert 'MES_ADAPTER=rest_api' in template
    assert 'MES_API_BASE=' in template
    assert 'MES_API_KEY=' in template
    assert 'MES_MVC_BASE_URL=' not in template


def test_inspect_statistics_module_ready_does_not_probe_live_aggregation_by_default() -> None:
    module = _load_script_module()

    def fail_if_called(_db):
        raise AssertionError('live aggregation probe should be opt-in')

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(),
        sessionmaker_factory=_sessionmaker_ok,
        live_aggregation_probe=fail_if_called,
    )

    assert payload['hard_gate_passed'] is True
    assert payload['stats']['live_aggregation_checked'] is False
    assert payload['stats']['live_aggregation_ok'] is None


def test_inspect_statistics_module_ready_can_probe_live_aggregation() -> None:
    module = _load_script_module()

    def live_probe(db):
        assert isinstance(db, _DummySession)
        return {
            'business_date': '2026-05-12',
            'business_date_source': 'recent_upload',
            'data_source': 'mixed',
            'total_entry_count': 37,
            'formal_entry_count': 37,
            'draft_entry_count': 0,
            'mes_row_count': 23,
            'fill_entries_with_mes_match': 24,
            'fill_entries_bound_to_machine': 24,
            'pending_assignment_entry_count': 0,
        }

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(),
        sessionmaker_factory=_sessionmaker_ok,
        check_live_aggregation=True,
        live_aggregation_probe=live_probe,
    )

    assert payload['hard_gate_passed'] is True
    assert payload['stats']['live_aggregation_checked'] is True
    assert payload['stats']['live_aggregation_ok'] is True
    assert payload['stats']['live_aggregation_business_date'] == '2026-05-12'
    assert payload['stats']['live_aggregation_date_source'] == 'recent_upload'
    assert payload['stats']['live_aggregation_data_source'] == 'mixed'
    assert payload['stats']['live_aggregation_total_entry_count'] == 37
    assert payload['stats']['live_aggregation_mes_row_count'] == 23
    assert payload['stats']['live_aggregation_bound_to_machine_count'] == 24
    assert payload['stats']['live_aggregation_pending_assignment_count'] == 0


def test_inspect_statistics_module_ready_blocks_when_live_aggregation_probe_fails() -> None:
    module = _load_script_module()

    def failing_probe(_db):
        raise RuntimeError('database details should not leak')

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(),
        sessionmaker_factory=_sessionmaker_ok,
        check_live_aggregation=True,
        live_aggregation_probe=failing_probe,
    )

    assert payload['hard_gate_passed'] is False
    assert payload['module_usable'] is False
    issue = next(item for item in payload['hard_issues'] if item['code'] == 'LIVE_AGGREGATION_UNAVAILABLE')
    assert 'RuntimeError' in issue['message']
    assert 'database details should not leak' not in issue['message']
    assert payload['stats']['live_aggregation_checked'] is True
    assert payload['stats']['live_aggregation_ok'] is False
