"""
企业微信 API 适配器。
封装所有与企业微信服务器的交互，包括：
- access_token 获取与缓存
- OAuth2 授权码换取 userid
- 应用消息推送
- JS-SDK 签名
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta

import httpx

from app.adapters.wecom.group_bot import WeComGroupBotPublisher
from app.config import settings

logger = logging.getLogger("wecom")

_token_cache: dict[str, tuple[str, datetime]] = {}
_jsapi_ticket_cache: dict[str, tuple[str, datetime]] = {}

WECOM_API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"


async def get_access_token() -> str:
    """
    获取企业微信 access_token。
    有效期 7200 秒，提前 300 秒刷新。
    """

    cache_key = f"{settings.WECOM_CORP_ID}:{settings.WECOM_AGENT_ID}"
    if cache_key in _token_cache:
        token, expires_at = _token_cache[cache_key]
        if datetime.utcnow() < expires_at:
            return token

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{WECOM_API_BASE}/gettoken",
            params={
                "corpid": settings.WECOM_CORP_ID,
                "corpsecret": settings.WECOM_APP_SECRET,
            },
        )
        data = resp.json()
        if data.get("errcode", 0) != 0:
            raise RuntimeError(f"企业微信 access_token 获取失败: {data}")

        token = data["access_token"]
        expires_in = data.get("expires_in", 7200)
        _token_cache[cache_key] = (token, datetime.utcnow() + timedelta(seconds=expires_in - 300))
        return token


async def code_to_userid(code: str) -> str:
    """
    通过 OAuth2 授权码获取企业微信 userid。

    参数：
        code: 前端通过 wx.config 获取的授权码

    返回：
        企业微信的 userid 字符串
    """

    token = await get_access_token()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{WECOM_API_BASE}/auth/getuserinfo",
            params={"access_token": token, "code": code},
        )
        data = resp.json()
        if data.get("errcode", 0) != 0:
            raise RuntimeError(f"企业微信用户身份获取失败: {data}")
        userid = data.get("userid") or data.get("UserId")
        if not userid:
            raise RuntimeError(f"企业微信返回数据中无 userid: {data}")
        return userid


async def send_app_message(userid: str, content: str, *, msg_type: str = "text") -> dict:
    """
    通过企业微信应用消息推送文本消息给指定用户。

    参数：
        userid: 企业微信用户ID，多个用 | 分隔
        content: 消息内容
        msg_type: 消息类型，默认 text

    返回：
        企业微信 API 响应
    """

    token = await get_access_token()
    payload = {
        "touser": userid,
        "msgtype": msg_type,
        "agentid": int(settings.WECOM_AGENT_ID),
        "text": {"content": content},
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{WECOM_API_BASE}/message/send",
            params={"access_token": token},
            json=payload,
        )
        data = resp.json()
        if data.get("errcode", 0) != 0:
            logger.error("消息推送失败: %s", data)
        return data


async def get_jsapi_ticket() -> str:
    """获取 JS-SDK ticket，用于前端 wx.config 签名。"""

    cache_key = "jsapi_ticket"
    if cache_key in _jsapi_ticket_cache:
        ticket, expires_at = _jsapi_ticket_cache[cache_key]
        if datetime.utcnow() < expires_at:
            return ticket

    token = await get_access_token()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{WECOM_API_BASE}/get_jsapi_ticket",
            params={"access_token": token},
        )
        data = resp.json()
        if data.get("errcode", 0) != 0:
            raise RuntimeError(f"JS-SDK ticket 获取失败: {data}")

        ticket = data["ticket"]
        expires_in = data.get("expires_in", 7200)
        _jsapi_ticket_cache[cache_key] = (ticket, datetime.utcnow() + timedelta(seconds=expires_in - 300))
        return ticket


def generate_jsapi_signature(url: str, *, ticket: str, noncestr: str, timestamp: int) -> str:
    """
    生成 JS-SDK 签名。

    签名算法：sha1(jsapi_ticket=xxx&noncestr=xxx&timestamp=xxx&url=xxx)
    """

    sign_str = f"jsapi_ticket={ticket}&noncestr={noncestr}&timestamp={timestamp}&url={url}"
    return hashlib.sha1(sign_str.encode()).hexdigest()


__all__ = [
    "WeComGroupBotPublisher",
    "get_access_token",
    "code_to_userid",
    "send_app_message",
    "get_jsapi_ticket",
    "generate_jsapi_signature",
]
