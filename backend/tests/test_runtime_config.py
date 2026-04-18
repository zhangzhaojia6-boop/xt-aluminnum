import pytest

from app.config import EXAMPLE_ADMIN_PASSWORD, EXAMPLE_SECRET_KEY, Settings


def build_settings(**overrides) -> Settings:
    values = {
        'APP_ENV': 'development',
        'DATABASE_URL': 'postgresql+psycopg2://user:pass@localhost:5432/test',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
    }
    values.update(overrides)
    return Settings(**values)


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
    assert settings.WECOM_BOT_ENABLED is False
    assert settings.WECOM_BOT_DRY_RUN is False
    assert settings.WECOM_APP_ENABLED is False
    assert settings.LLM_ENABLED is False
    assert settings.APP_CONNECTION_ENABLED is False
    assert settings.app_connection_push_mode_normalized == 'disabled'
    settings.validate_runtime_settings()


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


def test_validate_runtime_settings_rejects_missing_wecom_app_credentials_in_production() -> None:
    settings = build_settings(
        APP_ENV='production',
        WORKFLOW_ENABLED=True,
        WECOM_APP_ENABLED=True,
    )

    with pytest.raises(RuntimeError) as exc_info:
        settings.validate_runtime_settings()

    assert 'WECOM_APP_ENABLED requires WECOM_CORP_ID, WECOM_AGENT_ID, and WECOM_APP_SECRET' in str(exc_info.value)


def test_validate_runtime_settings_rejects_missing_llm_fields_in_production() -> None:
    settings = build_settings(
        APP_ENV='production',
        LLM_ENABLED=True,
    )

    with pytest.raises(RuntimeError) as exc_info:
        settings.validate_runtime_settings()

    assert 'LLM_ENABLED requires LLM_API_BASE, LLM_API_KEY, and LLM_MODEL' in str(exc_info.value)


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
