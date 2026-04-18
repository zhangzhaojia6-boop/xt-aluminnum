from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, settings as runtime_settings
from app.models.master import Workshop
from app.models.system import User
from app.services.contract_delivery_target_service import (
    FACTORY_OBSERVER_ROLES,
    ROLLOUT_ADMIN_ROLES,
    WORKSHOP_OBSERVER_ROLES,
    _build_target,
)


WORKSHOP_SCOPE_HINTS: dict[str, tuple[str, ...]] = {
    'cold_roll_1450': ('LZ1450', '1450'),
    'cold_roll_1650_2050': ('LZ2050', '2050', '1650'),
    'cold_roll_1850': ('1850',),
    'stretch': ('拉矫',),
    'finishing': ('精整',),
    'park_cutting': ('JQ', 'CPK', '飞剪', '剪切'),
}


def _find_workshops_by_scope_token(db: Session, workshop_token: str) -> list[Workshop]:
    token = str(workshop_token or '').strip()
    if not token:
        return []
    if token.isdigit():
        workshop = db.get(Workshop, int(token))
        return [workshop] if workshop else []

    direct = db.query(Workshop).filter(Workshop.code == token).all()
    if direct:
        return direct

    hints = WORKSHOP_SCOPE_HINTS.get(token, (token,))
    matches: list[Workshop] = []
    for workshop in db.query(Workshop).filter(Workshop.is_active.is_(True)).all():
        text = f'{getattr(workshop, "code", "")} {getattr(workshop, "name", "")}'
        if any(hint and hint in text for hint in hints):
            matches.append(workshop)
    return matches


def resolve_yield_matrix_delivery_targets(
    db: Session,
    *,
    delivery_scope: str | None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    runtime = settings or runtime_settings
    normalized_scope = str(delivery_scope or 'factory').strip() or 'factory'

    if normalized_scope == 'factory':
        admin_users = db.query(User).filter(User.is_active.is_(True), User.role.in_(tuple(FACTORY_OBSERVER_ROLES))).all()
        resolved_targets = [
            _build_target(
                logical_type='factory-observer',
                channel_type='management',
                channel_key='management',
                webhook_configured=bool(runtime.WECOM_BOT_MANAGEMENT_WEBHOOK_URL or runtime.WECOM_BOT_WEBHOOK_URL),
                user_ids=[item.id for item in admin_users],
            )
        ]
        resolution_status = 'resolved' if resolved_targets[0]['webhook_configured'] else 'blocked'
        return {
            'delivery_scope': normalized_scope,
            'resolution_status': resolution_status,
            'resolved_targets': resolved_targets,
            'publisher_delivery_target': 'management',
            'publisher_target_key': 'management',
        }

    if normalized_scope.startswith('workshop:'):
        workshop_token = normalized_scope.split(':', 1)[1]
        workshops = _find_workshops_by_scope_token(db, workshop_token)
        if len(workshops) != 1:
            return {
                'delivery_scope': normalized_scope,
                'resolution_status': 'conflict' if len(workshops) > 1 else 'blocked',
                'resolved_targets': [],
                'publisher_delivery_target': 'management',
                'publisher_target_key': 'management',
            }

        workshop = workshops[0]
        workshop_id = workshop.id
        configured = runtime.wecom_bot_workshop_webhook_map.get(str(workshop_id))
        observer_users = (
            db.query(User)
            .filter(User.is_active.is_(True), User.workshop_id == workshop_id, User.role.in_(tuple(WORKSHOP_OBSERVER_ROLES)))
            .all()
        )
        resolved_targets = [
            _build_target(
                logical_type='workshop-observer',
                channel_type='workshop',
                channel_key=str(workshop_id),
                webhook_configured=bool(configured or runtime.WECOM_BOT_WEBHOOK_URL),
                user_ids=[item.id for item in observer_users],
            )
        ]
        resolution_status = 'resolved' if resolved_targets[0]['webhook_configured'] else 'blocked'
        if len(observer_users) > 1 and not configured:
            resolution_status = 'conflict'
        publisher_delivery_target = 'workshop' if resolution_status == 'resolved' else 'management'
        publisher_target_key = str(workshop_id) if publisher_delivery_target == 'workshop' else 'management'
        if resolution_status in {'blocked', 'conflict'}:
            resolved_targets.append(
                _build_target(
                    logical_type='rollout-admin',
                    channel_type='management',
                    channel_key='management',
                    webhook_configured=bool(runtime.WECOM_BOT_MANAGEMENT_WEBHOOK_URL or runtime.WECOM_BOT_WEBHOOK_URL),
                    user_ids=[
                        item.id
                        for item in db.query(User)
                        .filter(User.is_active.is_(True), User.role.in_(tuple(ROLLOUT_ADMIN_ROLES)))
                        .all()
                    ],
                )
            )
        return {
            'delivery_scope': normalized_scope,
            'resolution_status': resolution_status,
            'resolved_targets': resolved_targets,
            'publisher_delivery_target': publisher_delivery_target,
            'publisher_target_key': publisher_target_key,
        }

    return {
        'delivery_scope': normalized_scope,
        'resolution_status': 'blocked',
        'resolved_targets': [],
        'publisher_delivery_target': 'management',
        'publisher_target_key': 'management',
    }
