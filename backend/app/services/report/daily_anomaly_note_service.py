from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.core.health import current_business_date
from app.models.reports import DailyFactCorrection
from app.models.system import User
from app.services.audit_service import record_audit

ANOMALY_FIELD = "anomaly_explanation_daily"
ANOMALY_REASON = "异常说明"
MAX_LENGTH = 2000


def author_user_ids() -> set[int]:
    return {
        int(item)
        for item in str(settings.ANOMALY_NOTE_AUTHOR_USER_IDS or "").split(",")
        if item.strip().isdigit()
    }


def can_edit(user: User, business_date: date) -> bool:
    today = current_business_date()
    return user.id in author_user_ids() and business_date in {today, today - timedelta(days=1)}


def _active_rows(db: Session, business_date: date, *, lock: bool = False) -> list[DailyFactCorrection]:
    query = (
        db.query(DailyFactCorrection)
        .filter(
            DailyFactCorrection.business_date == business_date,
            DailyFactCorrection.field_name == ANOMALY_FIELD,
            DailyFactCorrection.status == "active",
        )
        # 和日报采用补录的顺序一致：最后一条生效
        .order_by(DailyFactCorrection.created_at.asc(), DailyFactCorrection.id.asc())
    )
    if lock:
        query = query.with_for_update()
    return query.all()


def read_anomaly_note(db: Session, *, user: User, business_date: date) -> dict:
    rows = _active_rows(db, business_date)
    latest = rows[-1] if rows else None
    author = db.get(User, latest.actor_user_id) if latest and latest.actor_user_id else None
    return {
        "business_date": business_date.isoformat(),
        "content": str((latest.value_payload or {}).get("value") or "") if latest else "",
        "author_name": author.name if author else None,
        "updated_at": latest.created_at.isoformat() if latest and latest.created_at else None,
        "can_edit": can_edit(user, business_date),
    }


def save_anomaly_note(db: Session, *, user: User, business_date: date, content: str) -> dict:
    if not can_edit(user, business_date):
        raise HTTPException(status_code=403, detail="只有指定作者能写今天或昨天的异常说明。")
    text = str(content or "").strip()
    if not text or len(text) > MAX_LENGTH:
        raise HTTPException(status_code=422, detail=f"异常说明需要 1 到 {MAX_LENGTH} 字。")

    for row in _active_rows(db, business_date, lock=True):
        row.status = "revoked"
    trace_id = f"anomaly-note:{business_date.isoformat()}:{uuid4().hex[:12]}"
    db.add(
        DailyFactCorrection(
            business_date=business_date,
            field_name=ANOMALY_FIELD,
            value_payload={"value": text},
            unit=None,
            source_text=text,
            before_value=None,
            reason=ANOMALY_REASON,
            actor_user_id=user.id,
            trace_id=trace_id,
            status="active",
        )
    )
    record_audit(
        db,
        user=user,
        action="anomaly_note_save",
        module="alerts",
        entity_type="daily_fact_corrections",
        detail={"business_date": business_date.isoformat(), "length": len(text), "trace_id": trace_id},
        auto_commit=False,
    )
    db.commit()
    return read_anomaly_note(db, user=user, business_date=business_date)
