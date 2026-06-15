"""
钉钉 H5 微应用免登入口。
使用钉钉新版服务端 API 获取用户身份。
"""

from __future__ import annotations

from typing import Any

import json
import logging
from datetime import datetime, timezone
from urllib import request as urllib_request

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import create_access_token
from app.core.redaction import redact_secret_text
from app.core.scope import build_scope_summary
from app.database import get_db
from app.models.agent_communication import AgentChannelBinding, AgentProfile, CommunicationChannel
from app.models.master import Workshop
from app.models.system import User
from app.schemas.auth import LoginResponse, UserInfo
from app.services.audit_service import log_action
from app.services import dingtalk_service
from app.services.agent_command_service import AgentCommandError, handle_agent_command

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
    return dingtalk_service.resolve_unique_dingtalk_user(
        db,
        dingtalk_user_id=user_id,
        dingtalk_union_id=union_id,
    )


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

    try:
        user = _find_system_user(db, union_id=union_id, user_id=open_id)
    except dingtalk_service.DingTalkUserAmbiguous as exc:
        raise HTTPException(status_code=409, detail="钉钉账号绑定异常，请联系管理员。") from exc
    if not user:
        raise HTTPException(
            status_code=403,
            detail=f"钉钉用户 {nick or union_id[:8]} 未绑定系统账号，请联系管理员。",
        )

    try:
        dingtalk_service.ensure_dingtalk_binding_available(
            db,
            user,
            dingtalk_user_id=open_id,
            dingtalk_union_id=union_id,
        )
    except dingtalk_service.DingTalkUserAmbiguous as exc:
        raise HTTPException(status_code=409, detail="钉钉账号绑定异常，请联系管理员。") from exc

    if not user.dingtalk_union_id:
        user.dingtalk_union_id = union_id
    user.last_login = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="钉钉账号绑定异常，请联系管理员。") from exc

    token = create_access_token(user.id)
    log_action(
        db,
        user_id=user.id,
        user_name=user.name,
        action="login",
        module="dingtalk",
        table_name="users",
        record_id=user.id,
        reason="钉钉H5免登",
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "display_name": user.name or user.username,
    }


@router.post("/h5-login", response_model=LoginResponse)
def dingtalk_h5_login(
    request: Request,
    req: DingtalkLoginRequest,
    db: Session = Depends(get_db),
) -> dict:
    if not dingtalk_service.service.is_h5_configured():
        raise HTTPException(status_code=400, detail='dingtalk_not_configured')

    try:
        identity = dingtalk_service.service.exchange_code(req.code)
    except dingtalk_service.DingTalkNotConfigured as exc:
        raise HTTPException(status_code=400, detail='dingtalk_not_configured') from exc
    except dingtalk_service.DingTalkCodeInvalid as exc:
        logger.warning('钉钉 H5 code 换 userid 失败: %s', exc)
        raise HTTPException(status_code=401, detail='dingtalk_code_invalid') from exc

    dingtalk_user_id = identity.get('userid') or ''
    try:
        user, token = dingtalk_service.service.issue_jwt_for_dingtalk_user(
            db,
            dingtalk_user_id=dingtalk_user_id,
            dingtalk_union_id=identity.get('unionid'),
        )
    except dingtalk_service.DingTalkUserNotBound as exc:
        raise HTTPException(
            status_code=404,
            detail={
                'code': 'dingtalk_user_not_bound',
                'dingtalk_user_id': exc.dingtalk_user_id,
                'dingtalk_union_id': exc.dingtalk_union_id,
            },
        ) from exc
    except dingtalk_service.DingTalkUserAmbiguous as exc:
        raise HTTPException(
            status_code=409,
            detail={
                'code': 'dingtalk_user_ambiguous',
                'dingtalk_user_id': exc.dingtalk_user_id,
                'dingtalk_union_id': exc.dingtalk_union_id,
            },
        ) from exc

    log_action(
        db,
        user_id=user.id,
        user_name=user.name,
        action='login',
        module='dingtalk',
        table_name='users',
        record_id=user.id,
        reason='钉钉H5免登',
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
    )
    user_info = UserInfo.model_validate(user)
    return {
        'access_token': token,
        'token_type': 'bearer',
        'user': user_info.model_dump(),
        'machine_info': None,
    }


