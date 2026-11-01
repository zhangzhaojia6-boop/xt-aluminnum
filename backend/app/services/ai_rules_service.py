from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.scope import ScopeSummary
from app.services import factory_command_service


_SYNC_DEGRADED_STATUSES = {'stale', 'failed', 'unconfigured', 'migration_missing', 'offline_or_blocked'}
_SYNC_CRITICAL_STATUSES = {'failed', 'migration_missing', 'offline_or_blocked'}
_ROUTE_STEP_PROCESS = re.compile(r'\(([^()]*)\)')


def _route_processes(route_text: Any) -> list[str]:
    # 路线形如「2050车间(冷轧)-新厂在线车间(北线退火)-精整(包装)」，每段第一个括号里是工序
    processes = []
    for step in str(route_text or '').split('-'):
        names = _ROUTE_STEP_PROCESS.findall(step)
        if names:
            processes.append(names[0].strip())
    return processes


def _route_continues_without_next_step(coil: dict[str, Any]) -> bool:
    # 还没开工、已到路线最后一道（如包装）、不在制，都不算缺下道工序
    if (coil.get('destination') or {}).get('kind') != 'in_progress':
        return False
    current = coil.get('current_process')
    if not current or coil.get('next_process'):
        return False
    return current in _route_processes(coil.get('process_route_text'))[:-1]


def evaluate_rules(db: Session, *, scope: ScopeSummary | None = None) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    freshness = factory_command_service.build_freshness(db)
    freshness_status = str(freshness.get('status') or '')
    if freshness_status in _SYNC_DEGRADED_STATUSES:
        rules.append(
            {
                'key': 'sync_stale',
                'severity': 'critical' if freshness_status in _SYNC_CRITICAL_STATUSES else 'warning',
                'evidence_refs': [{'kind': 'sync', 'key': 'mes_projection'}],
                'recommended_next_actions': ['检查外部 MES 同步任务'],
            }
        )

    for coil in factory_command_service.list_coils(db, scope=scope):
        if _route_continues_without_next_step(coil):
            rules.append(
                {
                    'key': 'route_missing',
                    'severity': 'warning',
                    'evidence_refs': [{'kind': 'coil', 'key': coil.get('coil_key', '')}],
                    'recommended_next_actions': ['补齐当前/下道工序'],
                }
            )
        if (coil.get('destination') or {}).get('kind') == 'unknown':
            rules.append(
                {
                    'key': 'destination_unknown',
                    'severity': 'warning',
                    'evidence_refs': [{'kind': 'coil', 'key': coil.get('coil_key', '')}],
                    'recommended_next_actions': ['核对库存去向'],
                }
            )

    overview = factory_command_service.build_overview(db, scope=scope)
    if 'cost_inputs' in (overview.get('missing_data') or []):
        rules.append(
            {
                'key': 'cost_estimate_missing',
                'severity': 'info',
                'evidence_refs': [{'kind': 'cost', 'key': 'management_estimate'}],
                'recommended_next_actions': ['补齐经营估算口径'],
            }
        )

    return rules
