"""
企业微信兼容路由。
当前主入口已转向钉钉优先，这里保留旧入口兼容。
"""

from __future__ import annotations

import secrets
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import create_access_token
from app.database import get_db
from app.services.wecom_mapping_service import resolve_wecom_user

router = APIRouter(tags=["wecom"])


class WecomLoginRequest(BaseModel):
    """企业微信登录请求。"""

    code: str


class WecomLoginResponse(BaseModel):
    """企业微信登录响应。"""

    token: str
    user_id: int
    display_name: str


class JsapiSignatureRequest(BaseModel):
    """JS-SDK 签名请求。"""

    url: str


class JsapiSignatureResponse(BaseModel):
    """JS-SDK 签名响应。"""

    app_id: str
    timestamp: int
    nonce_str: str
    signature: str


async def _channel_login(
    req: WecomLoginRequest,
    db: Session,
    *,
    entry_label: str,
) -> WecomLoginResponse:
    if not settings.WECOM_APP_ENABLED:
        raise HTTPException(status_code=503, detail=f"{entry_label}入口未启用")

    from app.adapters.wecom import code_to_userid

    try:
        channel_userid = await code_to_userid(req.code)
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    mapping = resolve_wecom_user(db, wecom_userid=channel_userid)
    if mapping.status == "invalid":
        raise HTTPException(status_code=403, detail=f"{entry_label}账号无效，请重新进入后再试。")
    if mapping.status == "not_found":
        raise HTTPException(
            status_code=403,
            detail=f"当前{entry_label}账号未绑定系统用户（{channel_userid}），请联系管理员开通。",
        )
    if mapping.status == "inactive":
        raise HTTPException(
            status_code=403,
            detail=f"账号已停用（{channel_userid}），请联系管理员启用后再试。",
        )
    if mapping.status == "ambiguous":
        conflict_names = [item.username for item in mapping.conflicts]
        raise HTTPException(
            status_code=403,
            detail=f"{entry_label}账号映射不唯一（{channel_userid}），请联系管理员清理重复账号：{', '.join(conflict_names)}。",
        )
    user = mapping.user
    if user is None:
        raise HTTPException(status_code=403, detail=f"{entry_label}账号映射失败，请联系管理员检查配置。")

    token = create_access_token(user.id)
    return WecomLoginResponse(
        token=token,
        user_id=user.id,
        display_name=user.name or user.username,
    )


@router.post("/login", response_model=WecomLoginResponse)
async def wecom_login(req: WecomLoginRequest, db: Session = Depends(get_db)):
    """
    企业微信 OAuth2 登录兼容入口。
    """

    return await _channel_login(req, db, entry_label="企业微信")


@router.post("/jsapi-signature", response_model=JsapiSignatureResponse)
async def get_jsapi_signature(req: JsapiSignatureRequest):
    """
    获取 JS-SDK 签名，用于前端 wx.config。

    注意：如果 WECOM_APP_ENABLED 为 false，返回 503
    """

    if not settings.WECOM_APP_ENABLED:
        raise HTTPException(status_code=503, detail="企业微信应用未启用")

    from app.adapters.wecom import generate_jsapi_signature, get_jsapi_ticket

    ticket = await get_jsapi_ticket()
    timestamp = int(time.time())
    nonce_str = secrets.token_hex(8)
    signature = generate_jsapi_signature(
        req.url,
        ticket=ticket,
        noncestr=nonce_str,
        timestamp=timestamp,
    )

    return JsapiSignatureResponse(
        app_id=settings.WECOM_CORP_ID or "",
        timestamp=timestamp,
        nonce_str=nonce_str,
        signature=signature,
    )