def _clean_text(value: Any) -> str:
    return str(value or '').strip()


def _first_payload_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ''):
            return value
    return None


def _extract_agent_text(payload: dict[str, Any]) -> str:
    text_value = payload.get('text')
    if isinstance(text_value, dict):
        content = _clean_text(text_value.get('content'))
        if content:
            return content
    if isinstance(text_value, str):
        content = _clean_text(text_value)
        if content:
            return content

    content_value = payload.get('content')
    if isinstance(content_value, dict):
        content = _clean_text(content_value.get('content') or content_value.get('text'))
        if content:
            return content
    return _clean_text(content_value)


def _sanitize_inbound_payload(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if any(marker in lowered for marker in ('token', 'secret', 'webhook', 'authorization', 'sign')):
                continue
            cleaned[key_text] = _sanitize_inbound_payload(item)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_inbound_payload(item) for item in value]
    return value


def _parse_inbound_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    text = _clean_text(value).lower()
    return text in {'true', '1', 'yes', 'y', 'on'}


def _resolve_inbound_channel_scope(db: Session, *, group_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    workshop = _clean_text(_first_payload_value(payload, 'workshop', 'workshopName', 'workshop_name')) or None
    machine_code = _clean_text(
        _first_payload_value(payload, 'machineCode', 'machine_code', 'equipmentCode', 'equipment_code')
    ) or None
    if not group_id:
        return {'workshop': workshop, 'machine_code': machine_code, 'workshop_id': None}

    channel = (
        db.query(CommunicationChannel)
        .filter(
            CommunicationChannel.channel_type == 'dingtalk_group',
            CommunicationChannel.channel_key == group_id,
            CommunicationChannel.is_active.is_(True),
        )
        .first()
    )
    if channel is None:
        return {'workshop': workshop, 'machine_code': machine_code, 'workshop_id': None}

    if not workshop and channel.workshop_id:
        bound_workshop = db.get(Workshop, channel.workshop_id)
        workshop = bound_workshop.name if bound_workshop else None
    if not workshop and channel.target_type == 'workshop':
        workshop = _clean_text(channel.target_key) or None

    metadata = channel.metadata_payload or {}
    if not machine_code and isinstance(metadata, dict):
        machine_code = _clean_text(
            metadata.get('machine_code') or metadata.get('machineCode') or metadata.get('equipment_code')
        ) or None

    return {'workshop': workshop, 'machine_code': machine_code, 'workshop_id': channel.workshop_id}


def _ensure_inbound_channel_scope_access(user: User, channel_scope: dict[str, Any]) -> None:
    workshop_id = channel_scope.get('workshop_id')
    if workshop_id is None:
        return
    scope = build_scope_summary(user)
    if scope.is_admin or scope.data_scope_type == 'all':
        return
    if scope.workshop_id is not None and int(scope.workshop_id) == int(workshop_id):
        return
    raise HTTPException(status_code=403, detail='dingtalk_channel_scope_denied')


def _has_bound_inbound_outbox_channel(db: Session, *, group_id: str, agent_code: str) -> bool:
    clean_group_id = _clean_text(group_id)
    clean_agent_code = _clean_text(agent_code)
    if not clean_group_id or not clean_agent_code:
        return False
    return (
        db.query(AgentChannelBinding.id)
        .join(AgentProfile, AgentProfile.id == AgentChannelBinding.agent_profile_id)
        .join(CommunicationChannel, CommunicationChannel.id == AgentChannelBinding.channel_id)
        .filter(
            AgentProfile.code == clean_agent_code,
            AgentProfile.is_active.is_(True),
            CommunicationChannel.channel_type == 'dingtalk_group',
            CommunicationChannel.channel_key == clean_group_id,
            CommunicationChannel.is_active.is_(True),
            AgentChannelBinding.is_active.is_(True),
        )
        .first()
        is not None
    )


def _ensure_inbound_token(header_token: str | None) -> None:
    expected = _clean_text(getattr(settings, 'DINGTALK_INBOUND_TOKEN', None))
    if not expected:
        if settings.is_production_like:
            raise HTTPException(status_code=503, detail='dingtalk_inbound_token_required')
        return
    if _clean_text(header_token) != expected:
        raise HTTPException(status_code=401, detail='dingtalk_inbound_token_invalid')


def _resolve_inbound_user(db: Session, payload: dict[str, Any]) -> User:
    sender_user_id = _clean_text(
        _first_payload_value(payload, 'senderStaffId', 'senderId', 'senderUserId', 'userid', 'userId')
    )
    sender_union_id = _clean_text(_first_payload_value(payload, 'senderUnionId', 'unionId'))
    if not sender_user_id and not sender_union_id:
        raise HTTPException(status_code=401, detail='dingtalk_sender_required')

    try:
        user = dingtalk_service.resolve_unique_dingtalk_user(
            db,
            dingtalk_user_id=sender_user_id,
            dingtalk_union_id=sender_union_id,
        )
    except dingtalk_service.DingTalkUserAmbiguous as exc:
        raise HTTPException(status_code=409, detail='dingtalk_user_ambiguous') from exc
    if not user:
        raise HTTPException(status_code=403, detail='dingtalk_user_not_bound')

    scope = build_scope_summary(user)
    if not (scope.is_admin or scope.is_manager or scope.is_reviewer):
        raise HTTPException(status_code=403, detail='dingtalk_agent_access_denied')
    return user


@router.post('/agent-inbound')
def dingtalk_agent_inbound(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    inbound_token: str | None = Header(default=None, alias='x-dingtalk-inbound-token'),
) -> dict[str, Any]:
    _ensure_inbound_token(inbound_token)
    text = _extract_agent_text(payload)
    if not text:
        raise HTTPException(status_code=400, detail='command_text_required')

    user = _resolve_inbound_user(db, payload)
    group_id = _clean_text(_first_payload_value(payload, 'conversationId', 'conversation_id', 'chatId', 'openConversationId'))
    sender_external_id = _clean_text(
        _first_payload_value(payload, 'senderStaffId', 'senderId', 'senderUserId', 'userid', 'userId')
    )
    trace_id = _clean_text(_first_payload_value(payload, 'traceId', 'trace_id', 'msgId', 'messageId'))
    agent_code = _clean_text(_first_payload_value(payload, 'agentCode', 'agent_code')) or 'factory_dispatch'
    queue_outbox_value = _first_payload_value(payload, 'queueOutbox', 'queue_outbox')
    queue_outbox = (
        _has_bound_inbound_outbox_channel(db, group_id=group_id, agent_code=agent_code)
        if queue_outbox_value is None
        else _parse_inbound_bool(queue_outbox_value)
    )
    channel_scope = _resolve_inbound_channel_scope(db, group_id=group_id, payload=payload)
    _ensure_inbound_channel_scope_access(user, channel_scope)

    try:
        result = handle_agent_command(
            db,
            channel='dingtalk_group',
            group_id=group_id or None,
            sender_external_id=sender_external_id or None,
            text=text,
            agent_code=agent_code,
            trace_id=trace_id or None,
            workshop=channel_scope['workshop'],
            machine_code=channel_scope['machine_code'],
            queue_outbox=queue_outbox,
            source_payload=_sanitize_inbound_payload(payload),
            current_user=user,
        )
        db.commit()
    except AgentCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=redact_secret_text(str(exc))) from exc
    except Exception:
        db.rollback()
        raise

    return {
        'errcode': 0,
        'errmsg': 'ok',
        'trace_id': result.trace_id,
        'status_color': result.status_color,
        'intent': result.intent,
        'answer': result.answer,
        'chat_inbox_id': result.chat_inbox_id,
        'agent_run_id': result.agent_run_id,
        'outbox_message_id': result.outbox_message_id,
    }
