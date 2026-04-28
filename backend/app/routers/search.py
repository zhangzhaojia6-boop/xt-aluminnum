from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user
from app.models.system import User

router = APIRouter(tags=['search'])


@router.get('/search')
def global_search(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
) -> dict[str, list[dict]]:
    _ = current_user
    query = q.strip().lower()
    navigation = [
        {'title': '总览', 'path': '/manage/overview', 'group': 'manage'},
        {'title': '填报中心', 'path': '/entry', 'group': 'entry'},
        {'title': 'AI 工作台', 'path': '/manage/ai', 'group': 'manage'},
    ]
    return {
        'navigation': [item for item in navigation if query in item['title'].lower() or query in item['path'].lower()],
        'production': [],
        'master': [],
    }
