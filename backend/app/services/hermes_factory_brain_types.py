from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class FactoryBrainIntent:
    intent_type: str
    task_type: str
    domain: str
    business_date: date | None
    entities: dict[str, Any] = field(default_factory=dict)
    should_use_factory_brain: bool = True
    requires_root_owner: bool = False
