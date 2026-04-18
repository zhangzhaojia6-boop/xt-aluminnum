from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import cv2
import numpy as np
import pytesseract
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.scope import build_scope_summary
from app.core.workshop_templates import get_workshop_template
from app.models.production import OCRSubmission
from app.models.system import User
from app.services.audit_service import record_entity_change

OCR_ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
OCR_MAX_BYTES = 8 * 1024 * 1024
NUMERIC_FIELD_NAMES = {
    'input_weight',
    'output_weight',
    'scrap_weight',
    'spool_weight',
    'energy_kwh',
    'gas_m3',
    'furnace_temp',
    'static_temp',
    'cast_speed',
    'skin_weight',
    'paper_furnace',
    'static_furnace',
    'unit_output',
    'gas_consumption',
    'trim_weight',
    'roll_speed',
    'verified_input_weight',
    'verified_output_weight',
}


def _http_error(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _public_upload_url(relative_path: str, *, public_prefix: str = '/uploads') -> str:
    prefix = public_prefix.rstrip('/')
    return f"{prefix}/{relative_path.lstrip('/')}"


def _normalize_filename(name: str) -> str:
    raw_name = (name or '').strip() or 'ocr'
    suffix = Path(raw_name).suffix.lower()
    if suffix not in OCR_ALLOWED_EXTENSIONS:
        suffix = '.jpg'
    stem = Path(raw_name).stem.strip().replace(' ', '_') or 'ocr'
    safe_stem = ''.join(char for char in stem if char.isalnum() or char in {'_', '-', '.'})
    safe_stem = safe_stem[:48] or 'ocr'
    return f'{safe_stem}{suffix}'


def store_ocr_image(
    *,
    file_bytes: bytes,
    original_name: str,
    upload_dir: Path,
    now: datetime | None = None,
    public_prefix: str = '/uploads',
) -> dict[str, Any]:
    if not file_bytes:
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'uploaded image is empty')
    if len(file_bytes) > OCR_MAX_BYTES:
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'uploaded image exceeds max size')

    normalized_name = _normalize_filename(original_name)
    suffix = Path(normalized_name).suffix.lower()
    if suffix not in OCR_ALLOWED_EXTENSIONS:
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'unsupported image type')

    current = now or _utcnow()
    relative_dir = Path('ocr') / current.strftime('%Y') / current.strftime('%m')
    absolute_dir = upload_dir / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f'{uuid4().hex}{suffix}'
    stored_path = absolute_dir / stored_name
    stored_path.write_bytes(file_bytes)

    relative_path = stored_path.relative_to(upload_dir).as_posix()
    return {
        'relative_path': relative_path,
        'file_name': normalized_name,
        'file_url': _public_upload_url(relative_path, public_prefix=public_prefix),
        'stored_at': current,
    }


def _deskew_image(image: np.ndarray) -> np.ndarray:
    edges = cv2.Canny(image, 50, 150)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=80,
        minLineLength=max(image.shape[1] // 4, 30),
        maxLineGap=20,
    )
    if lines is None:
        return image

    angles: list[float] = []
    for line in lines[:, 0]:
        x1, y1, x2, y2 = line
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if -25 <= angle <= 25:
            angles.append(float(angle))
    if not angles:
        return image

    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.3:
        return image

    height, width = image.shape[:2]
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'invalid image data')
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thresholded = cv2.adaptiveThreshold(
        grayscale,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    return _deskew_image(thresholded)


def _collect_template_fields(workshop_template_type: str, *, db: Session | None = None) -> list[dict[str, Any]]:
    if db is None:
        template = get_workshop_template(workshop_template_type, user_role='shift_leader')
    else:
        template = get_workshop_template(workshop_template_type, user_role='shift_leader', db=db)
    if template.get('supports_ocr') is False:
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'workshop template does not support OCR')
    return [
        *template.get('entry_fields', []),
        *template.get('extra_fields', []),
    ]


def _extract_token_confidences(ocr_data: dict[str, list[Any]]) -> dict[str, float]:
    token_confidences: dict[str, float] = {}
    texts = ocr_data.get('text', [])
    confs = ocr_data.get('conf', [])
    for index, token in enumerate(texts):
        text = str(token or '').strip()
        if not text:
            continue
        raw_conf = confs[index] if index < len(confs) else '0'
        try:
            confidence = max(float(raw_conf), 0.0) / 100.0
        except (TypeError, ValueError):
            confidence = 0.0
        token_confidences[text] = max(token_confidences.get(text, 0.0), confidence)
    return token_confidences


