from importlib.util import module_from_spec, spec_from_file_location

from app.config import Settings
from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'check_mes_sqlserver_preflight.py'


class _FakeProbe:
    def __init__(self, *, secret='secret-pass', fail=False):
        self.secret = secret
        self.fail = fail
        self.called = False

    def __call__(self, runtime):
        self.called = True
        if self.fail:
            raise RuntimeError(f'cannot connect with {self.secret}')
        assert runtime.MES_SQLSERVER_PASSWORD == self.secret
        return {
            'database_name': 'MESDB',
            'tables': [
                {
                    'schema': 'dbo',
                    'name': 'v_CoilStatus',
                    'row_count_estimate': 12,
                    'columns': [
                        {'name': 'ProductId', 'data_type': 'int'},
                        {'name': 'TrackingCardNo', 'data_type': 'nvarchar'},
                        {'name': 'MaterialCode', 'data_type': 'nvarchar'},
                        {'name': 'CustomerName', 'data_type': 'nvarchar'},
                        {'name': 'AlloyGrade', 'data_type': 'nvarchar'},
                        {'name': 'Spec', 'data_type': 'nvarchar'},
                        {'name': 'CurrentWorkShop', 'data_type': 'nvarchar'},
                        {'name': 'CurrentProcess', 'data_type': 'nvarchar'},
                        {'name': 'ProcessRoute', 'data_type': 'nvarchar'},
                        {'name': 'DoingWeight', 'data_type': 'decimal'},
                        {'name': 'UpdateTime', 'data_type': 'datetime'},
                        {'name': 'StatusName', 'data_type': 'nvarchar'},
                        {'name': 'CustomerPhone', 'data_type': 'nvarchar'},
                    ],
                }
            ],
        }


class _FakePermissionProbe:
    def __init__(self, *, secret='secret-pass', fail=False, can_write=False):
        self.secret = secret
        self.fail = fail
        self.can_write = can_write
        self.called = False

    def __call__(self, runtime):
        self.called = True
        if self.fail:
            raise RuntimeError(f'permission probe failed with {self.secret}')
        assert runtime.MES_SQLSERVER_PASSWORD == self.secret
        return {
            'database_name': 'MESDB',
            'can_select': 1,
            'can_insert': 1 if self.can_write else 0,
            'can_update': 0,
            'can_delete': 0,
            'can_create_table': 0,
            'is_sysadmin': 0,
            'is_dbcreator': 0,
        }


def _load_script_module():
    spec = spec_from_file_location('check_mes_sqlserver_preflight_script', SCRIPT_PATH)
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
        'MES_ADAPTER': 'sqlserver',
        'MES_SQLSERVER_HOST': 'sqlserver.example.com',
        'MES_SQLSERVER_PORT': 1433,
        'MES_SQLSERVER_DATABASE': 'MESDB',
        'MES_SQLSERVER_USERNAME': 'readonly',
        'MES_SQLSERVER_PASSWORD': 'secret-pass',
    }
    values.update(overrides)
    return Settings(**values)


def test_sqlserver_preflight_reports_missing_config_without_connecting() -> None:
    module = _load_script_module()
    probe = _FakeProbe()
    permission_probe = _FakePermissionProbe()

    payload = module.inspect_mes_sqlserver_preflight(
        runtime_settings=_build_settings(
            MES_ADAPTER='null',
            MES_SQLSERVER_HOST='',
            MES_SQLSERVER_DATABASE='',
            MES_SQLSERVER_USERNAME='',
            MES_SQLSERVER_PASSWORD='',
        ),
        probe=probe,
        permission_probe=permission_probe,
    )

    assert probe.called is False
    assert permission_probe.called is False
    assert payload['adapter'] == 'null'
    assert payload['sqlserver_configured'] is False
    assert payload['missing_env'] == [
        'MES_ADAPTER',
        'MES_SQLSERVER_HOST',
        'MES_SQLSERVER_DATABASE',
        'MES_SQLSERVER_USERNAME',
        'MES_SQLSERVER_PASSWORD',
    ]
    assert payload['connection']['status'] == 'skipped'


