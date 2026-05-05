from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.models.system import User

router = APIRouter(tags=['notifications'])

DEFAULT_NOTIFICATIONS: tuple[dict, ...] = (
    {
        'id': 'welcome',
        'title': '系统已就绪',
        'content': '新的管理工作台已上线。',
        'created_at': datetime.now(timezone.utc).isoformat(),
    },
)

notification_read_state: dict[str, set[str]] = {}


def _user_key(current_user: User) -> str:
    return str(current_user.id)


def _build_notifications(current_user: User) -> list[dict]:
    read_ids = notification_read_state.get(_user_key(current_user), set())
    return [
        {
            **notification,
            'read': notification['id'] in read_ids,
        }
        for notification in DEFAULT_NOTIFICATIONS
    ]


def _notification_exists(notification_id: str) -> bool:
    return any(notification['id'] == notification_id for notification in DEFAULT_NOTIFICATIONS)


@router.get('')
def list_notifications(current_user: User = Depends(get_current_user)) -> list[dict]:
    return _build_notifications(current_user)


@router.get('/unread-count')
def unread_count(current_user: User = Depends(get_current_user)) -> dict[str, int]:
    return {'count': sum(1 for notification in _build_notifications(current_user) if not notification['read'])}


@router.post('/{notification_id}/read')
def mark_read(notification_id: str, current_user: User = Depends(get_current_user)) -> dict[str, bool]:
    if not _notification_exists(notification_id):
        raise HTTPException(status_code=404, detail='通知不存在')
    notification_read_state.setdefault(_user_key(current_user), set()).add(notification_id)
    return {'ok': True}
