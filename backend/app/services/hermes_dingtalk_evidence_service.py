from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import re
from typing import Any, Mapping

from sqlalchemy import and_, case, or_
from sqlalchemy.orm import Session

from app.core.active_workshops import is_active_production_workshop_name, normalize_workshop_name
from app.core.business_time import production_business_window, resolve_production_business_date
from app.models.agent_communication import MultimodalEvidence
from app.services.dingtalk_energy_ingest_service import DATE_KEYS


ADOPTABLE_CONFIRMATION_STATUSES = {"specialist_sampled", "confirmed"}
TEXT_CONTENT_KEYS = ("message_text", "file_text", "attachment_text")
DATETIME_KEYS = (
    "sent_at",
    "sentAt",
    "event_time",
    "eventTime",
    "messageTime",
    "msgCreateTime",
    "dingtalk_message_time",
    "dingtalk_received_at",
    "received_at",
    "receivedAt",
)
SENDER_KEYS = (
    "dingtalk_sender_id",
    "senderStaffId",
    "senderId",
    "senderUserId",
    "senderUnionId",
)
GROUP_KEYS = ("group_id", "conversation_id", "conversationId")
FULL_DATE_RE = re.compile(r"(?P<year>20\d{2})[-/年]\s*(?P<month>\d{1,2})[-/月]\s*(?P<day>\d{1,2})")
MONTH_DAY_RE = re.compile(r"(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日")
DEFAULT_QUERY_LIMIT = 2000
MAX_QUERY_LIMIT = 5000


@dataclass(frozen=True, slots=True)
class DingTalkEvidenceItem:
    evidence_id: int
    trace_id: str
    business_date: date | None
    event_time: datetime | None
    group_id: str | None
    conversation_id: str | None
    sender_id: str | None
    content_kind: str
    text: str
    parse_status: str
    confirmation_status: str
    visible_to_hermes: bool
    adoptable_as_fact: bool
    source_key: str
    evidence_type: str
    file_uri: str | None
    payload: Mapping[str, Any]
    created_at: datetime | None
    source_user_id: int | None = None
    workshop_name: str | None = None


