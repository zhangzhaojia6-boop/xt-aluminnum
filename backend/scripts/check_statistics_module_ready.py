"""统计模块可用性自检脚本。

用于在配置 `LLM API`、应用连接 API 和钉钉触达后，
快速判断统计模块是否达到“配置后即可用”的最低门槛。
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

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


_MISSING_INPUT_CATALOG: dict[str, dict[str, Any]] = {
    'MES_UNCONFIGURED': {
        'purpose': '外部 MES 数据源',
        'location': '服务器 backend/.env',
        'missing_fields': ['MES_ADAPTER', 'MES_MVC_BASE_URL', 'MES_MVC_USERNAME', 'MES_MVC_PASSWORD'],
        'impact': '外部 MES 投影不可用，实时流转与机列绑定只能依赖本地填报。',
        'suggested_value': 'MES_ADAPTER=mvc；其余字段填现场 MES 地址和账号密钥。',
    },
    'MES_REST_CONFIG_MISSING': {
        'purpose': '外部 MES REST 数据源',
        'location': '服务器 backend/.env',
        'missing_fields': ['MES_ADAPTER', 'MES_API_BASE', 'MES_API_KEY'],
        'impact': '外部 MES REST 同步不可用。',
        'suggested_value': 'MES_ADAPTER=rest_api；MES_API_BASE=<现场提供>；MES_API_KEY=<现场提供>。',
    },
    'MES_MVC_CONFIG_MISSING': {
        'purpose': '外部 MES MVC 数据源',
        'location': '服务器 backend/.env',
        'missing_fields': ['MES_ADAPTER', 'MES_MVC_BASE_URL', 'MES_MVC_USERNAME', 'MES_MVC_PASSWORD'],
        'impact': '外部 MES MVC 同步不可用。',
        'suggested_value': 'MES_ADAPTER=mvc；MES_MVC_BASE_URL=<现场提供>；MES_MVC_USERNAME=<现场提供>；MES_MVC_PASSWORD=<现场提供>。',
    },
    'WORKFLOW_DISABLED': {
        'purpose': '自动日报 workflow',
        'location': '服务器 backend/.env',
        'missing_fields': ['WORKFLOW_ENABLED'],
        'impact': '自动日报生成与后续触达链路不会运行。',
        'suggested_value': 'WORKFLOW_ENABLED=true。',
    },
    'AUTO_PUBLISH_DISABLED': {
        'purpose': '日报自动发布',
        'location': '服务器 backend/.env',
        'missing_fields': ['AUTO_PUBLISH_ENABLED'],
        'impact': '日报生成后不会进入发布状态。',
        'suggested_value': 'AUTO_PUBLISH_ENABLED=true。',
    },
    'AUTO_PUSH_DISABLED': {
        'purpose': '日报自动触达',
        'location': '服务器 backend/.env',
        'missing_fields': ['AUTO_PUSH_ENABLED'],
        'impact': '日报不会自动推送到外部触达通道。',
        'suggested_value': 'AUTO_PUSH_ENABLED=true。',
    },
    'LLM_DISABLED': {
        'purpose': 'LLM/AI 摘要增强',
        'location': '服务器 backend/.env',
        'missing_fields': ['LLM_ENABLED', 'LLM_API_BASE', 'LLM_API_KEY', 'LLM_MODEL', 'LLM_ENDPOINT_ID'],
        'impact': 'AI 摘要与分析增强不可用，不能宣称 AI 能力正式联通。',
        'suggested_value': 'LLM_ENABLED=true；LLM_API_BASE=<现场提供>；LLM_API_KEY=<现场提供>；LLM_MODEL=<模型名> 或 LLM_ENDPOINT_ID=<endpoint>。',
    },
    'LLM_CONFIG_MISSING': {
        'purpose': 'LLM/AI 摘要增强',
        'location': '服务器 backend/.env',
        'missing_fields': ['LLM_API_BASE', 'LLM_API_KEY', 'LLM_MODEL', 'LLM_ENDPOINT_ID'],
        'impact': 'AI 摘要与分析增强不可用，不能宣称 AI 能力正式联通。',
        'suggested_value': 'LLM_API_BASE=<现场提供>；LLM_API_KEY=<现场提供>；LLM_MODEL=<模型名> 或 LLM_ENDPOINT_ID=<endpoint>。',
    },
    'DINGTALK_DISABLED': {
        'purpose': '钉钉日报触达',
        'location': '服务器 backend/.env',
        'missing_fields': ['DINGTALK_ENABLED', 'DINGTALK_CORP_ID', 'DINGTALK_APP_KEY', 'DINGTALK_APP_SECRET', 'DINGTALK_AGENT_ID'],
        'impact': '日报和提醒不能发送到钉钉。',
        'suggested_value': 'DINGTALK_ENABLED=true；其余字段填钉钉开放平台真实应用配置。',
    },
    'DINGTALK_CONFIG_MISSING': {
        'purpose': '钉钉日报触达',
        'location': '服务器 backend/.env',
        'missing_fields': ['DINGTALK_CORP_ID', 'DINGTALK_APP_KEY', 'DINGTALK_APP_SECRET', 'DINGTALK_AGENT_ID'],
        'impact': '日报和提醒不能发送到钉钉。',
        'suggested_value': '填钉钉开放平台真实应用配置，不写入 Git。',
    },
    'DINGTALK_NO_BOUND_USERS': {
        'purpose': '钉钉真实人员触达',
        'location': '生产数据库 users/employees 与钉钉通讯录',
        'missing_fields': ['users.dingtalk_user_id', 'employees.dingtalk_user_id'],
        'impact': 'token 可用但通知不能送达真实人员，真实客户端 UAT 不能闭环。',
        'suggested_value': '同步通讯录后，为试点 active 用户或员工绑定真实 dingtalk_user_id。',
    },
    'DINGTALK_CONTACTS_PERMISSION_MISSING': {
        'purpose': '钉钉通讯录同步',
        'location': '钉钉开放平台应用权限',
        'missing_fields': ['qyapi_get_department_member'],
        'impact': '无法读取通讯录成员，不能自动完成人员绑定。',
        'suggested_value': '给当前钉钉应用开通通讯录成员读取权限后重跑只读诊断。',
    },
    'APP_CONNECTION_DISABLED': {
        'purpose': '应用连接外发',
        'location': '服务器 backend/.env',
        'missing_fields': ['APP_CONNECTION_ENABLED', 'APP_CONNECTION_PUSH_MODE', 'APP_CONNECTION_API_BASE', 'APP_CONNECTION_API_KEY'],
        'impact': '统计模块不能对外推送，正式外部连接面未启用。',
        'suggested_value': 'APP_CONNECTION_ENABLED=true；APP_CONNECTION_PUSH_MODE=enabled；APP_CONNECTION_API_BASE=<现场提供>；APP_CONNECTION_API_KEY=<现场提供>。',
    },
    'APP_CONNECTION_PUSH_DISABLED': {
        'purpose': '应用连接外发',
        'location': '服务器 backend/.env',
        'missing_fields': ['APP_CONNECTION_PUSH_MODE', 'APP_CONNECTION_API_BASE', 'APP_CONNECTION_API_KEY'],
        'impact': '应用连接 API 未进入可外发状态。',
        'suggested_value': 'APP_CONNECTION_PUSH_MODE=enabled；APP_CONNECTION_API_BASE=<现场提供>；APP_CONNECTION_API_KEY=<现场提供>。',
    },
    'APP_CONNECTION_DRY_RUN_ONLY': {
        'purpose': '应用连接外发',
        'location': '服务器 backend/.env',
        'missing_fields': ['APP_CONNECTION_PUSH_MODE', 'APP_CONNECTION_API_BASE', 'APP_CONNECTION_API_KEY'],
        'impact': '应用连接仍是 dry-run，不能作为正式外发证据。',
        'suggested_value': 'APP_CONNECTION_PUSH_MODE=enabled；APP_CONNECTION_API_BASE=<现场提供>；APP_CONNECTION_API_KEY=<现场提供>。',
    },
    'APP_CONNECTION_CONFIG_MISSING': {
        'purpose': '应用连接外发',
        'location': '服务器 backend/.env',
        'missing_fields': ['APP_CONNECTION_API_BASE', 'APP_CONNECTION_API_KEY'],
        'impact': '应用连接 API 已启用但没有真实地址或密钥。',
        'suggested_value': 'APP_CONNECTION_API_BASE=<现场提供>；APP_CONNECTION_API_KEY=<现场提供>。',
    },
    'APP_CONNECTION_LIVE_FAILED': {
        'purpose': '应用连接外发',
        'location': '外部应用连接 API',
        'missing_fields': ['APP_CONNECTION_API_BASE', 'APP_CONNECTION_API_KEY'],
        'impact': '应用连接 API 已配置但 readiness 测试 POST 未收到 2xx，不能证明正式外发可用。',
        'suggested_value': '确认下游 API 地址、Bearer 密钥、网络白名单和 2xx 响应后重跑 --check-app-connection-live。',
    },
}


def _missing_input_from_issue(issue: dict[str, Any]) -> dict[str, Any] | None:
    code = str(issue.get('code') or '').strip()
    catalog_item = _MISSING_INPUT_CATALOG.get(code)
    if catalog_item:
        return {
            'issue_code': code,
            'level': issue.get('level') or 'hard',
            **catalog_item,
        }
    required_env = issue.get('required_env') or []
    if not required_env:
        return None
    return {
        'issue_code': code,
        'level': issue.get('level') or 'hard',
        'purpose': issue.get('message') or code,
        'location': '服务器 backend/.env',
        'missing_fields': list(required_env),
        'impact': issue.get('message') or '正式试用前需要补齐该项。',
        'suggested_value': issue.get('suggestion') or '按现场真实配置填写。',
    }


def build_missing_inputs(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        row = _missing_input_from_issue(issue)
        if row is None:
            continue
        key = (str(row['issue_code']), str(row['purpose']))
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def _format_missing_fields(fields: list[str]) -> str:
    return '、'.join(f'`{item}`' for item in fields)


def _table_cell(value: object) -> str:
    return str(value if value is not None else '').replace('\n', '<br>').replace('|', '\\|')


def format_missing_inputs_markdown(missing_inputs: list[dict[str, Any]]) -> str:
    if not missing_inputs:
        return '当前没有缺失外部输入。\n'
    lines = [
        '| 用途 | 所在位置 | 缺失字段 | 影响范围 | 建议取值 |',
        '| --- | --- | --- | --- | --- |',
    ]
    for item in missing_inputs:
        lines.append(
            '| '
            + ' | '.join(
                [
                    _table_cell(item.get('purpose')),
                    _table_cell(item.get('location')),
                    _table_cell(_format_missing_fields(item.get('missing_fields') or [])),
                    _table_cell(item.get('impact')),
                    _table_cell(item.get('suggested_value')),
                ]
            )
            + ' |'
        )
    return '\n'.join(lines) + '\n'


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


def _default_dingtalk_contacts_checker(*, department_id: int) -> dict[str, Any]:
    from scripts.dingtalk_cli import check_department_contacts

    return check_department_contacts(department_id=department_id)


def _default_live_aggregation_probe(db) -> dict[str, Any]:
    from app.services import realtime_service

    active_date_payload = realtime_service.resolve_live_business_date(db)
    business_date = date.fromisoformat(str(active_date_payload.get('business_date')))
    probe_user = SimpleNamespace(
        id=0,
        role='admin',
        data_scope_type='all',
        workshop_id=None,
        team_id=None,
        assigned_shift_ids=[],
        is_manager=True,
        is_reviewer=True,
        is_mobile_user=False,
    )
    payload = realtime_service.build_live_aggregation(
        db,
        business_date=business_date,
        workshop_id=None,
        current_user=probe_user,
    )
    progress = payload.get('overall_progress') or {}
    binding = payload.get('mes_machine_binding') or {}
    pending_assignment = progress.get('pending_assignment') or {}
    pending_assignment_count = binding.get('pending_assignment_entry_count')
    if pending_assignment_count is None:
        pending_assignment_count = pending_assignment.get('entry_count')
    return {
        'business_date': payload.get('business_date') or business_date.isoformat(),
        'business_date_source': active_date_payload.get('source') or 'unknown',
        'data_source': payload.get('data_source'),
        'total_entry_count': progress.get('total_entry_count'),
        'formal_entry_count': progress.get('formal_entry_count'),
        'draft_entry_count': progress.get('draft_entry_count'),
        'mes_row_count': binding.get('mes_row_count'),
        'fill_entries_with_mes_match': binding.get('fill_entries_with_mes_match'),
        'fill_entries_bound_to_machine': binding.get('fill_entries_bound_to_machine'),
        'pending_assignment_entry_count': pending_assignment_count,
    }


def _run_live_aggregation_probe(
    session_factory,
    live_aggregation_probe: Callable[[Any], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], str | None]:
    probe = live_aggregation_probe or _default_live_aggregation_probe
    try:
        db = session_factory()
        try:
            payload = probe(db)
        finally:
            close = getattr(db, 'close', None)
            if callable(close):
                close()
    except Exception as exc:  # noqa: BLE001
        return {}, exc.__class__.__name__

    return {
        'business_date': payload.get('business_date'),
        'business_date_source': payload.get('business_date_source'),
        'data_source': payload.get('data_source'),
        'total_entry_count': payload.get('total_entry_count'),
        'formal_entry_count': payload.get('formal_entry_count'),
        'draft_entry_count': payload.get('draft_entry_count'),
        'mes_row_count': payload.get('mes_row_count'),
        'fill_entries_with_mes_match': payload.get('fill_entries_with_mes_match'),
        'fill_entries_bound_to_machine': payload.get('fill_entries_bound_to_machine'),
        'pending_assignment_entry_count': payload.get('pending_assignment_entry_count'),
    }, None


def _build_app_connection_live_probe_payload() -> dict[str, Any]:
    today = date.today().isoformat()
    return {
        'payload_version': 1,
        'dispatch_key': f"readiness:{datetime.now(timezone.utc).isoformat()}",
        'report_date': today,
        'metrics': {
            'report_date': today,
            'total_output_weight': 0,
            'total_energy': 0,
            'energy_per_ton': 0,
            'reporting_rate': 0,
            'total_attendance': 0,
            'contract_weight': 0,
            'yield_rate': 0,
            'anomaly_total': 0,
            'anomaly_digest': '应用连接联通测试',
            'in_process_weight': 0,
            'consumable_weight': 0,
        },
        'leader_summary': '数据中枢应用连接联通测试',
        'delivery_status': {
            'report_id': 0,
            'status': 'readiness_check',
            'generated_scope': 'readiness_probe',
        },
        'summary_source': 'deterministic',
    }


def _default_app_connection_live_probe(runtime_settings: Settings) -> dict[str, Any]:
    from app.services.app_connection_service import dispatch_app_connection_payload

    return dispatch_app_connection_payload(
        payload=_build_app_connection_live_probe_payload(),
        settings=runtime_settings,
    )


def _run_app_connection_live_probe(
    runtime_settings: Settings,
    app_connection_live_probe: Callable[[Settings], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], str | None]:
    probe = app_connection_live_probe or _default_app_connection_live_probe
    try:
        payload = probe(runtime_settings)
    except Exception as exc:  # noqa: BLE001
        return {}, exc.__class__.__name__
    return payload, None


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
    check_dingtalk_contacts: bool = False,
    dingtalk_department_id: int = 1,
    dingtalk_contacts_checker: Callable[..., dict[str, Any]] | None = None,
    check_live_aggregation: bool = False,
    live_aggregation_probe: Callable[[Any], dict[str, Any]] | None = None,
    check_app_connection_live: bool = False,
    app_connection_live_probe: Callable[[Settings], dict[str, Any]] | None = None,
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
    dingtalk_department_access: bool | None = None
    dingtalk_contacts_missing_scope: str | None = None
    dingtalk_contact_count: int | None = None
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
        if check_dingtalk_contacts:
            checker = dingtalk_contacts_checker or _default_dingtalk_contacts_checker
            try:
                contacts_payload = checker(department_id=dingtalk_department_id)
            except Exception as exc:  # noqa: BLE001
                contacts_payload = {
                    'ok': False,
                    'department_access': False,
                    'message': f'{exc.__class__.__name__}: contacts check failed',
                }
            dingtalk_department_access = bool(contacts_payload.get('department_access'))
            dingtalk_contacts_missing_scope = contacts_payload.get('missing_scope')
            dingtalk_contact_count = contacts_payload.get('contact_count')
            if not contacts_payload.get('ok') and dingtalk_contacts_missing_scope:
                issues.append(
                    _issue(
                        level='warning',
                        code='DINGTALK_CONTACTS_PERMISSION_MISSING',
                        message=f'钉钉通讯录成员读取权限缺失：{dingtalk_contacts_missing_scope}。',
                        suggestion='在钉钉开放平台给当前应用开通通讯录成员读取权限后，再运行通讯录同步。',
                    )
                )
            elif not contacts_payload.get('ok'):
                issues.append(
                    _issue(
                        level='warning',
                        code='DINGTALK_CONTACTS_CHECK_FAILED',
                        message='钉钉通讯录只读诊断未通过。',
                        suggestion='运行 scripts/dingtalk_cli.py contacts --department-id 1 --json 查看脱敏诊断结果。',
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

    app_connection_live_checked = bool(check_app_connection_live)
    app_connection_live_ok: bool | None = None
    app_connection_live_result: dict[str, Any] = {}
    app_connection_live_error: str | None = None
    if app_connection_live_checked and app_connection_ready:
        app_connection_live_result, app_connection_live_error = _run_app_connection_live_probe(
            runtime,
            app_connection_live_probe=app_connection_live_probe,
        )
        app_connection_live_ok = (
            app_connection_live_error is None
            and app_connection_live_result.get('status') == 'sent'
            and (
                app_connection_live_result.get('http_status') is None
                or 200 <= int(app_connection_live_result.get('http_status') or 0) < 300
            )
        )
        if not app_connection_live_ok:
            detail = app_connection_live_error or app_connection_live_result.get('detail') or 'unknown'
            issues.append(
                _issue(
                    level='hard',
                    code='APP_CONNECTION_LIVE_FAILED',
                    message=f'应用连接 readiness POST 未送达：{detail}。',
                    suggestion='检查 APP_CONNECTION_API_BASE / APP_CONNECTION_API_KEY / 网络白名单，并确认下游返回 2xx 后重跑 --check-app-connection-live。',
                    required_env=['APP_CONNECTION_API_BASE', 'APP_CONNECTION_API_KEY'],
                )
            )

    live_aggregation_checked = bool(check_live_aggregation)
    live_aggregation_ok: bool | None = None
    live_aggregation_stats: dict[str, Any] = {}
    live_aggregation_error: str | None = None
    if live_aggregation_checked:
        live_aggregation_stats, live_aggregation_error = _run_live_aggregation_probe(
            session_factory,
            live_aggregation_probe=live_aggregation_probe,
        )
        live_aggregation_ok = live_aggregation_error is None
        if live_aggregation_error:
            issues.append(
                _issue(
                    level='hard',
                    code='LIVE_AGGREGATION_UNAVAILABLE',
                    message=f'实时聚合只读探针失败：{live_aggregation_error}。',
                    suggestion='请检查 /api/v1/aggregation/live、数据库迁移、主数据和实时聚合服务日志后重跑 readiness。',
                )
            )

    local_runnable = runtime_valid and database_ok
    hard_issues = [item for item in issues if item['level'] == 'hard']
    warning_issues = [item for item in issues if item['level'] == 'warning']
    missing_inputs = build_missing_inputs([*hard_issues, *warning_issues])
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
        'missing_inputs': missing_inputs,
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
            'dingtalk_department_access': dingtalk_department_access,
            'dingtalk_contacts_missing_scope': dingtalk_contacts_missing_scope,
            'dingtalk_contact_count': dingtalk_contact_count,
            'app_connection_enabled': runtime.APP_CONNECTION_ENABLED,
            'app_connection_push_mode': app_connection_mode,
            'app_connection_live_checked': app_connection_live_checked,
            'app_connection_live_ok': app_connection_live_ok,
            'app_connection_live_status': app_connection_live_result.get('status'),
            'app_connection_live_http_status': app_connection_live_result.get('http_status'),
            'app_connection_live_detail': app_connection_live_error or app_connection_live_result.get('detail'),
            'runtime_valid': runtime_valid,
            'database_ok': database_ok,
            'live_aggregation_checked': live_aggregation_checked,
            'live_aggregation_ok': live_aggregation_ok,
            'live_aggregation_error': live_aggregation_error,
            'live_aggregation_business_date': live_aggregation_stats.get('business_date'),
            'live_aggregation_date_source': live_aggregation_stats.get('business_date_source'),
            'live_aggregation_data_source': live_aggregation_stats.get('data_source'),
            'live_aggregation_total_entry_count': live_aggregation_stats.get('total_entry_count'),
            'live_aggregation_formal_entry_count': live_aggregation_stats.get('formal_entry_count'),
            'live_aggregation_draft_entry_count': live_aggregation_stats.get('draft_entry_count'),
            'live_aggregation_mes_row_count': live_aggregation_stats.get('mes_row_count'),
            'live_aggregation_mes_match_count': live_aggregation_stats.get('fill_entries_with_mes_match'),
            'live_aggregation_bound_to_machine_count': live_aggregation_stats.get('fill_entries_bound_to_machine'),
            'live_aggregation_pending_assignment_count': live_aggregation_stats.get('pending_assignment_entry_count'),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='统计模块可用性自检')
    parser.add_argument('--json', dest='json_mode', action='store_true', help='以 JSON 输出完整结果')
    parser.add_argument('--env-template', action='store_true', help='输出正式外部联通所需 .env 模板，不回显现有密钥')
    parser.add_argument('--missing-inputs', action='store_true', help='输出正式外部联通仍缺的现场输入清单，不回显密钥')
    parser.add_argument('--check-dingtalk-contacts', action='store_true', help='显式执行钉钉通讯录只读权限诊断')
    parser.add_argument('--dingtalk-department-id', type=int, default=1, help='钉钉通讯录诊断部门 ID')
    parser.add_argument('--check-live-aggregation', action='store_true', help='显式执行实时聚合只读探针，验证管理端实时数据服务可计算')
    parser.add_argument('--check-app-connection-live', action='store_true', help='显式向应用连接 API 发送 readiness POST，验证外发真的收到 2xx')
    args = parser.parse_args()

    if args.env_template:
        print(build_external_env_template(), end='')
        return 0

    result = inspect_statistics_module_ready(
        check_dingtalk_contacts=args.check_dingtalk_contacts,
        dingtalk_department_id=args.dingtalk_department_id,
        check_live_aggregation=args.check_live_aggregation,
        check_app_connection_live=args.check_app_connection_live,
    )
    if args.json_mode:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.missing_inputs:
        print(format_missing_inputs_markdown(result['missing_inputs']), end='')
        return 0
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