def _extract_numeric_value(raw_text: str, label: str) -> str | None:
    escaped_label = re.escape(label)
    match = re.search(rf'{escaped_label}[\s:：-]*([0-9]+(?:\.[0-9]+)?)', raw_text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_generic_value(raw_text: str, label: str) -> str | None:
    escaped_label = re.escape(label)
    match = re.search(rf'{escaped_label}[\s:：-]*([^\r\n]+)', raw_text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def extract_fields(image_bytes: bytes, workshop_template_type: str, *, db: Session | None = None) -> dict[str, Any]:
    processed = preprocess_image(image_bytes)
    try:
        raw_text = pytesseract.image_to_string(processed, lang='chi_sim+eng')
        ocr_data = pytesseract.image_to_data(processed, lang='chi_sim+eng', output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError as exc:  # pragma: no cover - runtime specific
        raise _http_error(status.HTTP_503_SERVICE_UNAVAILABLE, 'Tesseract OCR runtime is not installed') from exc
    except pytesseract.TesseractError as exc:
        raise _http_error(status.HTTP_500_INTERNAL_SERVER_ERROR, f'OCR extraction failed: {exc}') from exc

    token_confidences = _extract_token_confidences(ocr_data)
    fields: dict[str, dict[str, Any]] = {}
    for field in _collect_template_fields(workshop_template_type, db=db):
        label = str(field.get('label') or field['name'])
        name = field['name']
        field_type = str(field.get('type') or '')
        if name in NUMERIC_FIELD_NAMES or field_type == 'number':
            value = _extract_numeric_value(raw_text, label)
        else:
            value = _extract_generic_value(raw_text, label)

        confidence = None
        if value is not None:
            confidence = token_confidences.get(value)
            if confidence is None:
                confidence = token_confidences.get(label)
        fields[name] = {
            'value': value,
            'confidence': round(float(confidence), 2) if confidence is not None else None,
        }

    return {
        'raw_text': raw_text or '',
        'fields': fields,
        'image_id': uuid4().hex,
    }


def extract_submission(
    db: Session,
    *,
    file_name: str,
    file_bytes: bytes,
    workshop_type: str,
    current_user: User,
) -> dict[str, Any]:
    stored = store_ocr_image(
        file_bytes=file_bytes,
        original_name=file_name,
        upload_dir=settings.upload_dir_path,
        public_prefix='/uploads',
    )
    extracted = extract_fields(file_bytes, workshop_template_type=workshop_type, db=db)
    entity = OCRSubmission(
        image_path=stored['relative_path'],
        workshop_type=workshop_type,
        extracted_json=extracted,
        verified_json=None,
        status='pending_review',
        created_by=current_user.id,
    )
    db.add(entity)
    db.flush()
    record_entity_change(
        db,
        user=current_user,
        module='ocr',
        entity_type='ocr_submissions',
        entity_id=entity.id,
        action='extract',
        new_value={'workshop_type': workshop_type, 'image_path': entity.image_path},
        auto_commit=False,
    )
    db.commit()
    db.refresh(entity)
    return {
        'ocr_submission_id': entity.id,
        'image_url': stored['file_url'],
        'raw_text': extracted.get('raw_text', ''),
        'fields': extracted.get('fields', {}),
    }


def _ensure_submission_access(entity: OCRSubmission, current_user: User) -> None:
    summary = build_scope_summary(current_user)
    if summary.is_admin or summary.is_manager or summary.is_reviewer:
        return
    if entity.created_by != current_user.id:
        raise _http_error(status.HTTP_403_FORBIDDEN, 'OCR submission access denied')


def _build_prefill_payload(corrected_fields: dict[str, Any]) -> dict[str, Any]:
    from app.services.work_order_service import split_entry_form_payload

    split_payload = split_entry_form_payload(corrected_fields)
    prefill_payload: dict[str, Any] = {}
    prefill_payload.update(split_payload['work_order_values'])
    prefill_payload.update(split_payload['entry_values'])
    if split_payload['extra_values']:
        prefill_payload['extra_payload'] = split_payload['extra_values']
    if split_payload['qc_values']:
        prefill_payload['qc_payload'] = split_payload['qc_values']
    return prefill_payload


def verify_submission(
    db: Session,
    *,
    submission_id: int,
    corrected_fields: dict[str, Any],
    rejected: bool,
    current_user: User,
) -> dict[str, Any]:
    entity = db.get(OCRSubmission, submission_id)
    if entity is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, 'ocr submission not found')
    _ensure_submission_access(entity, current_user)

    cleaned_fields = {key: value for key, value in (corrected_fields or {}).items() if value is not None}
    entity.verified_json = {'corrected_fields': cleaned_fields}
    entity.status = 'rejected' if rejected else 'verified'

    prefill_payload = {} if rejected else _build_prefill_payload(cleaned_fields)
    if not rejected:
        prefill_payload['ocr_submission_id'] = entity.id

    record_entity_change(
        db,
        user=current_user,
        module='ocr',
        entity_type='ocr_submissions',
        entity_id=entity.id,
        action='verify',
        new_value={'status': entity.status, 'verified_fields': cleaned_fields},
        auto_commit=False,
    )
    db.commit()
    db.refresh(entity)
    return {
        'ocr_submission_id': entity.id,
        'status': entity.status,
        'prefill_payload': prefill_payload,
    }


def link_submission_to_entry(
    db: Session,
    *,
    submission_id: int,
    entry_id: int,
    operator: User,
) -> OCRSubmission:
    entity = db.get(OCRSubmission, submission_id)
    if entity is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, 'ocr submission not found')
    _ensure_submission_access(entity, operator)
    if entity.status != 'verified':
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'ocr submission must be verified before linking')
    entity.linked_entry_id = entry_id
    record_entity_change(
        db,
        user=operator,
        module='ocr',
        entity_type='ocr_submissions',
        entity_id=entity.id,
        action='link_entry',
        new_value={'linked_entry_id': entry_id},
        auto_commit=False,
    )
    return entity
