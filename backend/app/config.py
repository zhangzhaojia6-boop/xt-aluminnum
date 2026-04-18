import json
from pathlib import Path
import warnings

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_DEV_SECRET_KEY = 'dev-only-secret-key-change-before-production-2026'
DEFAULT_DEV_ADMIN_PASSWORD = 'DevAdmin#ChangeMe2026'
EXAMPLE_SECRET_KEY = 'CHANGE_ME_SECRET_KEY_FOR_DEPLOYMENT_ONLY_32CHARS_MIN'
EXAMPLE_ADMIN_PASSWORD = 'CHANGE_ME_ADMIN_PASSWORD_FOR_DEPLOYMENT'
WEAK_SECRET_KEY_VALUES = {
    '',
    'change-this-secret-key-in-production-min-32-chars',
    'replace-with-a-strong-secret-key-at-least-32-characters',
    EXAMPLE_SECRET_KEY,
    DEFAULT_DEV_SECRET_KEY,
}
WEAK_ADMIN_PASSWORD_VALUES = {
    '',
    'Admin@123456',
    EXAMPLE_ADMIN_PASSWORD,
    DEFAULT_DEV_ADMIN_PASSWORD,
}


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def _parse_json_object(value: str | None, *, setting_name: str) -> dict[str, str]:
    if _is_blank(value):
        return {}
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f'{setting_name} must be a JSON object') from exc
    if not isinstance(parsed, dict):
        raise ValueError(f'{setting_name} must be a JSON object')

    normalized: dict[str, str] = {}
    for raw_key, raw_value in parsed.items():
        key = str(raw_key).strip()
        value_text = str(raw_value).strip() if raw_value is not None else ''
        if key and value_text:
            normalized[key] = value_text
    return normalized