def query_dingtalk_evidence(
    db: Session,
    *,
    business_date: date,
    include_outside_business_context: bool = False,
    newest_first: bool = False,
    limit: int = DEFAULT_QUERY_LIMIT,
    per_source_key_limit: int | None = None,
    content_channels: tuple[str, ...] | None = None,
) -> list[DingTalkEvidenceItem]:
    target_date = business_date.isoformat()
    next_calendar_date = (business_date + timedelta(days=1)).isoformat()
    exact_date_match = or_(
        *(MultimodalEvidence.payload[key].as_string() == target_date for key in DATE_KEYS)
    )
    default_start, _ = production_business_window(business_date)
    _, special_end = production_business_window(business_date, workshop_name="热轧")
    target_text_match = or_(
        MultimodalEvidence.recognized_text.like(f"%{target_date}%"),
        MultimodalEvidence.recognized_text.like(
            f"%{business_date.year}年{business_date.month}月{business_date.day}日%"
        ),
        *(
            or_(
                MultimodalEvidence.payload[key].as_string().like(f"%{target_date}%"),
                MultimodalEvidence.payload[key].as_string().like(
                    f"%{business_date.year}年{business_date.month}月{business_date.day}日%"
                ),
            )
            for key in TEXT_CONTENT_KEYS
        ),
    )
    target_event_match = or_(
        *(
            or_(
                MultimodalEvidence.payload[key].as_string().like(f"{target_date}%"),
                MultimodalEvidence.payload[key].as_string().like(f"{next_calendar_date}%"),
            )
            for key in DATETIME_KEYS
        ),
    )
    target_created_match = and_(
        MultimodalEvidence.created_at >= default_start,
        MultimodalEvidence.created_at < special_end,
    )
    query = db.query(MultimodalEvidence).filter(
        MultimodalEvidence.payload.is_not(None),
        or_(
            MultimodalEvidence.payload["source"].as_string() == "dingtalk",
            MultimodalEvidence.evidence_type.like("dingtalk/_%", escape="/"),
            MultimodalEvidence.file_uri.like("dingtalk://%"),
        ),
    )
    if not include_outside_business_context:
        missing_explicit_date = and_(
            *(
                or_(
                    MultimodalEvidence.payload[key].as_string().is_(None),
                    MultimodalEvidence.payload[key].as_string() == "",
                )
                for key in DATE_KEYS
            )
        )
        query = query.filter(
            or_(
                exact_date_match,
                missing_explicit_date,
            )
        )
    output_limit = min(max(int(limit or DEFAULT_QUERY_LIMIT), 1), MAX_QUERY_LIMIT)
    rows = (
        query.order_by(
            case((exact_date_match, 0), else_=1),
            case((target_text_match, 0), else_=1),
            case((target_event_match, 0), else_=1),
            case((target_created_match, 0), else_=1),
            MultimodalEvidence.created_at.desc(),
            MultimodalEvidence.id.desc(),
        )
        .limit(MAX_QUERY_LIMIT)
        .all()
    )

    eligible_items: list[DingTalkEvidenceItem] = []
    source_key_limit = (
        min(max(int(per_source_key_limit), 1), MAX_QUERY_LIMIT)
        if per_source_key_limit is not None
        else None
    )
    allowed_content_channels = set(content_channels) if content_channels is not None else None
    for row in rows:
        raw_payload = row.payload if isinstance(row.payload, Mapping) else {}
        if not _is_dingtalk_row(row, raw_payload):
            continue
        item = _normalize_row(row, target_business_date=business_date)
        if item is not None and (
            include_outside_business_context
            or _belongs_to_business_context(
                item,
                business_date=business_date,
            )
        ):
            if (
                allowed_content_channels is not None
                and item.source_key == "dingtalk_group_content"
                and str(item.payload.get("channel") or "dingtalk_group") not in allowed_content_channels
            ):
                continue
            eligible_items.append(item)
    eligible_items.sort(
        key=lambda item: (
            item.created_at.timestamp() if item.created_at is not None else 0.0,
            item.evidence_id,
        ),
        reverse=True,
    )
    target_items = [item for item in eligible_items if item.business_date == business_date]
    candidate_items = [item for item in eligible_items if item.business_date != business_date]
    if not newest_first:
        target_items.reverse()
        candidate_items.reverse()
    ordered_items = [*target_items, *candidate_items]
    if source_key_limit is None:
        items = ordered_items[:output_limit]
    else:
        items = []
        source_key_counts: dict[str, int] = {}
        for item in ordered_items:
            if len(items) >= output_limit:
                break
            current_count = source_key_counts.get(item.source_key, 0)
            if current_count >= source_key_limit:
                continue
            source_key_counts[item.source_key] = current_count + 1
            items.append(item)
    return items


def dingtalk_evidence_adoption_reason(item: DingTalkEvidenceItem, *, business_date: date) -> str:
    if item.parse_status != "text_captured":
        return "parse_status_not_text_captured"
    if item.confirmation_status not in ADOPTABLE_CONFIRMATION_STATUSES:
        return "confirmation_status_not_adoptable"
    if not str(item.trace_id or "").strip():
        return "missing_trace_id"
    if item.business_date != business_date:
        return "payload_business_date_missing_or_mismatch"
    return "not_adoptable"


def _normalize_row(
    row: MultimodalEvidence,
    *,
    target_business_date: date,
) -> DingTalkEvidenceItem | None:
    payload = _effective_payload(row.payload if isinstance(row.payload, Mapping) else {})
    content_kind, text = _content_kind_and_text(row, payload)
    parse_status = str(payload.get("parse_status") or "unknown").strip()
    event_time = _coerce_datetime(_first_non_empty(payload, DATETIME_KEYS)) or row.created_at
    raw_workshop_name = _first_non_empty(payload, ("workshop_name", "workshop"))
    normalized_workshop_name = normalize_workshop_name(raw_workshop_name)
    workshop_name = normalized_workshop_name if is_active_production_workshop_name(normalized_workshop_name) else None
    business_date = _parse_business_date(_first_non_empty(payload, DATE_KEYS))
    if business_date is None:
        business_date = _derive_business_date_from_text(
            text,
            reference_time=event_time or row.created_at,
            workshop_name=workshop_name,
        )
    trace_id = str(payload.get("trace_id") or "").strip()
    group_id = _as_optional_text(_first_non_empty(payload, GROUP_KEYS))
    conversation_id = _as_optional_text(
        _first_non_empty(payload, ("conversation_id", "conversationId")) or group_id
    )
    sender_id = _as_optional_text(_first_non_empty(payload, SENDER_KEYS))
    visible_to_hermes = True
    adoptable_as_fact = (
        parse_status == "text_captured"
        and str(row.confirmation_status or "").strip() in ADOPTABLE_CONFIRMATION_STATUSES
        and business_date == target_business_date
        and bool(trace_id)
    )
    return DingTalkEvidenceItem(
        evidence_id=int(row.id),
        trace_id=trace_id,
        business_date=business_date,
        event_time=event_time,
        group_id=group_id,
        conversation_id=conversation_id,
        sender_id=sender_id,
        content_kind=content_kind,
        text=text,
        parse_status=parse_status,
        confirmation_status=str(row.confirmation_status or "").strip(),
        visible_to_hermes=visible_to_hermes,
        adoptable_as_fact=adoptable_as_fact,
        source_key=_source_key(row, payload, content_kind),
        evidence_type=str(row.evidence_type or "").strip(),
        file_uri=row.file_uri,
        payload=dict(payload),
        created_at=row.created_at,
        source_user_id=row.source_user_id,
        workshop_name=workshop_name,
    )


