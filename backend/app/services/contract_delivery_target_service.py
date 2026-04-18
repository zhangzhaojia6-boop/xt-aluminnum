from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, settings as runtime_settings
from app.models.master import Workshop
from app.models.system import User


FACTORY_OBSERVER_ROLES = {'factory-observer', 'factory_director', 'senior_manager', 'manager', 'admin'}
WORKSHOP_OBSERVER_ROLES = {'workshop-observer', 'workshop_director', 'reviewer', 'manager', 'admin'}
ROLLOUT_ADMIN_ROLES = {'rollout-admin', 'ops-implementer', 'admin'}


def _build_target(*, logical_type: str, channel_type: str, channel_key: str, webhook_configured: bool, user_ids: list[int] | None = None) -> dict[str, Any]:
    return {
        'logical_type': logical_type,
        'channel_type': channel_type,
        'channel_key': channel_key,
        'webhook_configured': bool(webhook_configured),
        'user_ids': list(user_ids or []),
    }


def _find_workshop(db: Session, workshop_token: str) -> Workshop | None:
    token = str(workshop_token or '').strip()
    if not token:
        return None
    if token.isdigit():
        return db.get(Workshop, int(token))
    return db.query(Workshop).filter(Workshop.code == token).first()


def resolve_contract_delivery_targets(
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
        workshop = _find_workshop(db, normalized_scope.split(':', 1)[1])
        workshop_id = getattr(workshop, 'id', None)
        configured = runtime.wecom_bot_workshop_webhook_map.get(str(workshop_id)) if workshop_id is not None else None
        observer_users = []
        if workshop_id is not None:
            observer_users = (
                db.query(User)
                .filter(User.is_active.is_(True), User.workshop_id == workshop_id, User.role.in_(tuple(WORKSHOP_OBSERVER_ROLES)))
                .all()
            )
        if workshop_id is None:
            return {
                'delivery_scope': normalized_scope,
                'resolution_status': 'blocked',
                'resolved_targets': [],
                'publisher_delivery_target': 'management',
                'publisher_target_key': 'management',
            }
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
