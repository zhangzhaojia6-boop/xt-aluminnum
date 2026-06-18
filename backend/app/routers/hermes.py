from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import dingtalk


router = APIRouter(tags=['hermes'])


@router.post('/dingtalk/inbound')
def hermes_dingtalk_inbound(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    inbound_token: str | None = Header(default=None, alias='x-dingtalk-inbound-token'),
) -> dict[str, Any]:
    return dingtalk.dingtalk_agent_inbound(payload=payload, db=db, inbound_token=inbound_token)