class Settings(BaseSettings):
    APP_NAME: str = '鑫泰铝业'
    API_V1_PREFIX: str = '/api/v1'
    APP_ENV: str = 'development'

    DATABASE_URL: str = 'postgresql+psycopg2://bypass_user:password@localhost:5432/aluminum_bypass'
    SECRET_KEY: str = DEFAULT_DEV_SECRET_KEY
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: str = 'http://localhost:5173,http://localhost:8080,http://localhost:3000'
    UPLOAD_DIR: str = './uploads'
    DEFAULT_TIMEZONE: str = 'Asia/Shanghai'
    MOBILE_DATA_ENTRY_MODE: str = 'manual_only'
    MOBILE_SCAN_ASSIST_ENABLED: bool = False
    MOBILE_MES_DISPLAY_ENABLED: bool = False
    MES_ADAPTER: str = 'null'
    MES_API_BASE: str | None = None
    MES_API_KEY: str | None = None
    MES_API_TIMEOUT_SECONDS: float = 8.0
    MES_API_TRACKING_CARD_INFO_PATH: str = '/tracking-cards/{card_no}'
    MES_API_COIL_SNAPSHOTS_PATH: str = '/coil-snapshots'
    MES_SYNC_LIMIT: int = 200
    MES_SYNC_WINDOW_MINUTES: int = 10
    MES_SYNC_POLL_MINUTES: int = 1
    MES_SYNC_RETRY_LIMIT: int = 3
    MES_SYNC_BACKOFF_SECONDS: float = 2.0
    MANAGEMENT_ESTIMATE_REVENUE_PER_TON: float | None = None
    MANAGEMENT_ESTIMATE_ELECTRICITY_COST_PER_UNIT: float | None = None
    MANAGEMENT_ESTIMATE_GAS_COST_PER_UNIT: float | None = None
    MANAGEMENT_ESTIMATE_LABOR_COST_PER_ATTENDANCE: float | None = None

    DINGTALK_CORP_ID: str | None = None
    DINGTALK_APP_KEY: str | None = None
    DINGTALK_APP_SECRET: str | None = None
    DINGTALK_AGENT_ID: str | None = None
    WORKFLOW_ENABLED: bool = False
    AUTO_PUBLISH_ENABLED: bool = True
    AUTO_PUSH_ENABLED: bool = True
    AUTO_PIPELINE_REQUIRE_READY: bool = True
    WECOM_BOT_ENABLED: bool = False
    WECOM_BOT_DRY_RUN: bool = False
    WECOM_BOT_WEBHOOK_URL: str | None = None
    WECOM_BOT_MANAGEMENT_WEBHOOK_URL: str | None = None
    WECOM_BOT_WORKSHOP_WEBHOOK_MAP: str | None = None
    WECOM_BOT_TEAM_WEBHOOK_MAP: str | None = None
    WECOM_BOT_TIMEOUT_SECONDS: float = 8.0
    WECOM_APP_ENABLED: bool = False
    WECOM_CORP_ID: str | None = None
    WECOM_AGENT_ID: str | None = None
    WECOM_APP_SECRET: str | None = None
    LLM_ENABLED: bool = False
    LLM_API_BASE: str | None = None
    LLM_API_KEY: str | None = None
    LLM_MODEL: str | None = None
    LLM_TIMEOUT_SECONDS: float = 20.0
    APP_CONNECTION_ENABLED: bool = False
    APP_CONNECTION_API_BASE: str | None = None
    APP_CONNECTION_API_KEY: str | None = None
    APP_CONNECTION_TIMEOUT_SECONDS: float = 8.0
    APP_CONNECTION_PUSH_MODE: str = 'disabled'
    MANAGEMENT_ESTIMATE_REVENUE_PER_TON: float | None = None
    MANAGEMENT_ESTIMATE_ELECTRICITY_COST_PER_UNIT: float | None = None
    MANAGEMENT_ESTIMATE_GAS_COST_PER_UNIT: float | None = None
    MANAGEMENT_ESTIMATE_LABOR_COST_PER_ATTENDANCE: float | None = None

    INIT_ADMIN_USERNAME: str = 'admin'
    INIT_ADMIN_PASSWORD: str = DEFAULT_DEV_ADMIN_PASSWORD
    INIT_ADMIN_NAME: str = '系统管理员'

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    @field_validator(
        'MANAGEMENT_ESTIMATE_REVENUE_PER_TON',
        'MANAGEMENT_ESTIMATE_ELECTRICITY_COST_PER_UNIT',
        'MANAGEMENT_ESTIMATE_GAS_COST_PER_UNIT',
        'MANAGEMENT_ESTIMATE_LABOR_COST_PER_ATTENDANCE',
        mode='before',
    )
    @classmethod
    def _blank_management_estimate_values_to_none(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [item.strip() for item in self.CORS_ORIGINS.split(',') if item.strip()]
        return origins or ['http://localhost:5173']

    @property
    def upload_dir_path(self) -> Path:
        return Path(self.UPLOAD_DIR)

    @property
    def app_env_normalized(self) -> str:
        return self.APP_ENV.strip().lower() or 'development'

    @property
    def is_production_like(self) -> bool:
        return self.app_env_normalized in {'production', 'prod', 'staging'}

    @property
    def wecom_bot_workshop_webhook_map(self) -> dict[str, str]:
        return _parse_json_object(self.WECOM_BOT_WORKSHOP_WEBHOOK_MAP, setting_name='WECOM_BOT_WORKSHOP_WEBHOOK_MAP')

    @property
    def wecom_bot_team_webhook_map(self) -> dict[str, str]:
        return _parse_json_object(self.WECOM_BOT_TEAM_WEBHOOK_MAP, setting_name='WECOM_BOT_TEAM_WEBHOOK_MAP')

    @property
    def app_connection_push_mode_normalized(self) -> str:
        return str(self.APP_CONNECTION_PUSH_MODE or 'disabled').strip().lower() or 'disabled'

    @property
    def mobile_data_entry_mode_normalized(self) -> str:
        return str(self.MOBILE_DATA_ENTRY_MODE or 'manual_only').strip().lower() or 'manual_only'

    @property
    def mes_api_tracking_card_info_path_normalized(self) -> str:
        value = str(self.MES_API_TRACKING_CARD_INFO_PATH or '').strip()
        return value or '/tracking-cards/{card_no}'

    @property
    def mes_api_coil_snapshots_path_normalized(self) -> str:
        value = str(self.MES_API_COIL_SNAPSHOTS_PATH or '').strip()
        return value or '/coil-snapshots'

    def validate_runtime_settings(self) -> None:
        issues: list[str] = []

        secret_key = self.SECRET_KEY.strip()
        admin_password = self.INIT_ADMIN_PASSWORD.strip()

        if secret_key in WEAK_SECRET_KEY_VALUES or len(secret_key) < 32:
            issues.append('SECRET_KEY is using a weak default value')

        if admin_password in WEAK_ADMIN_PASSWORD_VALUES or len(admin_password) < 12:
            issues.append('INIT_ADMIN_PASSWORD is using a weak default value')

        if self.WECOM_BOT_ENABLED and not self.WORKFLOW_ENABLED:
            issues.append('WECOM_BOT_ENABLED requires WORKFLOW_ENABLED=true')

        if self.WECOM_APP_ENABLED and not self.WORKFLOW_ENABLED:
            issues.append('WECOM_APP_ENABLED requires WORKFLOW_ENABLED=true')

        try:
            workshop_webhooks = self.wecom_bot_workshop_webhook_map
        except ValueError as exc:
            workshop_webhooks = {}
            issues.append(str(exc))

        try:
            team_webhooks = self.wecom_bot_team_webhook_map
        except ValueError as exc:
            team_webhooks = {}
            issues.append(str(exc))

        if self.WECOM_BOT_TIMEOUT_SECONDS <= 0:
            issues.append('WECOM_BOT_TIMEOUT_SECONDS must be greater than 0')

        if self.MES_API_TIMEOUT_SECONDS <= 0:
            issues.append('MES_API_TIMEOUT_SECONDS must be greater than 0')

        if self.MES_SYNC_LIMIT <= 0:
            issues.append('MES_SYNC_LIMIT must be greater than 0')

        if self.MES_SYNC_WINDOW_MINUTES <= 0:
            issues.append('MES_SYNC_WINDOW_MINUTES must be greater than 0')

        if self.MES_SYNC_POLL_MINUTES <= 0:
            issues.append('MES_SYNC_POLL_MINUTES must be greater than 0')

        if self.MES_SYNC_RETRY_LIMIT < 0:
            issues.append('MES_SYNC_RETRY_LIMIT must be zero or greater')

        if self.MES_SYNC_BACKOFF_SECONDS < 0:
            issues.append('MES_SYNC_BACKOFF_SECONDS must be zero or greater')

        if (self.MES_ADAPTER or 'null').strip().lower() == 'rest_api':
            if _is_blank(self.MES_API_BASE):
                issues.append('MES_ADAPTER=rest_api requires MES_API_BASE')
            if not str(self.MES_API_TRACKING_CARD_INFO_PATH or '').strip().startswith('/'):
                issues.append('MES_API_TRACKING_CARD_INFO_PATH must start with /')
            if not str(self.MES_API_COIL_SNAPSHOTS_PATH or '').strip().startswith('/'):
                issues.append('MES_API_COIL_SNAPSHOTS_PATH must start with /')

        for field_name, field_value in (
            ('MANAGEMENT_ESTIMATE_REVENUE_PER_TON', self.MANAGEMENT_ESTIMATE_REVENUE_PER_TON),
            ('MANAGEMENT_ESTIMATE_ELECTRICITY_COST_PER_UNIT', self.MANAGEMENT_ESTIMATE_ELECTRICITY_COST_PER_UNIT),
            ('MANAGEMENT_ESTIMATE_GAS_COST_PER_UNIT', self.MANAGEMENT_ESTIMATE_GAS_COST_PER_UNIT),
            ('MANAGEMENT_ESTIMATE_LABOR_COST_PER_ATTENDANCE', self.MANAGEMENT_ESTIMATE_LABOR_COST_PER_ATTENDANCE),
        ):
            if field_value is not None and field_value < 0:
                issues.append(f'{field_name} must be zero or greater')

        if self.LLM_TIMEOUT_SECONDS <= 0:
            issues.append('LLM_TIMEOUT_SECONDS must be greater than 0')

        if self.APP_CONNECTION_TIMEOUT_SECONDS <= 0:
            issues.append('APP_CONNECTION_TIMEOUT_SECONDS must be greater than 0')

        for setting_name, setting_value in (
            ('MANAGEMENT_ESTIMATE_REVENUE_PER_TON', self.MANAGEMENT_ESTIMATE_REVENUE_PER_TON),
            ('MANAGEMENT_ESTIMATE_ELECTRICITY_COST_PER_UNIT', self.MANAGEMENT_ESTIMATE_ELECTRICITY_COST_PER_UNIT),
            ('MANAGEMENT_ESTIMATE_GAS_COST_PER_UNIT', self.MANAGEMENT_ESTIMATE_GAS_COST_PER_UNIT),
            ('MANAGEMENT_ESTIMATE_LABOR_COST_PER_ATTENDANCE', self.MANAGEMENT_ESTIMATE_LABOR_COST_PER_ATTENDANCE),
        ):
            if setting_value is not None and setting_value < 0:
                issues.append(f'{setting_name} must be zero or greater')

        if self.WECOM_BOT_ENABLED and not self.WECOM_BOT_DRY_RUN:
            has_any_wecom_target = any(
                (
                    not _is_blank(self.WECOM_BOT_WEBHOOK_URL),
                    not _is_blank(self.WECOM_BOT_MANAGEMENT_WEBHOOK_URL),
                    bool(workshop_webhooks),
                    bool(team_webhooks),
                )
            )
            if not has_any_wecom_target:
                issues.append('WECOM_BOT_ENABLED requires at least one webhook target when dry-run is disabled')

        if self.WECOM_APP_ENABLED:
            missing_wecom_app_fields = [
                field_name
                for field_name, field_value in (
                    ('WECOM_CORP_ID', self.WECOM_CORP_ID),
                    ('WECOM_AGENT_ID', self.WECOM_AGENT_ID),
                    ('WECOM_APP_SECRET', self.WECOM_APP_SECRET),
                )
                if _is_blank(field_value)
            ]
            if missing_wecom_app_fields:
                if len(missing_wecom_app_fields) == 3:
                    issues.append(
                        'WECOM_APP_ENABLED requires WECOM_CORP_ID, WECOM_AGENT_ID, and WECOM_APP_SECRET'
                    )
                else:
                    issues.append(f"WECOM_APP_ENABLED is missing {', '.join(missing_wecom_app_fields)}")

        if self.LLM_ENABLED:
            missing_llm_fields = [
                field_name
                for field_name, field_value in (
                    ('LLM_API_BASE', self.LLM_API_BASE),
                    ('LLM_API_KEY', self.LLM_API_KEY),
                    ('LLM_MODEL', self.LLM_MODEL),
                )
                if _is_blank(field_value)
            ]
            if missing_llm_fields:
                if len(missing_llm_fields) == 3:
                    issues.append('LLM_ENABLED requires LLM_API_BASE, LLM_API_KEY, and LLM_MODEL')
                else:
                    issues.append(f"LLM_ENABLED is missing {', '.join(missing_llm_fields)}")

        app_connection_mode = self.app_connection_push_mode_normalized
        if app_connection_mode not in {'disabled', 'dry_run', 'enabled'}:
            issues.append('APP_CONNECTION_PUSH_MODE must be one of disabled, dry_run, or enabled')

        if self.APP_CONNECTION_ENABLED and not self.WORKFLOW_ENABLED:
            issues.append('APP_CONNECTION_ENABLED requires WORKFLOW_ENABLED=true')

        if self.APP_CONNECTION_ENABLED and app_connection_mode == 'disabled':
            issues.append('APP_CONNECTION_ENABLED requires APP_CONNECTION_PUSH_MODE=dry_run or enabled')

        if self.APP_CONNECTION_ENABLED and app_connection_mode == 'enabled':
            missing_app_connection_fields = [
                field_name
                for field_name, field_value in (
                    ('APP_CONNECTION_API_BASE', self.APP_CONNECTION_API_BASE),
                    ('APP_CONNECTION_API_KEY', self.APP_CONNECTION_API_KEY),
                )
                if _is_blank(field_value)
            ]
            if missing_app_connection_fields:
                issues.append(
                    f"APP_CONNECTION_PUSH_MODE=enabled is missing {', '.join(missing_app_connection_fields)}"
                )

        mobile_data_entry_mode = self.mobile_data_entry_mode_normalized
        if mobile_data_entry_mode not in {'manual_only', 'scan_assisted', 'mes_assisted'}:
            issues.append('MOBILE_DATA_ENTRY_MODE must be one of manual_only, scan_assisted, or mes_assisted')

        mes_adapter_name = (self.MES_ADAPTER or 'null').strip().lower()
        if mes_adapter_name not in {'null', 'rest_api'}:
            issues.append('MES_ADAPTER must be null or rest_api')

        if mobile_data_entry_mode == 'manual_only' and self.MOBILE_SCAN_ASSIST_ENABLED:
            issues.append('manual_only cannot enable MOBILE_SCAN_ASSIST_ENABLED')

        if mobile_data_entry_mode == 'manual_only' and self.MOBILE_MES_DISPLAY_ENABLED:
            issues.append('manual_only cannot enable MOBILE_MES_DISPLAY_ENABLED')

        if mobile_data_entry_mode == 'mes_assisted' and mes_adapter_name == 'null':
            issues.append('mes_assisted requires MES_ADAPTER=rest_api')

        if mes_adapter_name == 'rest_api':
            missing_mes_fields = [
                field_name
                for field_name, field_value in (
                    ('MES_API_BASE', self.MES_API_BASE),
                    ('MES_API_TRACKING_CARD_INFO_PATH', self.mes_api_tracking_card_info_path_normalized),
                    ('MES_API_COIL_SNAPSHOTS_PATH', self.mes_api_coil_snapshots_path_normalized),
                )
                if _is_blank(field_value)
            ]
            if missing_mes_fields:
                issues.append(f"MES_ADAPTER=rest_api is missing {', '.join(missing_mes_fields)}")

        if not issues:
            return

        message = '; '.join(issues)
        if self.is_production_like:
            raise RuntimeError(f'Unsafe runtime configuration for {self.app_env_normalized}: {message}')

        warnings.warn(
            f'Running with development-only configuration in {self.app_env_normalized}: {message}',
            RuntimeWarning,
            stacklevel=2,
        )


settings = Settings()
