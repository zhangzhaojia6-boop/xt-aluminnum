from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.models.system import User

router = APIRouter(tags=['notifications'])

notifications_db: list[dict] = [
    {
        'id': 'welcome',
        'title': '系统已就绪',
        'content': '新的管理工作台已上线。',
        'read': False,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
]


@router.get('')
def list_notifications(current_user: User = Depends(get_current_user)) -> list[dict]:
    _ = current_user
    return notifications_db


@router.get('/unread-count')
def unread_count(current_user: User = Depends(get_current_user)) -> dict[str, int]:
    _ = current_user
    return {'count': sum(1 for notification in notifications_db if not notification.get('read'))}


@router.post('/{notification_id}/read')
def mark_read(notification_id: str, current_user: User = Depends(get_current_user)) -> dict[str, bool]:
    _ = current_user
    for notification in notifications_db:
        if notification['id'] == notification_id:
            notification['read'] = True
            return {'ok': True}
    return {'ok': False}
