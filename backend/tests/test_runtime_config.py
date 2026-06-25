from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from app.config import EXAMPLE_ADMIN_PASSWORD, EXAMPLE_SECRET_KEY, Settings


def build_settings(**overrides) -> Settings:
    values = {
        '_env_file': None,
        'APP_ENV': 'development',
        'DATABASE_URL': 'postgresql+psycopg2://user:pass@localhost:5432/test',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        'LLM_ENABLED': False,
        'LLM_API_BASE': None,
        'LLM_API_KEY': None,
        'LLM_MODEL': '',
        'LLM_ENDPOINT_ID': '',
        'WORKFLOW_ENABLED': False,
        'DINGTALK_ENABLED': False,
        'WECOM_BOT_ENABLED': False,
        'WECOM_BOT_DRY_RUN': False,
        'WECOM_APP_ENABLED': False,
        'APP_CONNECTION_ENABLED': False,
        'APP_CONNECTION_PUSH_MODE': 'disabled',
    }
    values.update(overrides)
    return Settings(**values)


def _read_alembic_sqlalchemy_url() -> str:
    alembic_ini = Path(__file__).resolve().parents[1] / 'alembic.ini'
    for line in alembic_ini.read_text(encoding='utf-8').splitlines():
        normalized = line.strip()
        if normalized.startswith('sqlalchemy.url'):
            return normalized.split('=', 1)[1].strip()
    raise AssertionError('sqlalchemy.url is missing from backend/alembic.ini')


def test_default_database_url_has_no_embedded_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('DATABASE_URL', raising=False)

    settings = Settings(_env_file=None)
    url = make_url(settings.DATABASE_URL)

    assert url.password in (None, '')


def test_alembic_ini_fallback_url_has_no_embedded_password() -> None:
    url = make_url(_read_alembic_sqlalchemy_url())

    assert url.password in (None, '')


def test_validate_runtime_settings_rejects_placeholder_values_in_production() -> None:
    settings = Settings(
        APP_ENV='production',
        DATABASE_URL='postgresql+psycopg2://user:pass@localhost:5432/test',
        SECRET_KEY=EXAMPLE_SECRET_KEY,
        INIT_ADMIN_PASSWORD=EXAMPLE_ADMIN_PASSWORD,
    )

    with pytest.raises(RuntimeError) as exc_info:
        settings.validate_runtime_settings()

    assert 'Unsafe runtime configuration' in str(exc_info.value)


def test_validate_runtime_settings_rejects_placeholder_values_in_trial() -> None:
    settings = Settings(
        APP_ENV='trial',
        DATABASE_URL='postgresql+psycopg2://user:pass@localhost:5432/test',
        SECRET_KEY=EXAMPLE_SECRET_KEY,
        INIT_ADMIN_PASSWORD=EXAMPLE_ADMIN_PASSWORD,
    )

    with pytest.raises(RuntimeError) as exc_info:
        settings.validate_runtime_settings()

    assert 'Unsafe runtime configuration for trial' in str(exc_info.value)


def test_validate_runtime_settings_warns_in_development() -> None:
    settings = Settings(
        APP_ENV='development',
        DATABASE_URL='postgresql+psycopg2://user:pass@localhost:5432/test',
        SECRET_KEY=EXAMPLE_SECRET_KEY,
        INIT_ADMIN_PASSWORD=EXAMPLE_ADMIN_PASSWORD,
    )

    with pytest.warns(RuntimeWarning):
        settings.validate_runtime_settings()


def test_workflow_related_feature_flags_default_to_disabled() -> None:
    settings = build_settings()

    assert settings.WORKFLOW_ENABLED is False
    assert settings.AUTO_PUBLISH_ENABLED is True
    assert settings.AUTO_PUSH_ENABLED is True
    assert settings.AUTO_PIPELINE_REQUIRE_READY is True
    assert settings.DINGTALK_ENABLED is False
    assert settings.WECOM_BOT_ENABLED is False
    assert settings.WECOM_BOT_DRY_RUN is False
    assert settings.WECOM_APP_ENABLED is False
    assert settings.LLM_ENABLED is False
    assert settings.APP_CONNECTION_ENABLED is False
    assert settings.app_connection_push_mode_normalized == 'disabled'
    settings.validate_runtime_settings()


def test_production_cors_defaults_to_public_data_center_domains() -> None:
    settings = build_settings(APP_ENV='production')

    assert settings.cors_origins_list == [
        'https://data.xintai-alu.com',
        'https://m.xintai-alu.com',
    ]


def test_validate_runtime_settings_warns_when_wecom_bot_enabled_without_workflow() -> None:
    settings = build_settings(WECOM_BOT_ENABLED=True)

    with pytest.warns(RuntimeWarning) as caught:
        settings.validate_runtime_settings()

    assert 'WECOM_BOT_ENABLED requires WORKFLOW_ENABLED=true' in str(caught[0].message)


def test_validate_runtime_settings_allows_wecom_bot_dry_run_without_webhook() -> None:
    settings = build_settings(
        WORKFLOW_ENABLED=True,
        WECOM_BOT_ENABLED=True,
        WECOM_BOT_DRY_RUN=True,
    )

    settings.validate_runtime_settings()


