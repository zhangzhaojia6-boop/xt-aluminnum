from __future__ import annotations

import json
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, quote, urlsplit, urlunsplit

from app.core.redaction import filter_sensitive_mapping, redact_secret_text


DINGTALK_EPHEMERAL_KEYS = {
    'downloadcode',
    'download_code',
    'filecontentbase64',
    'file_content_base64',
    'filebytesbase64',
    'file_bytes_base64',
    'contentbase64',
    'filebytes',
    'file_bytes',
    'downloadedfilebytes',
}
DINGTALK_EPHEMERAL_QUERY_KEYS = {'downloadcode', 'download_code', 'access_token', 'signature', 'sign', 'sig'}
RAW_METADATA_MAX_STRING_LENGTH = 512
RAW_METADATA_MAX_ITEMS = 25
RAW_METADATA_MAX_DEPTH = 6
RAW_METADATA_TRUNCATION_MARKER = '...[truncated]'
SECRET_PAIR_PATTERN = re.compile(
    r'(?i)\b(downloadcode|download_code|access_token|signature|sign|sig)\s*[:=]\s*["\']?[^"\'\s,&}]+'
)
URL_PATTERN = re.compile(r'https?://[^\s"\'<>]+')


def sanitize_dingtalk_payload_for_storage(value: Any, *, depth: int = 0) -> Any:
    if depth >= RAW_METADATA_MAX_DEPTH:
        return RAW_METADATA_TRUNCATION_MARKER
    if isinstance(value, Mapping):
        filtered = filter_sensitive_mapping(value)
        sanitized: dict[str, Any] = {}
        kept = 0
        for raw_key, item in filtered.items():
            normalized_key = str(raw_key).strip().lower().replace('-', '_')
            if normalized_key in DINGTALK_EPHEMERAL_KEYS:
                continue
            if kept >= RAW_METADATA_MAX_ITEMS:
                sanitized['__truncated__'] = RAW_METADATA_TRUNCATION_MARKER
                break
            sanitized[str(raw_key)] = sanitize_dingtalk_payload_for_storage(item, depth=depth + 1)
            kept += 1
        return sanitized
    if isinstance(value, (list, tuple, set)):
        sanitized_items = [
            sanitize_dingtalk_payload_for_storage(item, depth=depth + 1)
            for item in list(value)[:RAW_METADATA_MAX_ITEMS]
        ]
        if len(value) > RAW_METADATA_MAX_ITEMS:
            sanitized_items.append(RAW_METADATA_TRUNCATION_MARKER)
        return sanitized_items
    if isinstance(value, str):
        return _sanitize_dingtalk_storage_text(value, depth=depth)
    return value


def _sanitize_dingtalk_storage_text(value: str, *, depth: int) -> Any:
    parsed = _parse_json_like_text(value)
    if parsed is not None:
        return sanitize_dingtalk_payload_for_storage(parsed, depth=depth + 1)
    sanitized = redact_secret_text(value)
    sanitized = SECRET_PAIR_PATTERN.sub(lambda match: f'{match.group(1)}=<redacted>', sanitized)
    sanitized = URL_PATTERN.sub(lambda match: _sanitize_signed_url(match.group(0)), sanitized)
    return _truncate_raw_metadata_string(sanitized)


def _parse_json_like_text(value: str) -> Mapping[str, Any] | list[Any] | None:
    text = str(value or '').strip()
    if not text:
        return None
    if not ((text.startswith('{') and text.endswith('}')) or (text.startswith('[') and text.endswith(']'))):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, (Mapping, list)):
        return parsed
    return None


def _sanitize_signed_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if not parts.scheme or not parts.netloc or not parts.query:
        return value
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    if not query_pairs:
        return value

    sanitized_pairs: list[str] = []
    for key, item in query_pairs:
        normalized_key = str(key).strip().lower().replace('-', '_')
        safe_key = quote(str(key), safe='')
        if normalized_key in DINGTALK_EPHEMERAL_QUERY_KEYS:
            sanitized_pairs.append(f'{safe_key}=<redacted>')
            continue
        sanitized_pairs.append(f'{safe_key}={quote(str(item), safe="")}')

    return urlunsplit((parts.scheme, parts.netloc, parts.path, '&'.join(sanitized_pairs), parts.fragment))


def _truncate_raw_metadata_string(value: str) -> str:
    if len(value) <= RAW_METADATA_MAX_STRING_LENGTH:
        return value
    keep = max(0, RAW_METADATA_MAX_STRING_LENGTH - len(RAW_METADATA_TRUNCATION_MARKER))
    return f'{value[:keep]}{RAW_METADATA_TRUNCATION_MARKER}'
