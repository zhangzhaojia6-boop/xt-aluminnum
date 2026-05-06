from importlib.util import module_from_spec, spec_from_file_location

from app.config import Settings
from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'check_mes_mvc_preflight.py'


class _Response:
    def __init__(self, *, payload=None, status_code=200, cookies=None, text=''):
        self._payload = payload if payload is not None else {}
        self.status_code = status_code
        self.cookies = cookies or {}
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'http_{self.status_code}')

    def json(self):
        return self._payload


def _load_script_module():
    spec = spec_from_file_location('check_mes_mvc_preflight_script', SCRIPT_PATH)
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
        'MES_ADAPTER': 'mvc',
        'MES_MVC_BASE_URL': 'https://mes.example.com',
        'MES_MVC_USERNAME': 'mes-user',
        'MES_MVC_PASSWORD': 'mes-pass',
    }
    values.update(overrides)
    return Settings(**values)


def _sender_for(payloads, calls):
    queue = list(payloads)

    def sender(**kwargs):
        calls.append(kwargs)
        if not queue:
            raise AssertionError(f'unexpected request: {kwargs}')
        return queue.pop(0)

    return sender


def test_mes_mvc_preflight_reports_missing_config_without_network_probe() -> None:
    module = _load_script_module()

    payload = module.inspect_mes_mvc_preflight(
        runtime_settings=_build_settings(
            MES_ADAPTER='null',
            MES_MVC_BASE_URL='',
            MES_MVC_USERNAME='',
            MES_MVC_PASSWORD='',
        )
    )

    assert payload['adapter'] == 'null'
    assert payload['mvc_configured'] is False
    assert payload['missing_env'] == [
        'MES_ADAPTER',
        'MES_MVC_BASE_URL',
        'MES_MVC_USERNAME',
        'MES_MVC_PASSWORD',
    ]
    assert payload['login_page']['status'] == 'skipped'
    assert payload['login']['status'] == 'skipped'


def test_mes_mvc_preflight_probes_login_page_without_sending_credentials() -> None:
    module = _load_script_module()
    calls = []

    payload = module.inspect_mes_mvc_preflight(
        runtime_settings=_build_settings(),
        sender=_sender_for(
            [
                _Response(
                    text='<input name="__RequestVerificationToken" type="hidden" value="token-1" />',
                    cookies={'csrf': 'one'},
                ),
            ],
            calls,
        ),
    )

    assert payload['mvc_configured'] is True
    assert payload['missing_env'] == []
    assert payload['login_page']['status'] == 'reachable'
    assert payload['login_page']['token_present'] is True
    assert payload['login']['status'] == 'skipped'
    assert [call['url'] for call in calls] == ['https://mes.example.com/Login/Index']
    assert 'Account' not in calls[0]['data']
    assert 'Password' not in calls[0]['data']


def test_mes_mvc_preflight_can_attempt_login_without_leaking_secret_values() -> None:
    module = _load_script_module()
    calls = []

    payload = module.inspect_mes_mvc_preflight(
        runtime_settings=_build_settings(MES_MVC_PASSWORD='real-secret-pass'),
        sender=_sender_for(
            [
                _Response(text='<input name="__RequestVerificationToken" type="hidden" value="token-1" />'),
                _Response(payload={'status': True, 'message': '验证成功!'}, cookies={'sid': 'abc'}),
                _Response(payload={'status': True, 'message': '登录成功!'}),
                _Response(payload={'data': []}),
            ],
            calls,
        ),
        attempt_login=True,
    )

    assert payload['login_page']['status'] == 'reachable'
    assert payload['login']['status'] == 'success'
    assert 'real-secret-pass' not in repr(payload)
    assert calls[1]['data']['Account'] == 'mes-user'
    assert calls[1]['data']['Password'] == 'real-secret-pass'


def test_mes_mvc_preflight_login_failure_is_sanitized() -> None:
    module = _load_script_module()

    payload = module.inspect_mes_mvc_preflight(
        runtime_settings=_build_settings(MES_MVC_PASSWORD='real-secret-pass'),
        sender=_sender_for(
            [
                _Response(text='<input name="__RequestVerificationToken" type="hidden" value="token-1" />'),
                _Response(payload={'status': False, 'message': 'bad real-secret-pass'}),
            ],
            [],
        ),
        attempt_login=True,
    )

    assert payload['login']['status'] == 'failed'
    assert payload['login']['error'] == 'RuntimeError'
    assert 'real-secret-pass' not in repr(payload)