def test_validate_runtime_settings_rejects_missing_wecom_bot_targets_in_production() -> None:
    settings = build_settings(
        APP_ENV='production',
        WORKFLOW_ENABLED=True,
        WECOM_BOT_ENABLED=True,
    )

    with pytest.raises(RuntimeError) as exc_info:
        settings.validate_runtime_settings()

    assert 'WECOM_BOT_ENABLED requires at least one webhook target when dry-run is disabled' in str(exc_info.value)


def test_validate_runtime_settings_rejects_invalid_wecom_bot_target_maps() -> None:
    settings = build_settings(
        WORKFLOW_ENABLED=True,
        WECOM_BOT_ENABLED=True,
        WECOM_BOT_DRY_RUN=True,
        WECOM_BOT_TEAM_WEBHOOK_MAP='[]',
    )

    with pytest.warns(RuntimeWarning) as caught:
        settings.validate_runtime_settings()

    assert 'WECOM_BOT_TEAM_WEBHOOK_MAP must be a JSON object' in str(caught[0].message)


def test_validate_runtime_settings_allows_deprecated_wecom_app_flag_without_credentials() -> None:
    settings = build_settings(
        APP_ENV='production',
        WORKFLOW_ENABLED=True,
        WECOM_APP_ENABLED=True,
    )

    settings.validate_runtime_settings()


def test_validate_runtime_settings_rejects_missing_llm_fields_in_production() -> None:
    settings = build_settings(
        APP_ENV='production',
        LLM_ENABLED=True,
    )

    with pytest.raises(RuntimeError) as exc_info:
        settings.validate_runtime_settings()

    assert 'LLM_ENABLED requires LLM_API_BASE, LLM_API_KEY, and (LLM_MODEL or LLM_ENDPOINT_ID)' in str(exc_info.value)


def test_validate_runtime_settings_allows_llm_with_endpoint_id_only() -> None:
    settings = build_settings(
        APP_ENV='production',
        LLM_ENABLED=True,
        LLM_API_BASE='https://ark.cn-beijing.volces.com/api/v3',
        LLM_API_KEY='test-key',
        LLM_MODEL='',
        LLM_ENDPOINT_ID='ep-20260422-test',
    )

    settings.validate_runtime_settings()


def test_validate_runtime_settings_warns_when_rest_api_mes_adapter_has_no_base_url() -> None:
    settings = build_settings(MES_ADAPTER='rest_api')

    with pytest.warns(RuntimeWarning) as caught:
        settings.validate_runtime_settings()

    assert 'MES_ADAPTER=rest_api requires MES_API_BASE' in str(caught[0].message)


def test_validate_runtime_settings_warns_when_management_estimate_values_negative() -> None:
    settings = build_settings(MANAGEMENT_ESTIMATE_REVENUE_PER_TON=-1)

    with pytest.warns(RuntimeWarning) as caught:
        settings.validate_runtime_settings()

    assert 'MANAGEMENT_ESTIMATE_REVENUE_PER_TON must be zero or greater' in str(caught[0].message)


def test_validate_runtime_settings_warns_when_app_connection_enabled_without_workflow() -> None:
    settings = build_settings(
        APP_CONNECTION_ENABLED=True,
        APP_CONNECTION_PUSH_MODE='dry_run',
    )

    with pytest.warns(RuntimeWarning) as caught:
        settings.validate_runtime_settings()

    assert 'APP_CONNECTION_ENABLED requires WORKFLOW_ENABLED=true' in str(caught[0].message)


def test_validate_runtime_settings_allows_app_connection_dry_run() -> None:
    settings = build_settings(
        WORKFLOW_ENABLED=True,
        APP_CONNECTION_ENABLED=True,
        APP_CONNECTION_PUSH_MODE='dry_run',
    )

    settings.validate_runtime_settings()


def test_validate_runtime_settings_rejects_invalid_app_connection_push_mode() -> None:
    settings = build_settings(
        APP_CONNECTION_ENABLED=True,
        WORKFLOW_ENABLED=True,
        APP_CONNECTION_PUSH_MODE='sometimes',
    )

    with pytest.warns(RuntimeWarning) as caught:
        settings.validate_runtime_settings()

    assert 'APP_CONNECTION_PUSH_MODE must be one of disabled, dry_run, or enabled' in str(caught[0].message)


def test_validate_runtime_settings_rejects_missing_app_connection_fields_in_production() -> None:
    settings = build_settings(
        APP_ENV='production',
        WORKFLOW_ENABLED=True,
        APP_CONNECTION_ENABLED=True,
        APP_CONNECTION_PUSH_MODE='enabled',
    )

    with pytest.raises(RuntimeError) as exc_info:
        settings.validate_runtime_settings()

    assert 'APP_CONNECTION_PUSH_MODE=enabled is missing APP_CONNECTION_API_BASE, APP_CONNECTION_API_KEY' in str(exc_info.value)
