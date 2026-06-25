from app.config import Settings


def build_settings(**overrides) -> Settings:
    values = {
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        '_env_file': None,
    }
    values.update(overrides)
    return Settings(**values)


def test_factory_brain_defaults_are_safe() -> None:
    settings = build_settings()

    assert settings.HERMES_FACTORY_BRAIN_ENABLED is False
    assert settings.HERMES_FACTORY_BRAIN_MODEL_PROVIDER == 'codex_token'
    assert settings.HERMES_CODEX_CONSTRUCTION_ENABLED is False
    assert settings.HERMES_LANGGRAPH_CHECKPOINT_SETUP_ON_START is False
    assert settings.HERMES_SOUL_PATH == 'app/hermes/Soul.md'


def test_factory_brain_validates_model_provider() -> None:
    settings = build_settings(HERMES_FACTORY_BRAIN_MODEL_PROVIDER='unknown-provider')

    issues = settings.validate_runtime()

    assert 'HERMES_FACTORY_BRAIN_MODEL_PROVIDER must be one of codex_token, service_llm' in issues


def test_factory_brain_validate_checkpoint_mode() -> None:
    settings = build_settings(HERMES_LANGGRAPH_CHECKPOINT_MODE='sqlite')

    issues = settings.validate_runtime()

    assert 'HERMES_LANGGRAPH_CHECKPOINT_MODE must be postgres' in issues


def test_factory_brain_validates_max_tool_steps() -> None:
    settings = build_settings(HERMES_FACTORY_BRAIN_MAX_TOOL_STEPS=0)

    issues = settings.validate_runtime()

    assert 'HERMES_FACTORY_BRAIN_MAX_TOOL_STEPS must be greater than 0' in issues


def test_factory_brain_validates_min_confidence() -> None:
    settings = build_settings(HERMES_FACTORY_BRAIN_MIN_CONFIDENCE=0)

    issues = settings.validate_runtime()

    assert 'HERMES_FACTORY_BRAIN_MIN_CONFIDENCE must be in (0, 1]' in issues
