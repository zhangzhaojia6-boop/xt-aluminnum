"""
钉钉 H5 微应用免登入口。
使用钉钉新版服务端 API 获取用户身份。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any

import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib import request as urllib_request
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.adapters import get_mes_adapter
from app.config import settings
from app.core.auth import create_access_token
from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.core.scope import build_scope_summary
from app.database import get_db
from app.models.agent_communication import (
    AgentChannelBinding,
    AgentProfile,
    AgentRateLimit,
    ChatInboxMessage,
    CommunicationChannel,
    DingTalkInboundReceipt,
    MultimodalEvidence,
)
from app.models.master import Workshop
from app.models.system import User
from app.schemas.auth import LoginResponse, UserInfo
from app.services.audit_service import log_action
from app.services import dingtalk_service
from app.services.agent_command_service import AgentCommandError, handle_agent_command
from app.services.dingtalk_energy_ingest_service import (
    EXCEL_SUFFIXES,
    INLINE_FILE_KEYS,
    ingest_dingtalk_energy_file,
    resolve_dingtalk_energy_business_date,
)
from app.services.dingtalk_file_text_extractor import extract_dingtalk_file_text
from app.services.dingtalk_secret_sanitizer import sanitize_dingtalk_payload_for_storage
from app.services.dingtalk_stream_event_service import normalize_dingtalk_stream_event
from app.services.dingtalk_stream_gateway_service import (
    ingest_dingtalk_stream_event,
    parse_dingtalk_event_datetime,
)
from app.services.hermes_day1_evidence_service import Day1EvidenceError, record_day1_dingtalk_evidence
from app.services.hermes_day1_intent_service import (
    Day1CommandParseError,
    classify_day1_actor,
    parse_day1_command,
    require_root_owner_for_day1_report,
)
from app.services.hermes_day1_orchestrator import run_day1_super_brain
from app.services.hermes_factory_brain_intent_service import classify_factory_brain_intent
from app.services.hermes_factory_brain_types import FactoryBrainIntent
from app.services.hermes_mes_read_service import HermesMesReadService
from app.services.hermes_root_owner_production_orchestrator import (
    run_root_owner_production_turn,
)
from app.services.hermes_root_owner_message_service import understand_root_owner_message

logger = logging.getLogger(__name__)
INBOUND_AGENT_PROCESSING_LEASE_SECONDS = 120

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


def _is_legacy_slash_daily_report_command(text: str) -> bool:
    clean_text = _clean_text(text)
    if not clean_text.startswith('/'):
        return False
    command = clean_text.split(maxsplit=1)[0].lstrip('/')
    return command in {'日报', '发日报'}


def _should_route_root_owner_private_production_turn(text: str) -> bool:
    clean_text = _clean_text(text)
    if not clean_text or clean_text.startswith('/'):
        return False
    plan = understand_root_owner_message(clean_text)
    if plan.domain != 'general':
        return True
    if not plan.needs_clarification:
        return False
    return not _is_clear_root_owner_private_general_chat(clean_text, plan.recognition_reason)


def _is_clear_root_owner_private_general_chat(clean_text: str, recognition_reason: str) -> bool:
    reason_tokens = {part.strip() for part in str(recognition_reason or '').split(',') if part.strip()}
    if reason_tokens & {'ambiguous_time_expression', 'explicit_today', 'explicit_yesterday', 'explicit_day_before_yesterday'}:
        return False
    intent = classify_factory_brain_intent(clean_text, today=datetime.now().date())
    return intent.intent_type == 'general_chat' and intent.task_type == 'general_chat'


def _get_factory_brain_route_intent(text: str) -> FactoryBrainIntent | None:
    clean_text = _clean_text(text)
    if not clean_text or clean_text.startswith('/'):
        return None
    intent = classify_factory_brain_intent(clean_text, today=datetime.now().date())
    if not intent.should_use_factory_brain:
        return None
    if _should_keep_simple_fact_query_on_factory_dispatch(clean_text, intent):
        return None
    return intent


def _should_keep_simple_fact_query_on_factory_dispatch(text: str, intent: FactoryBrainIntent) -> bool:
    if intent.task_type not in {'inventory_query', 'monthly_operation'}:
        return False
    return any(
        token in text
        for token in (
            '今日入库',
            '今天入库',
            '入库多少',
            '月累计入库',
            '入库和月累计',
            '包装入库',
        )
    )


def _require_root_owner_for_factory_brain_intent(
    *,
    intent: FactoryBrainIntent,
    user: User,
    sender_external_id: str,
    sender_union_id: str,
    channel: str,
    group_id: str,
) -> None:
    if not intent.requires_root_owner:
        return
    decision = classify_day1_actor(
        user,
        sender_user_id=sender_external_id,
        sender_union_id=sender_union_id,
        channel=channel,
        group_id=group_id,
    )
    require_root_owner_for_day1_report(decision)


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
    parsed_text_value = _coerce_payload_mapping(text_value)
    if parsed_text_value is not None:
        content = _clean_text(parsed_text_value.get('content') or parsed_text_value.get('text'))
        if content:
            return content
        return ''
    if isinstance(text_value, str):
        content = _clean_text(text_value)
        if content:
            return content

    content_value = payload.get('content')
    if isinstance(content_value, dict):
        content = _clean_text(content_value.get('content') or content_value.get('text'))
        if content:
            return content
    parsed_content_value = _coerce_payload_mapping(content_value)
    if parsed_content_value is not None:
        content = _clean_text(parsed_content_value.get('content') or parsed_content_value.get('text'))
        if content:
            return content
        return ''
    return _clean_text(content_value)


def _coerce_payload_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not (text.startswith('{') and text.endswith('}')):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _has_inbound_evidence_payload(payload: dict[str, Any]) -> bool:
    file_ref = _clean_text(
        _first_payload_value(payload, 'fileName', 'file_name', 'mediaId', 'media_id', 'fileId', 'file_id')
    )
    if file_ref:
        return True
    msg_type = _clean_text(_first_payload_value(payload, 'msgtype', 'msgType', 'messageType')).lower()
    return msg_type in {'file', 'image', 'voice', 'attachment'}


def _sanitize_inbound_payload(value: Any) -> Any:
    return sanitize_dingtalk_payload_for_storage(value)


def _resolve_inbound_trace_id(payload: dict[str, Any]) -> str:
    trace_id = _clean_text(_first_payload_value(payload, 'traceId', 'trace_id', 'msgId', 'messageId'))
    if trace_id:
        return trace_id
    if _has_inbound_evidence_payload(payload):
        return normalize_dingtalk_stream_event(payload).trace_id
    return uuid4().hex


def _prepare_attachment_processing_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    normalized = normalize_dingtalk_stream_event(payload)
    processing_payload = dict(payload)
    non_secret_updates: dict[str, Any] = {'downloadCode_present': bool(normalized.download_code)}

    if not _is_attachment_candidate_payload(normalized.file_name, normalized.file_id, normalized.download_code):
        return '', non_secret_updates, processing_payload
    if _has_inline_file_content(payload):
        return '', non_secret_updates, processing_payload
    if not normalized.download_code:
        non_secret_updates.update({'parse_status': 'download_failed', 'download_status': 'missing_download_code'})
        return '', non_secret_updates, processing_payload

    try:
        downloaded = dingtalk_service.service.download_robot_message_file(download_code=normalized.download_code)
    except Exception:  # noqa: BLE001
        non_secret_updates.update({'parse_status': 'download_failed', 'download_status': 'download_failed'})
        return '', non_secret_updates, processing_payload

    file_name = normalized.file_name or _clean_text(_first_payload_value(payload, 'fileName', 'file_name', 'name'))
    file_text = extract_dingtalk_file_text(
        file_name or '',
        downloaded.content,
        settings.DINGTALK_FILE_TEXT_MAX_BYTES,
    )
    non_secret_updates.update(
        {
            'file_hash': file_text.content_hash,
            'parse_status': file_text.status,
            'text_extract_detail': file_text.detail,
            'download_status': 'downloaded',
            'download_url_host': downloaded.download_url_host,
            'content_type': downloaded.content_type,
            'file_size': downloaded.size,
        }
    )
    if file_name and Path(file_name).suffix.lower() in EXCEL_SUFFIXES:
        processing_payload['fileContentBase64'] = base64.b64encode(downloaded.content).decode('ascii')
    return (file_text.text if file_text.status == 'text_captured' else ''), non_secret_updates, processing_payload


def _has_inline_file_content(payload: dict[str, Any]) -> bool:
    return any(payload.get(key) not in (None, '') for key in INLINE_FILE_KEYS)


def _is_attachment_candidate_payload(file_name: str | None, file_id: str | None, download_code: str | None) -> bool:
    return bool(_clean_text(file_name) or _clean_text(file_id) or _clean_text(download_code))


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


def _resolve_inbound_channel_type(payload: dict[str, Any], *, group_id: str) -> str:
    if not group_id:
        return 'dingtalk_private'

    conversation_type = _clean_text(
        _first_payload_value(
            payload,
            'conversationType',
            'conversation_type',
            'chatType',
            'chat_type',
        )
    ).lower()
    if conversation_type in {'group', 'chat', '2', 'group_chat', 'groupchat', 'chat_group'}:
        return 'dingtalk_group'
    if conversation_type in {'single', 'private', '1v1', 'private_chat', '1', 'one_to_one'}:
        return 'dingtalk_private'
    return 'dingtalk_private'


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


def _find_duplicate_inbound_message(
    db: Session,
    *,
    channel: str,
    group_id: str,
    trace_id: str,
) -> ChatInboxMessage | None:
    if not trace_id:
        return None
    query = db.query(ChatInboxMessage).filter(
        ChatInboxMessage.channel == channel,
        ChatInboxMessage.trace_id == trace_id,
    )
    if group_id:
        query = query.filter(ChatInboxMessage.group_id == group_id)
    return query.order_by(ChatInboxMessage.id.asc()).first()


def _inbound_inbox_text(
    payload: dict[str, Any],
    *,
    extracted_text: str,
    evidence: MultimodalEvidence | None,
) -> str:
    text = _clean_text(extracted_text)
    if text:
        return text
    evidence_text = _clean_text(getattr(evidence, 'recognized_text', None))
    if evidence_text:
        return evidence_text
    event = normalize_dingtalk_stream_event(payload)
    return _clean_text(event.file_name) or _clean_text(event.message_type)


def _inbound_evidence_metadata(evidence: MultimodalEvidence | None) -> dict[str, Any]:
    payload = dict(evidence.payload or {}) if evidence is not None else {}
    keys = (
        'business_date',
        'business_date_status',
        'dingtalk_content_type',
        'dingtalk_file_size',
        'dingtalk_message_time',
        'dingtalk_received_at',
        'downloadCode_present',
        'download_status',
        'file_hash',
        'file_name',
        'parse_status',
        'text_extract_detail',
    )
    metadata = {key: payload[key] for key in keys if payload.get(key) not in (None, '')}
    if payload.get('business_date_status') == 'missing':
        metadata['business_date'] = None
    return metadata


def _ensure_inbound_chat_inbox(
    db: Session,
    *,
    payload: dict[str, Any],
    channel: str,
    group_id: str,
    trace_id: str,
    sender_external_id: str,
    agent_code: str,
    extracted_text: str,
    evidence_id: int | None,
    inbound_dedupe_key: str,
    source_payload: dict[str, Any],
) -> ChatInboxMessage:
    existing = (
        db.query(ChatInboxMessage)
        .filter(ChatInboxMessage.inbound_dedupe_key == inbound_dedupe_key)
        .one_or_none()
    )
    if existing is not None:
        return existing

    existing = _find_duplicate_inbound_message(
        db,
        channel=channel,
        group_id=group_id,
        trace_id=trace_id,
    )
    if existing is not None:
        if existing.inbound_dedupe_key is None:
            existing.inbound_dedupe_key = inbound_dedupe_key
            db.add(existing)
            db.flush()
        return existing

    evidence = db.get(MultimodalEvidence, evidence_id) if evidence_id is not None else None
    inbox = ChatInboxMessage(
        channel=channel,
        group_id=group_id or None,
        sender_external_id=sender_external_id or None,
        text=_inbound_inbox_text(payload, extracted_text=extracted_text, evidence=evidence),
        agent_code=agent_code,
        trace_id=trace_id,
        inbound_dedupe_key=inbound_dedupe_key,
        source_payload=filter_sensitive_mapping(
            {
                **source_payload,
                **_inbound_evidence_metadata(evidence),
                'source': 'dingtalk_inbound',
                'channel': channel,
                'evidence_id': evidence_id,
            }
        ),
    )
    db.add(inbox)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(ChatInboxMessage)
            .filter(ChatInboxMessage.inbound_dedupe_key == inbound_dedupe_key)
            .one_or_none()
        )
        if existing is None:
            raise
        return existing
    return inbox


def _find_duplicate_inbound_evidence(
    db: Session,
    *,
    channel: str,
    group_id: str | None,
    trace_id: str,
    source_transport: str | None = None,
) -> MultimodalEvidence | None:
    clean_trace_id = _clean_text(trace_id)
    if not clean_trace_id:
        return None
    clean_channel = _clean_text(channel)
    clean_group_id = _clean_text(group_id)
    clean_source_transport = _clean_text(source_transport)
    rows = (
        db.query(MultimodalEvidence)
        .filter(MultimodalEvidence.payload.isnot(None))
        .order_by(MultimodalEvidence.id.asc())
        .all()
    )
    for row in rows:
        payload = row.payload if isinstance(row.payload, dict) else {}
        if _clean_text(payload.get('source')) != 'dingtalk':
            continue
        if _clean_text(payload.get('trace_id')) != clean_trace_id:
            continue
        if _clean_text(payload.get('channel')) != clean_channel:
            continue
        if _clean_text(payload.get('group_id')) != clean_group_id:
            continue
        if clean_source_transport and _clean_text(payload.get('source_transport')) != clean_source_transport:
            continue
        return row
    return None


def _ensure_inbound_token(header_token: str | None) -> None:
    accepted_tokens = {
        token
        for token in (
            _clean_text(getattr(settings, 'DINGTALK_INBOUND_TOKEN', None)),
            _clean_text(getattr(settings, 'HERMES_DINGTALK_INBOUND_TOKEN', None)),
        )
        if token
    }
    if not accepted_tokens:
        if settings.is_production_like:
            raise HTTPException(status_code=503, detail='dingtalk_inbound_token_required')
        return
    if _clean_text(header_token) not in accepted_tokens:
        raise HTTPException(status_code=401, detail='dingtalk_inbound_token_invalid')


def _ensure_inbound_request_auth(
    payload: dict[str, Any],
    *,
    header_token: str | None,
    signature: str | None,
    timestamp: str | None,
    nonce: str | None,
    kind: str | None,
) -> tuple[str, str, str | None]:
    if not signature and not timestamp and not nonce and not settings.is_production_like:
        _ensure_inbound_token(header_token)
        return 'dingtalk_signed_inbound', 'legacy_token', None

    clean_kind = _clean_text(kind) or 'signed_inbound'
    if re.fullmatch(r'[a-z0-9_-]{1,64}', clean_kind) is None:
        raise HTTPException(status_code=401, detail='dingtalk_inbound_kind_invalid')
    if clean_kind == 'dingtalk_stream':
        accepted_secrets = tuple(
            secret
            for secret in (
                _clean_text(getattr(settings, 'HERMES_DINGTALK_STREAM_RELAY_TOKEN', None)),
            )
            if secret
        )
        source_transport = 'dingtalk_stream'
    else:
        accepted_secrets = tuple(
            secret
            for secret in (
                _clean_text(getattr(settings, 'DINGTALK_INBOUND_TOKEN', None)),
                _clean_text(getattr(settings, 'HERMES_DINGTALK_INBOUND_TOKEN', None)),
            )
            if secret
        )
        source_transport = 'dingtalk_signed_inbound'
    if not accepted_secrets:
        raise HTTPException(status_code=503, detail='dingtalk_inbound_signature_secret_required')
    try:
        request_time = int(_clean_text(timestamp))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail='dingtalk_inbound_timestamp_invalid') from exc
    if abs(int(time.time()) - request_time) > 300:
        raise HTTPException(status_code=401, detail='dingtalk_inbound_timestamp_expired')
    clean_nonce = _clean_text(nonce)
    if not clean_nonce or len(clean_nonce) > 128:
        raise HTTPException(status_code=401, detail='dingtalk_inbound_nonce_invalid')
    try:
        clean_nonce.encode('ascii')
    except UnicodeEncodeError as exc:
        raise HTTPException(status_code=401, detail='dingtalk_inbound_nonce_invalid') from exc
    supplied_signature = _clean_text(signature)
    if supplied_signature.startswith('sha256='):
        supplied_signature = supplied_signature[7:]
    if len(supplied_signature) != 64:
        raise HTTPException(status_code=401, detail='dingtalk_inbound_signature_invalid')

    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    signed = (
        str(request_time).encode('ascii')
        + b'.'
        + clean_nonce.encode('ascii')
        + b'.'
        + clean_kind.encode('ascii')
        + b'.'
        + canonical
    )
    if not any(
        hmac.compare_digest(
            supplied_signature,
            hmac.new(secret.encode('utf-8'), signed, hashlib.sha256).hexdigest(),
        )
        for secret in accepted_secrets
    ):
        raise HTTPException(status_code=401, detail='dingtalk_inbound_signature_invalid')
    return source_transport, clean_kind, clean_nonce


def _consume_inbound_nonce(db: Session, *, kind: str, nonce: str) -> None:
    now = datetime.now(timezone.utc)
    nonce_hash = hashlib.sha256(f'{kind}\x1f{nonce}'.encode('utf-8')).hexdigest()
    db.add(
        AgentRateLimit(
            scope_key='dingtalk_inbound_nonce',
            event_key=nonce_hash,
            window_started_at=now,
            window_expires_at=now + timedelta(minutes=10),
            hit_count=1,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail='dingtalk_inbound_replay_detected') from exc


def _resolve_inbound_user(db: Session, payload: dict[str, Any]) -> User | None:
    sender_user_id = _clean_text(
        _first_payload_value(payload, 'senderStaffId', 'senderId', 'senderUserId', 'userid', 'userId')
    )
    sender_union_id = _clean_text(_first_payload_value(payload, 'senderUnionId', 'unionId'))
    if not sender_user_id and not sender_union_id:
        return None

    try:
        user = dingtalk_service.resolve_unique_dingtalk_user(
            db,
            dingtalk_user_id=sender_user_id,
            dingtalk_union_id=sender_union_id,
        )
    except dingtalk_service.DingTalkUserAmbiguous as exc:
        raise HTTPException(status_code=409, detail='dingtalk_user_ambiguous') from exc
    if not user:
        return None
    return user


def _has_inbound_agent_access(user: User | None) -> bool:
    if user is None:
        return False
    scope = build_scope_summary(user)
    return bool(scope.is_admin or scope.is_manager or scope.is_reviewer)


def _claim_inbound_receipt(
    db: Session,
    *,
    channel: str,
    group_id: str,
    trace_id: str,
    source_transport: str,
) -> tuple[DingTalkInboundReceipt, bool]:
    raw_key = '\x1f'.join((source_transport, channel, group_id, trace_id))
    receipt = DingTalkInboundReceipt(
        dedupe_key=hashlib.sha256(raw_key.encode('utf-8')).hexdigest(),
        channel=channel,
        group_id=group_id or None,
        trace_id=trace_id,
    )
    db.add(receipt)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(DingTalkInboundReceipt)
            .filter(DingTalkInboundReceipt.dedupe_key == receipt.dedupe_key)
            .one()
        )
        return existing, False
    return receipt, True


def _set_inbound_receipt_status(
    db: Session,
    receipt_id: int,
    status: str,
    *,
    commit: bool,
) -> None:
    db.query(DingTalkInboundReceipt).filter(DingTalkInboundReceipt.id == receipt_id).update(
        {
            DingTalkInboundReceipt.status: status,
            DingTalkInboundReceipt.updated_at: datetime.now(timezone.utc),
        },
        synchronize_session=False,
    )
    if commit:
        db.commit()


def _claim_inbound_agent_attempt(db: Session, receipt_id: int) -> bool:
    stale_before = datetime.now(timezone.utc) - timedelta(seconds=INBOUND_AGENT_PROCESSING_LEASE_SECONDS)
    updated = (
        db.query(DingTalkInboundReceipt)
        .filter(DingTalkInboundReceipt.id == receipt_id)
        .filter(
            or_(
                DingTalkInboundReceipt.status.in_(('evidence_recorded', 'agent_failed')),
                and_(
                    DingTalkInboundReceipt.status == 'agent_processing',
                    DingTalkInboundReceipt.updated_at < stale_before,
                ),
            )
        )
        .update(
            {
                DingTalkInboundReceipt.status: 'agent_processing',
                DingTalkInboundReceipt.attempt_count: DingTalkInboundReceipt.attempt_count + 1,
                DingTalkInboundReceipt.updated_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return updated == 1


def _duplicate_inbound_response(
    db: Session,
    *,
    channel: str,
    group_id: str,
    trace_id: str,
    source_transport: str,
) -> dict[str, Any]:
    inbox = _find_duplicate_inbound_message(db, channel=channel, group_id=group_id, trace_id=trace_id)
    evidence = _find_duplicate_inbound_evidence(
        db,
        channel=channel,
        group_id=group_id or None,
        trace_id=trace_id,
        source_transport=source_transport,
    )
    return {
        'errcode': 0,
        'errmsg': 'ok',
        'action': 'dingtalk-duplicate' if inbox is not None else 'dingtalk-evidence-duplicate',
        'status': 'duplicate',
        'trace_id': trace_id,
        'answer': '',
        'messages': [],
        'should_reply': False,
        'evidence_id': evidence.id if evidence is not None else None,
        'chat_inbox_id': inbox.id if inbox is not None else None,
        'agent_run_id': None,
        'report_id': None,
    }


@router.post('/agent-inbound')
def dingtalk_agent_inbound(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    inbound_token: str | None = Header(default=None, alias='x-dingtalk-inbound-token'),
    inbound_signature: str | None = Header(default=None, alias='x-dingtalk-inbound-signature'),
    inbound_timestamp: str | None = Header(default=None, alias='x-dingtalk-inbound-timestamp'),
    inbound_nonce: str | None = Header(default=None, alias='x-dingtalk-inbound-nonce'),
    inbound_kind: str | None = Header(default=None, alias='x-dingtalk-inbound-kind'),
) -> dict[str, Any]:
    source_transport, auth_kind, auth_nonce = _ensure_inbound_request_auth(
        payload,
        header_token=inbound_token,
        signature=inbound_signature,
        timestamp=inbound_timestamp,
        nonce=inbound_nonce,
        kind=inbound_kind,
    )
    if auth_nonce is not None:
        _consume_inbound_nonce(db, kind=auth_kind, nonce=auth_nonce)
    if not _clean_text(_first_payload_value(payload, 'receivedAt', 'received_at')):
        payload = {**payload, 'receivedAt': datetime.now(timezone.utc).isoformat()}
    group_id = _clean_text(_first_payload_value(payload, 'conversationId', 'conversation_id', 'chatId', 'openConversationId'))
    channel = _resolve_inbound_channel_type(payload, group_id=group_id)
    trace_id = _resolve_inbound_trace_id(payload)
    text = _extract_agent_text(payload)
    agent_code = _clean_text(_first_payload_value(payload, 'agentCode', 'agent_code')) or 'factory_dispatch'
    scoped_group_id = group_id if channel == 'dingtalk_group' else ''
    user: User | None = None
    channel_scope: dict[str, Any] | None = None
    if source_transport != 'dingtalk_stream':
        user = _resolve_inbound_user(db, payload)
        if not _has_inbound_agent_access(user):
            raise HTTPException(status_code=403, detail='dingtalk_agent_access_denied')
        assert user is not None
        channel_scope = _resolve_inbound_channel_scope(db, group_id=scoped_group_id, payload=payload)
        _ensure_inbound_channel_scope_access(user, channel_scope)

    receipt, receipt_created = _claim_inbound_receipt(
        db,
        channel=channel,
        group_id=group_id,
        trace_id=trace_id,
        source_transport=source_transport,
    )
    receipt_id = int(receipt.id)
    if not receipt_created and receipt.status not in (
        'evidence_pending',
        'evidence_recorded',
        'agent_processing',
        'agent_failed',
    ):
        return _duplicate_inbound_response(
            db,
            channel=channel,
            group_id=group_id,
            trace_id=trace_id,
            source_transport=source_transport,
        )
    if receipt_created:
        stream_result = ingest_dingtalk_stream_event(
            db,
            payload,
            dingtalk_service=dingtalk_service.service,
            require_authorized_group=False,
            source_transport=source_transport,
        )
        _set_inbound_receipt_status(db, receipt_id, 'evidence_recorded', commit=True)
    else:
        existing_evidence = _find_duplicate_inbound_evidence(
            db,
            channel=channel,
            group_id=group_id or None,
            trace_id=trace_id,
            source_transport=source_transport,
        )
        if receipt.status == 'evidence_pending':
            if existing_evidence is None:
                raise HTTPException(status_code=503, detail='dingtalk_inbound_evidence_pending')
            _set_inbound_receipt_status(db, receipt_id, 'evidence_recorded', commit=True)
        stream_result = {
            'accepted': existing_evidence is not None,
            'duplicate': True,
            'trace_id': trace_id,
            'evidence_id': existing_evidence.id if existing_evidence is not None else None,
        }
    sender_external_id = _clean_text(
        _first_payload_value(payload, 'senderStaffId', 'senderId', 'senderUserId', 'userid', 'userId')
    )
    source_payload = {
        **_sanitize_inbound_payload(payload),
        'source_transport': source_transport,
    }
    ingress_inbox = _ensure_inbound_chat_inbox(
        db,
        payload=payload,
        channel=channel,
        group_id=group_id,
        trace_id=trace_id,
        sender_external_id=sender_external_id,
        agent_code=agent_code,
        extracted_text=text,
        evidence_id=stream_result.get('evidence_id'),
        inbound_dedupe_key=receipt.dedupe_key,
        source_payload=source_payload,
    )
    db.commit()
    db.refresh(ingress_inbox)
    if source_transport == 'dingtalk_stream':
        user = _resolve_inbound_user(db, payload)
    if not text or not _has_inbound_agent_access(user):
        _set_inbound_receipt_status(db, receipt_id, 'completed_evidence', commit=True)
        return {
            'errcode': 0,
            'errmsg': 'ok',
            'action': 'dingtalk-evidence-duplicate' if stream_result.get('duplicate') else 'dingtalk-evidence-recorded',
            'status': 'duplicate' if stream_result.get('duplicate') else 'recorded',
            'trace_id': stream_result.get('trace_id') or _resolve_inbound_trace_id(payload),
            'answer': '',
            'messages': [],
            'should_reply': False,
            'evidence_id': stream_result.get('evidence_id'),
            'energy_ingest': stream_result.get('energy_ingest'),
            'chat_inbox_id': ingress_inbox.id,
            'agent_run_id': None,
            'report_id': None,
        }
    assert user is not None
    has_inbound_evidence = _has_inbound_evidence_payload(payload)
    queue_outbox = _has_bound_inbound_outbox_channel(db, group_id=scoped_group_id, agent_code=agent_code)
    if channel_scope is None:
        channel_scope = _resolve_inbound_channel_scope(db, group_id=scoped_group_id, payload=payload)
        try:
            _ensure_inbound_channel_scope_access(user, channel_scope)
        except HTTPException:
            _set_inbound_receipt_status(db, receipt_id, 'completed_evidence', commit=True)
            raise
    if not _claim_inbound_agent_attempt(db, receipt_id):
        if receipt.status == 'agent_processing':
            raise HTTPException(status_code=503, detail='dingtalk_inbound_agent_processing')
        return _duplicate_inbound_response(
            db,
            channel=channel,
            group_id=group_id,
            trace_id=trace_id,
            source_transport=source_transport,
        )
    day1_parse_error: Day1CommandParseError | None = None
    try:
        day1_command = None
        if not _is_legacy_slash_daily_report_command(text):
            event_time = parse_dingtalk_event_datetime(normalize_dingtalk_stream_event(payload).event_time)
            day1_command = parse_day1_command(
                text,
                default_year=event_time.year if event_time is not None else None,
                reference_date=event_time.date() if event_time is not None else None,
            )
    except Day1CommandParseError as exc:
        day1_parse_error = exc
        day1_command = None
    evidence_duplicate = _find_duplicate_inbound_evidence(
        db,
        channel=channel,
        group_id=group_id or None,
        trace_id=trace_id,
        source_transport=source_transport,
    )
    if day1_command is not None:
        command_date = day1_command.business_date.isoformat()
        source_payload = {
            **source_payload,
            'business_date': command_date,
            'business_date_status': 'command_explicit',
        }
        ingress_inbox.source_payload = {
            **dict(ingress_inbox.source_payload or {}),
            'business_date': command_date,
            'business_date_status': 'command_explicit',
        }
        db.add(ingress_inbox)
    if evidence_duplicate is not None and day1_command is not None:
        duplicate_payload = dict(evidence_duplicate.payload or {})
        duplicate_payload['business_date'] = command_date
        duplicate_payload['business_date_status'] = 'command_explicit'
        evidence_duplicate.payload = duplicate_payload
        db.add(evidence_duplicate)
    if evidence_duplicate is None:
        if has_inbound_evidence:
            _, attachment_payload_updates, _ = _prepare_attachment_processing_payload(payload)
            if attachment_payload_updates:
                source_payload = {**source_payload, **attachment_payload_updates}
        try:
            record_day1_dingtalk_evidence(
                db,
                payload=source_payload,
                actor=user,
                business_date=day1_command.business_date if day1_command is not None else None,
                channel=channel,
                group_id=group_id or None,
                trace_id=trace_id,
                recognized_text=text,
            )
        except Day1EvidenceError as exc:
            db.rollback()
            _set_inbound_receipt_status(db, receipt_id, 'rejected', commit=True)
            raise HTTPException(status_code=400, detail=redact_secret_text(str(exc))) from exc

    if day1_command is not None:
        decision = classify_day1_actor(
            user,
            sender_user_id=sender_external_id,
            sender_union_id=_clean_text(_first_payload_value(payload, 'senderUnionId', 'unionId')),
            channel=channel,
            group_id=group_id,
        )
        try:
            require_root_owner_for_day1_report(decision)
        except PermissionError as exc:
            _set_inbound_receipt_status(db, receipt_id, 'rejected', commit=False)
            db.commit()
            raise HTTPException(status_code=403, detail=str(exc)) from exc

        if not settings.HERMES_DAY1_ENABLED:
            _set_inbound_receipt_status(db, receipt_id, 'completed', commit=False)
            db.commit()
            answer = 'Hermes Day-1 当前未开启，已关闭完整版日报生成。'
            return {
                'errcode': 0,
                'errmsg': 'ok',
                'trace_id': trace_id,
                'status': 'disabled',
                'code': 'hermes_day1_disabled',
                'answer': answer,
                'messages': [],
                'chat_inbox_id': ingress_inbox.id,
                'agent_run_id': None,
                'report_id': None,
            }

        chat_inbox = ingress_inbox
        chat_inbox.source_payload = {
            **dict(chat_inbox.source_payload or {}),
            'day1_super_brain': True,
        }
        db.add(chat_inbox)

        try:
            result = run_day1_super_brain(
                db,
                command=day1_command,
                actor=user,
                trace_id=trace_id,
                chat_inbox=chat_inbox,
            )
            _set_inbound_receipt_status(db, receipt_id, 'completed', commit=False)
            db.commit()
        except Day1EvidenceError as exc:
            db.rollback()
            _set_inbound_receipt_status(db, receipt_id, 'rejected', commit=True)
            raise HTTPException(status_code=400, detail=redact_secret_text(str(exc))) from exc
        except Exception:
            db.rollback()
            _set_inbound_receipt_status(db, receipt_id, 'agent_failed', commit=True)
            raise

        return {
            'errcode': 0,
            'errmsg': 'ok',
            'trace_id': result.trace_id,
            'status': result.status,
            'answer': result.answer,
            'messages': result.reply_messages,
            'chat_inbox_id': chat_inbox.id,
            'agent_run_id': result.agent_run_id,
            'report_id': result.report_id,
        }

    root_owner_decision = classify_day1_actor(
        user,
        sender_user_id=sender_external_id,
        sender_union_id=_clean_text(_first_payload_value(payload, 'senderUnionId', 'unionId')),
        channel=channel,
        group_id=group_id,
    )
    if (
        channel == 'dingtalk_private'
        and root_owner_decision.is_root_owner
        and (
            _should_route_root_owner_private_production_turn(text)
            or day1_parse_error is not None
        )
    ):
        try:
            result = run_root_owner_production_turn(
                db,
                text=text,
                current_user=user,
                sender_external_id=sender_external_id or None,
                trace_id=trace_id or None,
                source_payload={
                    **source_payload,
                    **({'day1_parse_error': day1_parse_error.code} if day1_parse_error is not None else {}),
                },
                mes_reader=HermesMesReadService(get_mes_adapter()),
                chat_inbox=ingress_inbox,
            )
            _set_inbound_receipt_status(db, receipt_id, 'completed', commit=False)
            db.commit()
        except Exception:
            db.rollback()
            _set_inbound_receipt_status(db, receipt_id, 'agent_failed', commit=True)
            raise
        return {
            'errcode': 0,
            'errmsg': 'ok',
            'trace_id': result.trace_id,
            'agent_code': 'factory_dispatch',
            'status': result.status,
            'answer': result.answer,
            'messages': [result.answer] if result.answer else [],
            'chat_inbox_id': result.chat_inbox_id,
            'agent_run_id': result.agent_run_id,
            'report_id': None,
            'outbox_message_id': result.outbox_message_id,
            'dispatch_status': result.dispatch_status,
            'dispatch_detail': result.dispatch_detail,
        }

    if day1_parse_error is not None:
        _set_inbound_receipt_status(db, receipt_id, 'rejected', commit=True)
        raise HTTPException(status_code=400, detail=day1_parse_error.code) from day1_parse_error

    factory_brain_intent = _get_factory_brain_route_intent(text)
    if bool(getattr(settings, 'HERMES_FACTORY_BRAIN_ENABLED', False)) and factory_brain_intent is not None:
        from app.services.hermes_factory_brain_orchestrator import run_factory_brain_turn

        try:
            _require_root_owner_for_factory_brain_intent(
                intent=factory_brain_intent,
                user=user,
                sender_external_id=sender_external_id,
                sender_union_id=_clean_text(_first_payload_value(payload, 'senderUnionId', 'unionId')),
                channel=channel,
                group_id=group_id,
            )
        except PermissionError as exc:
            _set_inbound_receipt_status(db, receipt_id, 'rejected', commit=True)
            raise HTTPException(status_code=403, detail=str(exc)) from exc

        try:
            factory_result = run_factory_brain_turn(
                db,
                text=text,
                channel='dingtalk_group',
                group_id=group_id or None,
                sender_external_id=sender_external_id or None,
                current_user=user,
                trace_id=trace_id or None,
                source_payload=source_payload,
                chat_inbox=ingress_inbox,
            )
            _set_inbound_receipt_status(db, receipt_id, 'completed', commit=False)
            db.commit()
        except Exception:
            db.rollback()
            _set_inbound_receipt_status(db, receipt_id, 'agent_failed', commit=True)
            raise
        return {
            'errcode': 0,
            'errmsg': 'ok',
            'trace_id': factory_result.trace_id,
            'agent_code': 'factory_brain',
            'status': factory_result.status,
            'answer': factory_result.answer,
            'chat_inbox_id': factory_result.chat_inbox_id,
            'agent_run_id': factory_result.agent_run_id,
        }

    try:
        result = handle_agent_command(
            db,
            channel=channel,
            group_id=group_id or None,
            sender_external_id=sender_external_id or None,
            text=text,
            agent_code=agent_code,
            trace_id=trace_id or None,
            workshop=channel_scope['workshop'],
            machine_code=channel_scope['machine_code'],
            queue_outbox=queue_outbox,
            source_payload=source_payload,
            current_user=user,
            chat_inbox=ingress_inbox,
        )
        _set_inbound_receipt_status(db, receipt_id, 'completed', commit=False)
        db.commit()
    except AgentCommandError as exc:
        db.rollback()
        _set_inbound_receipt_status(db, receipt_id, 'rejected', commit=True)
        raise HTTPException(status_code=400, detail=redact_secret_text(str(exc))) from exc
    except Exception:
        db.rollback()
        _set_inbound_receipt_status(db, receipt_id, 'agent_failed', commit=True)
        raise

    return {
        'errcode': 0,
        'errmsg': 'ok',
        'trace_id': result.trace_id,
        'status': 'answered',
        'status_color': result.status_color,
        'intent': result.intent,
        'answer': result.answer,
        'messages': [result.answer] if result.answer else [],
        'chat_inbox_id': result.chat_inbox_id,
        'agent_run_id': result.agent_run_id,
        'report_id': None,
        'outbox_message_id': result.outbox_message_id,
    }
