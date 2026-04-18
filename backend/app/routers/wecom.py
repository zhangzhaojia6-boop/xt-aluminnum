"""
企业微信回调与认证路由。
处理 OAuth2 登录、JS-SDK 签名、消息回调。
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


@router.post("/login", response_model=WecomLoginResponse)
async def wecom_login(req: WecomLoginRequest, db: Session = Depends(get_db)):
    """
    企业微信 OAuth2 登录。

    流程：
    1. 用 code 换取 userid
    2. 通过 userid 在 users 表中查找对应用户（匹配 username 或 dingtalk_user_id 字段）
    3. 找到则签发 JWT token
    4. 找不到则返回 403

    注意：
    - 如果 WECOM_APP_ENABLED 为 false，返回 503
    """

    if not settings.WECOM_APP_ENABLED:
        raise HTTPException(status_code=503, detail="企业微信应用未启用")

    from app.adapters.wecom import code_to_userid

    try:
        wecom_userid = await code_to_userid(req.code)
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    mapping = resolve_wecom_user(db, wecom_userid=wecom_userid)
    if mapping.status == "invalid":
        raise HTTPException(status_code=403, detail="企业微信账号无效，请重新进入企业微信后再试。")
    if mapping.status == "not_found":
        raise HTTPException(
            status_code=403,
            detail=f"当前企业微信账号未绑定系统用户（{wecom_userid}），请联系管理员开通。",
        )
    if mapping.status == "inactive":
        raise HTTPException(
            status_code=403,
            detail=f"账号已停用（{wecom_userid}），请联系管理员启用后再试。",
        )
    if mapping.status == "ambiguous":
        conflict_names = [item.username for item in mapping.conflicts]
        raise HTTPException(
            status_code=403,
            detail=f"企业微信账号映射不唯一（{wecom_userid}），请联系管理员清理重复账号：{', '.join(conflict_names)}。",
        )
    user = mapping.user
    if user is None:
        raise HTTPException(status_code=403, detail="企业微信账号映射失败，请联系管理员检查配置。")

    token = create_access_token(user.id)
    return WecomLoginResponse(
        token=token,
        user_id=user.id,
        display_name=user.name or user.username,
    )


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
