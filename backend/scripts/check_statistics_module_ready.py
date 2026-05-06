"""统计模块可用性自检脚本。

用于在配置 `LLM API`、应用连接 API 和钉钉触达后，
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


def _issue(
    *,
    level: str,
    code: str,
    message: str,
    suggestion: str,
    required_env: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        'level': level,
        'code': code,
        'message': message,
        'suggestion': suggestion,
    }
    if required_env:
        payload['required_env'] = required_env
    return payload


def _scalar_int(db, statement: str) -> int:
    result = db.execute(text(statement))
    scalar = result.scalar() if hasattr(result, 'scalar') else result
    return int(scalar or 0)


def _count_active_dingtalk_bindings(session_factory) -> tuple[int | None, int | None, str | None]:
    try:
        db = session_factory()
        try:
            user_count = _scalar_int(
                db,
                """
                SELECT COUNT(*)
                FROM users
                WHERE is_active = true
                  AND dingtalk_user_id IS NOT NULL
                  AND TRIM(dingtalk_user_id) <> ''
                """,
            )
            employee_count = _scalar_int(
                db,
                """
                SELECT COUNT(*)
                FROM employees
                WHERE is_active = true
                  AND dingtalk_user_id IS NOT NULL
                  AND TRIM(dingtalk_user_id) <> ''
                """,
            )
            return user_count, employee_count, None
        finally:
            close = getattr(db, 'close', None)
            if callable(close):
                close()
    except SQLAlchemyError as exc:
        return None, None, exc.__class__.__name__


def build_external_env_template(*, runtime_settings: Settings | None = None) -> str:
    runtime = runtime_settings or settings
    mes_adapter = (runtime.MES_ADAPTER or 'null').strip().lower()
    lines: list[str] = [
        '# 数据中枢正式外部联通 .env 模板',
        '# 填入真实值后再运行: python scripts/check_statistics_module_ready.py --json',
        '# 不要把包含密钥的 .env 提交到 Git。',
        '',
    ]

    if mes_adapter == 'rest_api':
        lines.extend(
            [
                'MES_ADAPTER=rest_api',
                'MES_API_BASE=',
                'MES_API_KEY=',
            ]
        )
    else:
        lines.extend(
            [
                'MES_ADAPTER=mvc',
                'MES_MVC_BASE_URL=',
                'MES_MVC_USERNAME=',
                'MES_MVC_PASSWORD=',
                '',
                '# 如果现场使用 REST MES，改用下面三项替换上面的 MVC 配置：',
                '# MES_ADAPTER=rest_api',
                '# MES_API_BASE=',
                '# MES_API_KEY=',
            ]
        )

    lines.extend(
        [
            '',
            'WORKFLOW_ENABLED=true',
            'AUTO_PUBLISH_ENABLED=true',
            'AUTO_PUSH_ENABLED=true',
            '',
            'LLM_ENABLED=true',
            'LLM_API_BASE=',
            'LLM_API_KEY=',
            'LLM_MODEL=',
            '# 或使用 endpoint:',
            '# LLM_ENDPOINT_ID=',
            '',
            'DINGTALK_ENABLED=true',
            'DINGTALK_CORP_ID=',
            'DINGTALK_APP_KEY=',
            'DINGTALK_APP_SECRET=',
            'DINGTALK_AGENT_ID=',
            '',
            'APP_CONNECTION_ENABLED=true',
            'APP_CONNECTION_PUSH_MODE=enabled',
            'APP_CONNECTION_API_BASE=',
            'APP_CONNECTION_API_KEY=',
        ]
    )
    return '\n'.join(lines) + '\n'


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

    mes_adapter = (runtime.MES_ADAPTER or 'null').strip().lower()
    mes_ready = False
    if mes_adapter == 'null':
        issues.append(
            _issue(
                level='hard',
                code='MES_UNCONFIGURED',
                message='MES_ADAPTER=null，外部 MES 数据源未启用。',
                suggestion='将 MES_ADAPTER 设为 rest_api 或 mvc，并补齐对应连接配置。',
                required_env=[
                    'MES_ADAPTER',
                    'MES_API_BASE',
                    'MES_MVC_BASE_URL',
                    'MES_MVC_USERNAME',
                    'MES_MVC_PASSWORD',
                ],
            )
        )
    elif mes_adapter == 'rest_api':
        if _is_blank(runtime.MES_API_BASE):
            issues.append(
                _issue(
                    level='hard',
                    code='MES_REST_CONFIG_MISSING',
                    message='MES_ADAPTER=rest_api，但 MES_API_BASE 缺失。',
                    suggestion='补齐 MES_API_BASE，并确认外部 MES REST 接口可访问。',
                    required_env=['MES_ADAPTER', 'MES_API_BASE', 'MES_API_KEY'],
                )
            )
        else:
            mes_ready = True
    elif mes_adapter == 'mvc':
        missing_mvc_fields = [
            field_name
            for field_name, field_value in (
                ('MES_MVC_BASE_URL', runtime.MES_MVC_BASE_URL),
                ('MES_MVC_USERNAME', runtime.MES_MVC_USERNAME),
                ('MES_MVC_PASSWORD', runtime.MES_MVC_PASSWORD),
            )
            if _is_blank(field_value)
        ]
        if missing_mvc_fields:
            issues.append(
                _issue(
                    level='hard',
                    code='MES_MVC_CONFIG_MISSING',
                    message=f"MES_ADAPTER=mvc，但 {', '.join(missing_mvc_fields)} 缺失。",
                    suggestion='补齐 MES_MVC_BASE_URL / MES_MVC_USERNAME / MES_MVC_PASSWORD。',
                    required_env=['MES_ADAPTER', *missing_mvc_fields],
                )
            )
        else:
            mes_ready = True
    else:
        issues.append(
            _issue(
                level='hard',
                code='MES_ADAPTER_INVALID',
                message=f'MES_ADAPTER={runtime.MES_ADAPTER} 不受支持。',
                suggestion='将 MES_ADAPTER 设为 null、rest_api 或 mvc。',
                required_env=['MES_ADAPTER'],
            )
        )

    if not runtime.WORKFLOW_ENABLED:
        issues.append(
            _issue(
                level='hard',
                code='WORKFLOW_DISABLED',
                message='WORKFLOW_ENABLED=false，统计模块自动日报与外发链路未启用。',
                suggestion='将 WORKFLOW_ENABLED 设为 true。',
                required_env=['WORKFLOW_ENABLED'],
            )
        )

    if not runtime.AUTO_PUBLISH_ENABLED:
        issues.append(
            _issue(
                level='hard',
                code='AUTO_PUBLISH_DISABLED',
                message='AUTO_PUBLISH_ENABLED=false，日报不会自动发布。',
                suggestion='将 AUTO_PUBLISH_ENABLED 设为 true。',
                required_env=['AUTO_PUBLISH_ENABLED'],
            )
        )

    if not runtime.AUTO_PUSH_ENABLED:
        issues.append(
            _issue(
                level='hard',
                code='AUTO_PUSH_DISABLED',
                message='AUTO_PUSH_ENABLED=false，自动触达链路未启用。',
                suggestion='将 AUTO_PUSH_ENABLED 设为 true。',
                required_env=['AUTO_PUSH_ENABLED'],
            )
        )

    llm_ready = False
    if not runtime.LLM_ENABLED:
        issues.append(
            _issue(
                level='hard',
                code='LLM_DISABLED',
                message='LLM_ENABLED=false，LLM 摘要增强未启用。',
                suggestion='将 LLM_ENABLED 设为 true，并配置 LLM_API_BASE / LLM_API_KEY / LLM_MODEL 或 LLM_ENDPOINT_ID。',
                required_env=['LLM_ENABLED', 'LLM_API_BASE', 'LLM_API_KEY', 'LLM_MODEL', 'LLM_ENDPOINT_ID'],
            )
        )
    else:
        missing_llm_fields = [
            field_name
            for field_name, field_value in (
                ('LLM_API_BASE', runtime.LLM_API_BASE),
                ('LLM_API_KEY', runtime.LLM_API_KEY),
            )
            if _is_blank(field_value)
        ]
        has_llm_model_ref = not _is_blank(runtime.LLM_MODEL) or not _is_blank(runtime.LLM_ENDPOINT_ID)
        if not has_llm_model_ref:
            missing_llm_fields.append('(LLM_MODEL or LLM_ENDPOINT_ID)')
        if missing_llm_fields:
            issues.append(
                _issue(
                    level='hard',
                    code='LLM_CONFIG_MISSING',
                    message=f"LLM 已启用，但 {', '.join(missing_llm_fields)} 仍有缺失。",
                    suggestion='补齐 LLM API 地址、密钥和模型名或 endpoint ID。',
                    required_env=[
                        'LLM_API_BASE',
                        'LLM_API_KEY',
                        'LLM_MODEL',
                        'LLM_ENDPOINT_ID',
                    ],
                )
            )
        else:
            llm_ready = True

    dingtalk_ready = False
    active_dingtalk_user_count: int | None = None
    active_dingtalk_employee_count: int | None = None
    if not runtime.DINGTALK_ENABLED:
        issues.append(
            _issue(
                level='hard',
                code='DINGTALK_DISABLED',
                message='DINGTALK_ENABLED=false，领导钉钉日报触达未启用。',
                suggestion='将 DINGTALK_ENABLED 设为 true，并补齐钉钉应用配置。',
                required_env=[
                    'DINGTALK_ENABLED',
                    'DINGTALK_CORP_ID',
                    'DINGTALK_APP_KEY',
                    'DINGTALK_APP_SECRET',
                    'DINGTALK_AGENT_ID',
                ],
            )
        )
    elif any(
        _is_blank(value)
        for value in (
            runtime.DINGTALK_CORP_ID,
            runtime.DINGTALK_APP_KEY,
            runtime.DINGTALK_APP_SECRET,
            runtime.DINGTALK_AGENT_ID,
        )
    ):
        issues.append(
            _issue(
                level='hard',
                code='DINGTALK_CONFIG_MISSING',
                message='钉钉应用已启用，但 DINGTALK_CORP_ID / DINGTALK_APP_KEY / DINGTALK_APP_SECRET / DINGTALK_AGENT_ID 仍有缺失。',
                suggestion='补齐钉钉应用配置。',
                required_env=[
                    'DINGTALK_CORP_ID',
                    'DINGTALK_APP_KEY',
                    'DINGTALK_APP_SECRET',
                    'DINGTALK_AGENT_ID',
                ],
            )
        )
    else:
        dingtalk_ready = True
        if database_ok:
            (
                active_dingtalk_user_count,
                active_dingtalk_employee_count,
                dingtalk_binding_error,
            ) = _count_active_dingtalk_bindings(session_factory)
            if dingtalk_binding_error:
                issues.append(
                    _issue(
                        level='warning',
                        code='DINGTALK_BINDING_CHECK_UNAVAILABLE',
                        message=f'钉钉人员绑定数检查失败：{dingtalk_binding_error}。',
                        suggestion='请确认 users / employees 表结构已迁移，再重新运行 readiness 检查。',
                    )
                )
            elif active_dingtalk_user_count == 0 and active_dingtalk_employee_count == 0:
                issues.append(
                    _issue(
                        level='warning',
                        code='DINGTALK_NO_BOUND_USERS',
                        message='钉钉应用已启用，但没有 active 用户或员工绑定 dingtalk_user_id，工作通知无法送达真实人员。',
                        suggestion='先同步钉钉通讯录或给试点账号绑定 dingtalk_user_id，再做真实客户端 UAT。',
                    )
                )

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
                required_env=[
                    'APP_CONNECTION_ENABLED',
                    'APP_CONNECTION_PUSH_MODE',
                    'APP_CONNECTION_API_BASE',
                    'APP_CONNECTION_API_KEY',
                ],
            )
        )
    elif app_connection_mode == 'disabled':
        issues.append(
            _issue(
                level='hard',
                code='APP_CONNECTION_PUSH_DISABLED',
                message='APP_CONNECTION_PUSH_MODE=disabled，应用连接 API 未进入 dry-run 或 enabled 状态。',
                suggestion='将 APP_CONNECTION_PUSH_MODE 设为 enabled，并补齐应用连接 API 配置。',
                required_env=[
                    'APP_CONNECTION_PUSH_MODE',
                    'APP_CONNECTION_API_BASE',
                    'APP_CONNECTION_API_KEY',
                ],
            )
        )
    elif app_connection_mode == 'dry_run':
        issues.append(
            _issue(
                level='hard',
                code='APP_CONNECTION_DRY_RUN_ONLY',
                message='应用连接 API 当前仅处于 dry-run 状态。',
                suggestion='补齐 APP_CONNECTION_API_BASE / APP_CONNECTION_API_KEY，并将 APP_CONNECTION_PUSH_MODE 切到 enabled。',
                required_env=[
                    'APP_CONNECTION_PUSH_MODE',
                    'APP_CONNECTION_API_BASE',
                    'APP_CONNECTION_API_KEY',
                ],
            )
        )
    elif any(_is_blank(value) for value in (runtime.APP_CONNECTION_API_BASE, runtime.APP_CONNECTION_API_KEY)):
        issues.append(
            _issue(
                level='hard',
                code='APP_CONNECTION_CONFIG_MISSING',
                message='应用连接 API 已启用，但 APP_CONNECTION_API_BASE / APP_CONNECTION_API_KEY 仍有缺失。',
                suggestion='补齐应用连接 API 地址和密钥。',
                required_env=['APP_CONNECTION_API_BASE', 'APP_CONNECTION_API_KEY'],
            )
        )
    else:
        app_connection_ready = True
        external_connection_enabled = True

    local_runnable = runtime_valid and database_ok
    hard_issues = [item for item in issues if item['level'] == 'hard']
    warning_issues = [item for item in issues if item['level'] == 'warning']
    module_usable = (
        local_runnable
        and not hard_issues
        and mes_ready
        and llm_ready
        and dingtalk_ready
        and app_connection_ready
    )

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
            'mes_adapter': mes_adapter,
            'mes_ready': mes_ready,
            'llm_enabled': runtime.LLM_ENABLED,
            'llm_model_ref_set': not _is_blank(runtime.LLM_MODEL) or not _is_blank(runtime.LLM_ENDPOINT_ID),
            'dingtalk_enabled': runtime.DINGTALK_ENABLED,
            'active_dingtalk_user_count': active_dingtalk_user_count,
            'active_dingtalk_employee_count': active_dingtalk_employee_count,
            'app_connection_enabled': runtime.APP_CONNECTION_ENABLED,
            'app_connection_push_mode': app_connection_mode,
            'runtime_valid': runtime_valid,
            'database_ok': database_ok,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='统计模块可用性自检')
    parser.add_argument('--json', dest='json_mode', action='store_true', help='以 JSON 输出完整结果')
    parser.add_argument('--env-template', action='store_true', help='输出正式外部联通所需 .env 模板，不回显现有密钥')
    args = parser.parse_args()

    if args.env_template:
        print(build_external_env_template(), end='')
        return 0

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
                if item.get('required_env'):
                    print(f"  需配置：{', '.join(item['required_env'])}")
        if result['warning_issues']:
            print('\n建议修复问题：')
            for item in result['warning_issues']:
                print(f"- [{item['code']}] {item['message']}")
                print(f"  处理建议：{item['suggestion']}")
    return 0 if result['hard_gate_passed'] else 2


if __name__ == '__main__':
    sys.exit(main())
