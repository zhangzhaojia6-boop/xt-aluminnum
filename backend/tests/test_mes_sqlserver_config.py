import warnings

from app.config import Settings


def _settings(**overrides) -> Settings:
    values = {
        'APP_ENV': 'development',
        'DATABASE_URL': 'postgresql+psycopg2://user:pass@localhost:5432/test',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        'MES_ADAPTER': 'sqlserver',
        'MES_SQLSERVER_HOST': 'sqlserver.example.com',
        'MES_SQLSERVER_PORT': 1433,
        'MES_SQLSERVER_DATABASE': 'mes',
        'MES_SQLSERVER_USERNAME': 'readonly',
        'MES_SQLSERVER_PASSWORD': 'secret-pass',
    }
    values.update(overrides)
    return Settings(**values)


def test_sqlserver_adapter_requires_connection_env() -> None:
    runtime = _settings(
        MES_SQLSERVER_HOST='',
        MES_SQLSERVER_DATABASE='',
        MES_SQLSERVER_USERNAME='',
        MES_SQLSERVER_PASSWORD='',
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        runtime.validate_runtime_settings()

    message = str(caught[-1].message)
    assert 'MES_ADAPTER=sqlserver is missing' in message
    assert 'MES_SQLSERVER_HOST' in message
    assert 'MES_SQLSERVER_DATABASE' in message
    assert 'MES_SQLSERVER_USERNAME' in message
    assert 'MES_SQLSERVER_PASSWORD' in message
    assert 'secret-pass' not in message


def test_sqlserver_adapter_config_can_pass_without_warnings() -> None:
    runtime = _settings()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        runtime.validate_runtime_settings()

    assert caught == []
