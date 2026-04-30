"""
钉钉 H5 微应用免登入口。
使用钉钉新版服务端 API 获取用户身份。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from urllib import request as urllib_request

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import create_access_token
from app.database import get_db
from app.models.system import User
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dingtalk"])


class DingtalkLoginRequest(BaseModel):
    code: str


def _dingtalk_post(url: str, payload: dict, headers: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib_request.Request(url, data=body, headers=hdrs, method="POST")
    with urllib_request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode(resp.headers.get_content_charset("utf-8")))


def _get_user_access_token(auth_code: str) -> str:
    resp = _dingtalk_post(
        "https://api.dingtalk.com/v1.0/oauth2/userAccessToken",
        {
            "clientId": settings.DINGTALK_APP_KEY,
            "clientSecret": settings.DINGTALK_APP_SECRET,
            "code": auth_code,
            "grantType": "authorization_code",
        },
    )
    token = resp.get("accessToken")
    if not token:
        raise RuntimeError(resp.get("message") or "获取钉钉用户令牌失败")
    return token


def _get_user_info(user_access_token: str) -> dict:
    url = "https://api.dingtalk.com/v1.0/contact/users/me"
    hdrs = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-acs-dingtalk-access-token": user_access_token,
    }
    req = urllib_request.Request(url, headers=hdrs, method="GET")
    with urllib_request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode(resp.headers.get_content_charset("utf-8")))


def _find_system_user(db: Session, union_id: str, user_id: str | None) -> User | None:
    if user_id:
        user = db.query(User).filter(User.dingtalk_user_id == user_id, User.is_active.is_(True)).first()
        if user:
            return user
    if union_id:
        user = db.query(User).filter(User.dingtalk_union_id == union_id, User.is_active.is_(True)).first()
        if user:
            return user
    return None


@router.post("/login")
async def dingtalk_login(req: DingtalkLoginRequest, db: Session = Depends(get_db)):
    if not settings.DINGTALK_APP_KEY or not settings.DINGTALK_APP_SECRET:
        raise HTTPException(status_code=503, detail="钉钉应用未配置")

    try:
        user_token = _get_user_access_token(req.code)
    except Exception as exc:
        logger.warning("钉钉 userAccessToken 获取失败: %s", exc)
        raise HTTPException(status_code=401, detail=f"钉钉授权失败: {exc}") from exc

    try:
        info = _get_user_info(user_token)
    except Exception as exc:
        logger.warning("钉钉用户信息获取失败: %s", exc)
        raise HTTPException(status_code=401, detail=f"获取钉钉用户信息失败: {exc}") from exc

    union_id = info.get("unionId") or ""
    open_id = info.get("openId") or ""
    nick = info.get("nick") or ""

    if not union_id:
        raise HTTPException(status_code=401, detail="钉钉未返回用户标识")

    user = _find_system_user(db, union_id=union_id, user_id=open_id)
    if not user:
        raise HTTPException(
            status_code=403,
            detail=f"钉钉用户 {nick or union_id[:8]} 未绑定系统账号，请联系管理员。",
        )

    if not user.dingtalk_union_id:
        user.dingtalk_union_id = union_id
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(user.id)
    log_action(db, user=user, action="login", module="dingtalk", reason="钉钉H5免登")

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "display_name": user.name or user.username,
    }
