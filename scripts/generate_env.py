from __future__ import annotations

import argparse
import secrets
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = ROOT_DIR / '.env'

WARNING_LINES = [
    '# ⚠ NEVER commit .env to version control',
    '# Generate SECRET_KEY: python -c "import secrets; print(secrets.token_hex(32))"',
    '# Generate POSTGRES_PASSWORD: python -c "import secrets; print(secrets.token_hex(16))"',
]


def prompt_value(label: str, default: str = '') -> str:
    prompt = f'{label}'
    if default:
        prompt += f' [{default}]'
    prompt += ': '
    value = input(prompt).strip()
    return value or default


def build_env_content(
    *,
    postgres_password: str,
    secret_key: str,
    admin_password: str,
    dingtalk_corp_id: str,
    dingtalk_app_key: str,
    dingtalk_app_secret: str,
    dingtalk_agent_id: str,
    app_env: str,
    cors_origins: str,
) -> str:
    lines = [
        *WARNING_LINES,
        '',
        f'APP_ENV={app_env}',
        '',
        '# PostgreSQL settings',
        'POSTGRES_USER=bypass_user',
        f'POSTGRES_PASSWORD={postgres_password}',
        'POSTGRES_DB=aluminum_bypass',
        '',
        '# Backend runtime settings',
        f'SECRET_KEY={secret_key}',
        'ALGORITHM=HS256',
        'ACCESS_TOKEN_EXPIRE_MINUTES=480',
        f'CORS_ORIGINS={cors_origins}',
        'DEFAULT_TIMEZONE=Asia/Shanghai',
        'UPLOAD_DIR=./backend/uploads',
        'MES_ADAPTER=null',
        'MES_API_BASE=',
        'MES_API_KEY=',
        'MES_API_TIMEOUT_SECONDS=8',
        'MES_API_TRACKING_CARD_INFO_PATH=/tracking-cards/{card_no}',
        'MES_API_COIL_SNAPSHOTS_PATH=/coil-snapshots',
        'MES_SYNC_LIMIT=200',
        'MES_SYNC_WINDOW_MINUTES=10',
        'MES_SYNC_POLL_MINUTES=1',
        'MES_SYNC_RETRY_LIMIT=3',
        'MES_SYNC_BACKOFF_SECONDS=2',
        '',
        '# Optional external integrations',
        f'DINGTALK_CORP_ID={dingtalk_corp_id}',
        f'DINGTALK_APP_KEY={dingtalk_app_key}',
        f'DINGTALK_APP_SECRET={dingtalk_app_secret}',
        f'DINGTALK_AGENT_ID={dingtalk_agent_id}',
        '',
        '# Workflow delivery toggles (keep disabled until adapters are wired)',
        'WORKFLOW_ENABLED=false',
        'AUTO_PUBLISH_ENABLED=true',
        'AUTO_PUSH_ENABLED=true',
        'AUTO_PIPELINE_REQUIRE_READY=true',
        'WECOM_BOT_ENABLED=false',
        'WECOM_BOT_DRY_RUN=false',
        'WECOM_BOT_WEBHOOK_URL=',
        'WECOM_BOT_MANAGEMENT_WEBHOOK_URL=',
        'WECOM_BOT_WORKSHOP_WEBHOOK_MAP={}',
        'WECOM_BOT_TEAM_WEBHOOK_MAP={}',
        'WECOM_BOT_TIMEOUT_SECONDS=8',
        'WECOM_APP_ENABLED=false',
        'WECOM_CORP_ID=',
        'WECOM_AGENT_ID=',
        'WECOM_APP_SECRET=',
        '',
        '# Statistics module usable-after-config',
        'LLM_ENABLED=false',
        'LLM_API_BASE=https://ark.cn-beijing.volces.com/api/v3',
        'LLM_API_KEY=',
        'LLM_ENDPOINT_ID=',
        'LLM_MODEL=DeepSeek-V3.2',
        'LLM_TIMEOUT_SECONDS=20',
        'APP_CONNECTION_ENABLED=false',
        'APP_CONNECTION_API_BASE=',
        'APP_CONNECTION_API_KEY=',
        'APP_CONNECTION_TIMEOUT_SECONDS=8',
        'APP_CONNECTION_PUSH_MODE=disabled',
        'MANAGEMENT_ESTIMATE_REVENUE_PER_TON=',
        'MANAGEMENT_ESTIMATE_ELECTRICITY_COST_PER_UNIT=',
        'MANAGEMENT_ESTIMATE_GAS_COST_PER_UNIT=',
        'MANAGEMENT_ESTIMATE_LABOR_COST_PER_ATTENDANCE=',
        '',
        '# Initial admin user',
        'INIT_ADMIN_USERNAME=admin',
        f'INIT_ADMIN_PASSWORD={admin_password}',
        'INIT_ADMIN_NAME=系统管理员',
        '',
        '# Frontend runtime settings',
        'VITE_API_BASE_URL=/api/v1',
    ]
    return '\n'.join(lines) + '\n'


def write_env_file(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    *,
    app_env: str = 'production',
    domain: str = '',
) -> Path:
    postgres_password = secrets.token_hex(16)
    secret_key = secrets.token_hex(32)
    admin_password = secrets.token_urlsafe(18)
    cors_origins = f'https://{domain}' if domain else 'http://localhost:8080,http://localhost:3000,http://localhost:5173'

    if domain:
        dingtalk_corp_id = ''
        dingtalk_app_key = ''
        dingtalk_app_secret = ''
        dingtalk_agent_id = ''
    else:
        print('Generate DingTalk settings. Leave blank if not ready yet.')
        dingtalk_corp_id = prompt_value('DINGTALK_CORP_ID')
        dingtalk_app_key = prompt_value('DINGTALK_APP_KEY')
        dingtalk_app_secret = prompt_value('DINGTALK_APP_SECRET')
        dingtalk_agent_id = prompt_value('DINGTALK_AGENT_ID')

    env_content = build_env_content(
        postgres_password=postgres_password,
        secret_key=secret_key,
        admin_password=admin_password,
        dingtalk_corp_id=dingtalk_corp_id,
        dingtalk_app_key=dingtalk_app_key,
        dingtalk_app_secret=dingtalk_app_secret,
        dingtalk_agent_id=dingtalk_agent_id,
        app_env=app_env,
        cors_origins=cors_origins,
    )
    output_path.write_text(env_content, encoding='utf-8')
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate a quick-trial .env file.')
    parser.add_argument('--app-env', default='production')
    parser.add_argument('--domain', default='')
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = write_env_file(
        Path(args.output),
        app_env=args.app_env,
        domain=args.domain,
    )
    print(f'Wrote secure environment template to {output_path}')


if __name__ == '__main__':
    main()