def _effective_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    confirm_result = payload.get("confirm_result")
    if not isinstance(confirm_result, Mapping):
        return dict(payload)
    merged = dict(payload)
    merged.update(confirm_result)
    return merged


def _content_kind_and_text(row: MultimodalEvidence, payload: Mapping[str, Any]) -> tuple[str, str]:
    for key in TEXT_CONTENT_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return key, value.strip()
    recognized = str(row.recognized_text or "").strip()
    if recognized:
        return "recognized_text", recognized
    return "recognized_text", ""


def _source_key(row: MultimodalEvidence, payload: Mapping[str, Any], content_kind: str) -> str:
    if row.file_uri or str(row.evidence_type or "").strip().lower() in {"attachment", "file", "dingtalk_file"}:
        return "dingtalk_group_file"
    if content_kind in {"file_text", "attachment_text"}:
        return "dingtalk_group_file"
    if payload.get("file_name") or payload.get("dingtalk_media_id"):
        return "dingtalk_group_file"
    return "dingtalk_group_content"


def _is_dingtalk_row(row: MultimodalEvidence, payload: Mapping[str, Any]) -> bool:
    source = str(payload.get("source") or "").strip().lower()
    if source and source != "dingtalk":
        return False
    if source == "dingtalk":
        return True
    evidence_type = str(row.evidence_type or "").strip().lower()
    if evidence_type.startswith("dingtalk_"):
        return True
    if str(row.file_uri or "").strip().lower().startswith("dingtalk://"):
        return True
    return False


def _belongs_to_business_context(
    item: DingTalkEvidenceItem,
    *,
    business_date: date,
) -> bool:
    if item.business_date == business_date:
        return True
    if item.event_time is None:
        return False
    window_start, window_end = production_business_window(
        business_date,
        workshop_name=item.workshop_name,
    )
    event_time = item.event_time
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=window_start.tzinfo)
    return window_start <= event_time < window_end


def _first_non_empty(payload: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _parse_business_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        numeric = float(text)
    except ValueError:
        numeric = None
    if numeric is not None:
        if abs(numeric) >= 10**11:
            numeric /= 1000.0
        try:
            return datetime.fromtimestamp(numeric, tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _derive_business_date_from_text(
    text: str,
    *,
    reference_time: datetime | None,
    workshop_name: str | None,
) -> date | None:
    clean = str(text or "").strip()
    if not clean:
        return None
    full_match = FULL_DATE_RE.search(clean)
    if full_match is not None:
        try:
            return date(
                int(full_match.group("year")),
                int(full_match.group("month")),
                int(full_match.group("day")),
            )
        except ValueError:
            return None
    month_day_match = MONTH_DAY_RE.search(clean)
    if month_day_match is not None:
        if reference_time is None:
            return None
        try:
            return date(
                reference_time.year,
                int(month_day_match.group("month")),
                int(month_day_match.group("day")),
            )
        except ValueError:
            return None
    if "今日" in clean or "今天" in clean:
        if not workshop_name:
            return None
        return _resolve_from_datetime(reference_time, workshop_name=workshop_name)
    return None


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        epoch_value = float(text)
    except ValueError:
        pass
    else:
        if abs(epoch_value) >= 100_000_000_000:
            epoch_value /= 1000
        try:
            return datetime.fromtimestamp(epoch_value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _resolve_from_datetime(value: datetime | None, *, workshop_name: str | None) -> date | None:
    if value is None:
        return None
    return resolve_production_business_date(value, workshop_name=workshop_name)


def _as_optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
