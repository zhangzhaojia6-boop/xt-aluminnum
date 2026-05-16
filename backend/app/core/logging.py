from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        telemetry = getattr(record, 'telemetry', None)
        if telemetry is not None:
            payload['telemetry'] = telemetry
        if record.exc_info:
            payload['exc_info'] = self.formatException(record.exc_info)
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
