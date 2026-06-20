from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import re
from typing import Any, Mapping
from uuid import UUID


_SENSITIVE_KEY_TOKENS = (
    'password',
    'passwd',
    'pwd',
    'secret',
    'token',
    'apikey',
    'api_key',
    'authorization',
    'credential',
    'mobile',
    'phone',
    'address',
    'email',
)

_TEXT_PATTERNS = (
    re.compile(r'(?i)\b(password|pwd|secret|token|api[_-]?key)\s*=\s*[^;,\s]+'),
    re.compile(r'(?i)\b(user id|uid)\s*=\s*[^;,\s]+'),
    re.compile(r'(?i)\b(authorization)\s*[:=]\s*[^;,\s]+'),
)
_URI_AUTHORITY_PATTERN = re.compile(
    r'(?i)\b((?:postgresql(?:\+[a-z0-9_]+)?|mysql|mssql|sqlserver|https?)://)[^/\s:@]+:[^@\s/]+@([^\s,;]+)'
)


def is_sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace('-', '_').replace(' ', '_')
    compact = normalized.replace('_', '')
    return any(token.replace('_', '') in compact for token in _SENSITIVE_KEY_TOKENS)


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return filter_sensitive_mapping(value)
    if isinstance(value, (list, tuple, set)):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def filter_sensitive_mapping(metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(value) for key, value in metadata.items() if not is_sensitive_key(key)}


def redact_secret_text(value: object) -> str:
    text = str(value)
    redacted = _URI_AUTHORITY_PATTERN.sub(lambda match: f'{match.group(1)}<redacted>@{match.group(2)}', text)
    for pattern in _TEXT_PATTERNS:
        redacted = pattern.sub(lambda match: f'{match.group(1)}=<redacted>', redacted)
    return redacted
