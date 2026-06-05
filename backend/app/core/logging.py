from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any

from app.core.redaction import redact_secret_text


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': redact_secret_text(record.getMessage()),
        }
        telemetry = getattr(record, 'telemetry', None)
        if telemetry is not None:
            payload['telemetry'] = telemetry
        if record.exc_info:
            payload['exc_info'] = redact_secret_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_json_logging() -> None:
    root = logging.getLogger()
    formatter = JsonLogFormatter()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root.addHandler(handler)
        return
    for handler in root.handlers:
        handler.setFormatter(formatter)
