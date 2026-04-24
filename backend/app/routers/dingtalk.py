"""
钉钉登录入口。
当前阶段复用既有移动免登映射逻辑，统一到钉钉优先命名。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.wecom import WecomLoginRequest, WecomLoginResponse, _channel_login

router = APIRouter(tags=["dingtalk"])


@router.post("/login", response_model=WecomLoginResponse)
async def dingtalk_login(req: WecomLoginRequest, db: Session = Depends(get_db)):
    """
    钉钉 OAuth 兼容登录入口。
    """

    return await _channel_login(req, db, entry_label="钉钉")
