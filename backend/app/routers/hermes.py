from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.routers import dingtalk


router = APIRouter(tags=['hermes'])


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


@router.get('/factory-brain/status')
def hermes_factory_brain_status() -> dict[str, object]:
    return {
        'enabled': bool(settings.HERMES_FACTORY_BRAIN_ENABLED),
        'model_provider': settings.HERMES_FACTORY_BRAIN_MODEL_PROVIDER,
        'checkpoint_mode': settings.HERMES_LANGGRAPH_CHECKPOINT_MODE,
    }
