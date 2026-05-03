from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.scope import ScopeSummary
from app.services import factory_command_service


def evaluate_rules(db: Session, *, scope: ScopeSummary | None = None) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    freshness = factory_command_service.build_freshness(db)
    if freshness.get('status') in {'stale', 'offline_or_blocked'}:
        rules.append(
            {
                'key': 'sync_stale',
                'severity': 'critical' if freshness.get('status') == 'offline_or_blocked' else 'warning',
                'evidence_refs': [{'kind': 'sync', 'key': 'mes_projection'}],
                'recommended_next_actions': ['检查外部 MES 同步任务'],
            }
        )

    for coil in factory_command_service.list_coils(db, scope=scope):
        if not coil.get('current_process') or not coil.get('next_process'):
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
