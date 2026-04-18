"""试点运行可观测服务。
用于替代现场口头追踪，统一记录关键运行节点日志，便于试点复盘与快速排障。
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from typing import Any


logger = logging.getLogger("pilot.runtime")


def log_pilot_event(event_name: str, /, **fields: Any) -> None:
    """记录试点运行事件日志。"""

    payload: dict[str, Any] = {
        "event": event_name,
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    payload.update(fields)
    logger.info(json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True))