def test_sqlserver_preflight_lists_safe_metadata_without_leaking_password() -> None:
    module = _load_script_module()

    payload = module.inspect_mes_sqlserver_preflight(
        runtime_settings=_build_settings(MES_SQLSERVER_PASSWORD='secret-pass'),
        probe=_FakeProbe(secret='secret-pass'),
        permission_probe=_FakePermissionProbe(secret='secret-pass'),
    )

    assert payload['sqlserver_configured'] is True
    assert payload['connection']['status'] == 'success'
    assert payload['database']['name'] == 'MESDB'
    assert payload['tables']['count'] == 1
    assert payload['tables']['items'][0]['name'] == 'v_CoilStatus'
    assert payload['tables']['items'][0]['columns'][1]['name'] == 'TrackingCardNo'
    analysis = payload['field_map']['tables'][0]
    assert analysis['name'] == 'v_CoilStatus'
    assert analysis['business_roles'] == ['coil_status']
    assert analysis['primary_key_candidates'] == ['ProductId']
    assert analysis['updated_at_candidates'] == ['UpdateTime']
    assert analysis['status_field_candidates'] == ['StatusName']
    assert analysis['weight_field_candidates'] == ['DoingWeight']
    assert analysis['field_matches']['tracking_card_no'] == ['TrackingCardNo', 'MaterialCode']
    assert analysis['field_matches']['customer_name'] == ['CustomerName']
    assert analysis['field_matches']['alloy_grade'] == ['AlloyGrade']
    assert analysis['field_matches']['current_process'] == ['CurrentProcess']
    assert 'CustomerPhone' not in repr(payload['field_map'])
    assert 'CustomerPhone' not in repr(payload['tables'])
    assert payload['permissions']['status'] == 'success'
    assert payload['permissions']['read_only_account'] is True
    assert payload['permissions']['can_select'] is True
    assert payload['permissions']['can_insert'] is False
    assert payload['permissions']['can_update'] is False
    assert payload['permissions']['can_delete'] is False
    assert payload['permissions']['can_create_table'] is False
    assert payload['permissions']['is_sysadmin'] is False
    assert payload['permissions']['is_dbcreator'] is False
    assert 'secret-pass' not in repr(payload)


def test_sqlserver_preflight_marks_writable_account_not_read_only() -> None:
    module = _load_script_module()

    payload = module.inspect_mes_sqlserver_preflight(
        runtime_settings=_build_settings(MES_SQLSERVER_PASSWORD='secret-pass'),
        probe=_FakeProbe(secret='secret-pass'),
        permission_probe=_FakePermissionProbe(secret='secret-pass', can_write=True),
    )

    assert payload['permissions']['status'] == 'success'
    assert payload['permissions']['read_only_account'] is False
    assert payload['permissions']['can_insert'] is True
    assert 'secret-pass' not in repr(payload)


def test_sqlserver_preflight_connection_failure_is_sanitized() -> None:
    module = _load_script_module()

    payload = module.inspect_mes_sqlserver_preflight(
        runtime_settings=_build_settings(MES_SQLSERVER_PASSWORD='secret-pass'),
        probe=_FakeProbe(secret='secret-pass', fail=True),
        permission_probe=_FakePermissionProbe(secret='secret-pass'),
    )

    assert payload['connection']['status'] == 'failed'
    assert payload['connection']['error'] == 'RuntimeError'
    assert payload['permissions']['status'] == 'skipped'
    assert 'secret-pass' not in repr(payload)


def test_sqlserver_preflight_permission_failure_is_sanitized() -> None:
    module = _load_script_module()

    payload = module.inspect_mes_sqlserver_preflight(
        runtime_settings=_build_settings(MES_SQLSERVER_PASSWORD='secret-pass'),
        probe=_FakeProbe(secret='secret-pass'),
        permission_probe=_FakePermissionProbe(secret='secret-pass', fail=True),
    )

    assert payload['connection']['status'] == 'success'
    assert payload['permissions']['status'] == 'failed'
    assert payload['permissions']['error'] == 'RuntimeError'
    assert 'secret-pass' not in repr(payload)
