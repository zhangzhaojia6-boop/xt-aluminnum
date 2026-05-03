from __future__ import annotations

import base64
from datetime import date, datetime, time
from decimal import Decimal
import hashlib
import hmac
import json
from typing import Any

from app.config import settings


class LockedFieldsTokenInvalid(ValueError):
    pass


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    return value


def _normalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): _json_ready(value)
        for key, value in snapshot.items()
        if value is not None and str(value).strip() != ''
    }


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def _b64_decode(value: str) -> bytes:
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode('ascii'))


def _secret() -> bytes:
    return str(settings.SECRET_KEY).encode('utf-8')


def sign_locked_fields(snapshot: dict[str, Any]) -> str:
    payload = {
        'v': 1,
        'fields': _normalize_snapshot(snapshot),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(_secret(), raw, hashlib.sha256).digest()
    return f'{_b64_encode(raw)}.{_b64_encode(signature)}'


def verify_locked_fields_token(token: str) -> dict[str, Any]:
    try:
        raw_part, signature_part = str(token or '').split('.', 1)
        raw = _b64_decode(raw_part)
        signature = _b64_decode(signature_part)
    except Exception as exc:  # noqa: BLE001
        raise LockedFieldsTokenInvalid('locked_fields_token_invalid') from exc

    expected_signature = hmac.new(_secret(), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise LockedFieldsTokenInvalid('locked_fields_token_invalid')

    try:
        payload = json.loads(raw.decode('utf-8'))
    except Exception as exc:  # noqa: BLE001
        raise LockedFieldsTokenInvalid('locked_fields_token_invalid') from exc
    if payload.get('v') != 1 or not isinstance(payload.get('fields'), dict):
        raise LockedFieldsTokenInvalid('locked_fields_token_invalid')
    return _normalize_snapshot(payload['fields'])
