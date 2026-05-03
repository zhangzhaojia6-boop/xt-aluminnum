from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RuleConfigOut(BaseModel):
    id: int | None = None
    scope_type: str
    scope_key: str | None = None
    key: str
    value: float | int
    value_type: str
    version: int = 0
    updated_by: int | None = None
    updated_at: datetime | None = None
    source: str


class RuleConfigUpsert(BaseModel):
    scope_type: str
    scope_key: str | None = None
    key: str
    value: float | int


class RuleConfigUpdate(BaseModel):
    value: float | int

