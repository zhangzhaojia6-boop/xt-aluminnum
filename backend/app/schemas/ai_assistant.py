from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AiConversationCreateIn(BaseModel):
    title: str | None = Field(default=None, max_length=128)
    scope: dict[str, Any] | None = None


class AiConversationOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class AiMessageCreateIn(BaseModel):
    content: str = Field(min_length=1)
    intent: str = 'factory_status'
    scope: dict[str, Any] | None = None


class AiMessageOut(BaseModel):
    role: str
    content: str
    timestamp: str
    payload: dict[str, Any] | None = None


class AiAskIn(BaseModel):
    question: str = Field(min_length=1)
    intent: str = 'factory_status'
    scope: dict[str, Any] | None = None


class AiEvidenceRefOut(BaseModel):
    kind: str
    key: str
    label: str | None = None


class AiAnswerOut(BaseModel):
    answer: str
    confidence: str
    evidence_refs: list[dict[str, Any]]
    missing_data: list[str]
    recommended_next_actions: list[str]
    can_create_watch: bool


class AiConversationMessageResponseOut(BaseModel):
    user_message: AiMessageOut
    assistant_message: AiMessageOut
    answer: AiAnswerOut
