"""统计模块可用性自检脚本。

用于在配置 `LLM API`、应用连接 API 和企业微信触达后，
快速判断统计模块是否达到“配置后即可用”的最低门槛。
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import Settings, settings
from app.database import get_sessionmaker


def _is_blank(value: str | None) -> bool:
    return value is None or not str(value).strip()


def _issue(*, level: str, code: str, message: str, suggestion: str) -> dict[str, Any]:
    return {
        'level': level,
        'code': code,
        'message': message,
        'suggestion': suggestion,
    }


def inspect_statistics_module_ready(
    *,
    runtime_settings: Settings | None = None,
    sessionmaker_factory=None,
) -> dict[str, Any]:
    runtime = runtime_settings or settings
    issues: list[dict[str, Any]] = []

    runtime_valid = True
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try:
            runtime.validate_runtime_settings()
        except RuntimeError as exc:
            runtime_valid = False
            issues.append(
                _issue(
                    level='hard',
                    code='RUNTIME_CONFIG_INVALID',
                    message=str(exc),
                    suggestion='请先修复 .env / docker-compose 中的非法配置项。',
                )
            )
        for item in caught:
            issues.append(
                _issue(
                    level='warning',
                    code='RUNTIME_CONFIG_WARNING',
                    message=str(item.message),
                    suggestion='请按警告修正配置，避免统计模块处于可运行但不可用状态。',
                )
            )

    database_ok = True
    session_factory = sessionmaker_factory or get_sessionmaker()
    try:
        db = session_factory()
        try:
            db.execute(text('SELECT 1'))
        finally:
            close = getattr(db, 'close', None)
            if callable(close):
                close()
    except SQLAlchemyError as exc:
        database_ok = False
        issues.append(
            _issue(
                level='hard',
                code='DATABASE_UNAVAILABLE',
                message=f'统计模块无法连接数据库：{exc.__class__.__name__}',
                suggestion='请确认数据库服务可用，且 .env 中数据库账号密码正确。',
            )
        )

    if not runtime.WORKFLOW_ENABLED:
        issues.append(
            _issue(
                level='hard',
                code='WORKFLOW_DISABLED',
                message='WORKFLOW_ENABLED=false，统计模块自动日报与外发链路未启用。',
                suggestion='将 WORKFLOW_ENABLED 设为 true。',
            )
        )

    if not runtime.AUTO_PUBLISH_ENABLED:
        issues.append(
            _issue(
                level='hard',
                code='AUTO_PUBLISH_DISABLED',
                message='AUTO_PUBLISH_ENABLED=false，日报不会自动发布。',
                suggestion='将 AUTO_PUBLISH_ENABLED 设为 true。',
            )
        )

    if not runtime.AUTO_PUSH_ENABLED:
        issues.append(
            _issue(
                level='hard',
                code='AUTO_PUSH_DISABLED',
                message='AUTO_PUSH_ENABLED=false，自动触达链路未启用。',
                suggestion='将 AUTO_PUSH_ENABLED 设为 true。',
            )
        )

    llm_ready = False
    if not runtime.LLM_ENABLED:
        issues.append(
            _issue(
                level='hard',
                code='LLM_DISABLED',
                message='LLM_ENABLED=false，LLM 摘要增强未启用。',
                suggestion='将 LLM_ENABLED 设为 true，并配置 LLM_API_BASE / LLM_API_KEY / LLM_MODEL。',
            )
        )
    elif any(_is_blank(value) for value in (runtime.LLM_API_BASE, runtime.LLM_API_KEY, runtime.LLM_MODEL)):
        issues.append(
            _issue(
                level='hard',
                code='LLM_CONFIG_MISSING',
                message='LLM 已启用，但 LLM_API_BASE / LLM_API_KEY / LLM_MODEL 仍有缺失。',
                suggestion='补齐 LLM API 地址、密钥和模型名。',
            )
        )
    else:
        llm_ready = True

    wecom_ready = False
    if not runtime.WECOM_APP_ENABLED:
        issues.append(
            _issue(
                level='hard',
                code='WECOM_APP_DISABLED',
                message='WECOM_APP_ENABLED=false，领导微信日报触达未启用。',
                suggestion='将 WECOM_APP_ENABLED 设为 true，并补齐企业微信应用配置。',
            )
        )
    elif any(_is_blank(value) for value in (runtime.WECOM_CORP_ID, runtime.WECOM_AGENT_ID, runtime.WECOM_APP_SECRET)):
        issues.append(
            _issue(
                level='hard',
                code='WECOM_APP_CONFIG_MISSING',
                message='企业微信应用已启用，但 WECOM_CORP_ID / WECOM_AGENT_ID / WECOM_APP_SECRET 仍有缺失。',
                suggestion='补齐企业微信应用配置。',
            )
        )
    else:
        wecom_ready = True

    app_connection_mode = runtime.app_connection_push_mode_normalized
    app_connection_ready = False
    external_connection_enabled = False
    if not runtime.APP_CONNECTION_ENABLED:
        issues.append(
            _issue(
                level='hard',
                code='APP_CONNECTION_DISABLED',
                message='APP_CONNECTION_ENABLED=false，统计模块对外连接面未启用。',
                suggestion='将 APP_CONNECTION_ENABLED 设为 true。',
            )
        )
    elif app_connection_mode == 'disabled':
        issues.append(
            _issue(
                level='hard',
                code='APP_CONNECTION_PUSH_DISABLED',
                message='APP_CONNECTION_PUSH_MODE=disabled，应用连接 API 未进入 dry-run 或 enabled 状态。',
                suggestion='将 APP_CONNECTION_PUSH_MODE 设为 dry_run 或 enabled。',
            )
        )
    elif app_connection_mode == 'dry_run':
        app_connection_ready = True
        issues.append(
            _issue(
                level='warning',
                code='APP_CONNECTION_DRY_RUN_ONLY',
                message='应用连接 API 当前仅处于 dry-run 状态。',
                suggestion='如需真实对外连接，请补齐 APP_CONNECTION_API_BASE / APP_CONNECTION_API_KEY 并切到 enabled。',
            )
        )
    elif any(_is_blank(value) for value in (runtime.APP_CONNECTION_API_BASE, runtime.APP_CONNECTION_API_KEY)):
        issues.append(
            _issue(
                level='hard',
                code='APP_CONNECTION_CONFIG_MISSING',
                message='应用连接 API 已启用，但 APP_CONNECTION_API_BASE / APP_CONNECTION_API_KEY 仍有缺失。',
                suggestion='补齐应用连接 API 地址和密钥。',
            )
        )
    else:
        app_connection_ready = True
        external_connection_enabled = True

    local_runnable = runtime_valid and database_ok
    hard_issues = [item for item in issues if item['level'] == 'hard']
    warning_issues = [item for item in issues if item['level'] == 'warning']
    module_usable = local_runnable and not hard_issues and llm_ready and wecom_ready and app_connection_ready

    return {
        'hard_gate_passed': module_usable,
        'local_runnable': local_runnable,
        'module_usable': module_usable,
        'external_connection_enabled': external_connection_enabled,
        'hard_issues': hard_issues,
        'warning_issues': warning_issues,
        'stats': {
            'workflow_enabled': runtime.WORKFLOW_ENABLED,
            'auto_publish_enabled': runtime.AUTO_PUBLISH_ENABLED,
            'auto_push_enabled': runtime.AUTO_PUSH_ENABLED,
            'llm_enabled': runtime.LLM_ENABLED,
            'wecom_app_enabled': runtime.WECOM_APP_ENABLED,
            'app_connection_enabled': runtime.APP_CONNECTION_ENABLED,
            'app_connection_push_mode': app_connection_mode,
            'runtime_valid': runtime_valid,
            'database_ok': database_ok,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='统计模块可用性自检')
    parser.add_argument('--json', dest='json_mode', action='store_true', help='以 JSON 输出完整结果')
    args = parser.parse_args()

    result = inspect_statistics_module_ready()
    if args.json_mode:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"本地可运行：{'是' if result['local_runnable'] else '否'}")
        print(f"统计模块可用：{'是' if result['module_usable'] else '否'}")
        print(f"对外连接已启用：{'是' if result['external_connection_enabled'] else '否'}")
        print('统计信息：')
        for key, value in result['stats'].items():
            print(f'- {key}: {value}')
        if result['hard_issues']:
            print('\n硬门槛问题：')
            for item in result['hard_issues']:
                print(f"- [{item['code']}] {item['message']}")
                print(f"  处理建议：{item['suggestion']}")
        if result['warning_issues']:
            print('\n建议修复问题：')
            for item in result['warning_issues']:
                print(f"- [{item['code']}] {item['message']}")
                print(f"  处理建议：{item['suggestion']}")
    return 0 if result['hard_gate_passed'] else 2


if __name__ == '__main__':
    sys.exit(main())
