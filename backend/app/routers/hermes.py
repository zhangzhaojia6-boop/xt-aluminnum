from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.routers import dingtalk
from app.services import hermes_outbound_service

router = APIRouter(tags=['hermes'])


class HermesOutboundRequest(BaseModel):
    target_user_id: str
    content: str
    title: str = '鑫泰铝业智能大脑'
    trace_id: str | None = None
    dedupe_key: str | None = None
    source_ref: str | None = None


@router.post('/dingtalk/inbound')
def hermes_dingtalk_inbound(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    inbound_token: str | None = Header(default=None, alias='x-dingtalk-inbound-token'),
    inbound_signature: str | None = Header(default=None, alias='x-dingtalk-inbound-signature'),
    inbound_timestamp: str | None = Header(default=None, alias='x-dingtalk-inbound-timestamp'),
    inbound_nonce: str | None = Header(default=None, alias='x-dingtalk-inbound-nonce'),
    inbound_kind: str | None = Header(default=None, alias='x-dingtalk-inbound-kind'),
) -> dict[str, Any]:
    return dingtalk.dingtalk_agent_inbound(
        payload=payload,
        db=db,
        inbound_token=inbound_token,
        inbound_signature=inbound_signature,
        inbound_timestamp=inbound_timestamp,
        inbound_nonce=inbound_nonce,
        inbound_kind=inbound_kind,
    )


@router.post('/outbound')
def hermes_outbound(
    payload: HermesOutboundRequest,
    db: Session = Depends(get_db),
    relay_token: str | None = Header(default=None, alias='x-dingtalk-inbound-token'),
) -> dict[str, Any]:
    expected_token = str(settings.HERMES_DINGTALK_STREAM_RELAY_TOKEN or '').strip()
    supplied_token = str(relay_token or '').strip()
    if not expected_token:
        raise HTTPException(status_code=503, detail='hermes_outbound_token_required')
    if not supplied_token or not secrets.compare_digest(supplied_token, expected_token):
        raise HTTPException(status_code=401, detail='hermes_outbound_token_invalid')
    try:
        outcome = hermes_outbound_service.relay_proactive_message(
            db,
            target_user_id=payload.target_user_id,
            content=payload.content,
            title=payload.title,
            trace_id=payload.trace_id,
            dedupe_key=payload.dedupe_key,
            source_ref=payload.source_ref,
        )
    except hermes_outbound_service.HermesOutboundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        'success': True,
        'accepted': True,
        'status': outcome.status,
        'event_id': outcome.event_id,
        'outbox_message_id': outcome.outbox_message_id,
        'duplicate': outcome.duplicate,
    }


@router.get('/factory-brain/status')
def hermes_factory_brain_status() -> dict[str, object]:
    return {
        'enabled': bool(settings.HERMES_FACTORY_BRAIN_ENABLED),
        'model_provider': settings.HERMES_FACTORY_BRAIN_MODEL_PROVIDER,
        'checkpoint_mode': settings.HERMES_LANGGRAPH_CHECKPOINT_MODE,
    }
