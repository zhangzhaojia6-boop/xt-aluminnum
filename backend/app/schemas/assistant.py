from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AssistantCapabilityOut(BaseModel):
    key: str
    label: str
    entrypoint: str


class AssistantIntegrationOut(BaseModel):
    key: str
    label: str
    status: Literal['mock_ready', 'planned', 'live']


class AssistantCapabilityGroupOut(BaseModel):
    key: str
    kicker: str
    label: str
    description: str
    examples: list[str]


class AssistantSummaryCardOut(BaseModel):
    key: str
    title: str
    value: str
    detail: str
    tone: Literal['primary', 'neutral', 'success']


class AssistantQuickActionOut(BaseModel):
    key: str
    label: str
    mode: Literal['answer', 'search', 'retrieve', 'generate_image', 'automation']
    query: str


class AssistantCapabilitiesResponseOut(BaseModel):
    connected: bool
    assistant_status: Literal['mock_ready', 'live']
    capabilities: list[AssistantCapabilityOut]
    integrations: list[AssistantIntegrationOut]
    quick_actions: list[AssistantQuickActionOut]
    groups: list[AssistantCapabilityGroupOut]
    summary_cards: list[AssistantSummaryCardOut]


class AssistantQueryRequestIn(BaseModel):
    mode: Literal['answer', 'search', 'retrieve', 'generate_image', 'automation']
    query: str
    surface: Literal['review_home'] | None = None


class AssistantResultCardOut(BaseModel):
    title: str
    summary: str
    source_labels: list[str]


class AssistantQueryResponseOut(BaseModel):
    mode: Literal['answer', 'search', 'retrieve', 'generate_image', 'automation']
    mock: bool
    summary: str
    cards: list[AssistantResultCardOut]
    integrations_used: list[str]
    next_actions: list[str]


class AssistantImageRequestIn(BaseModel):
    prompt: str
    image_type: Literal['daily_briefing_card']
    surface: Literal['review_home'] | None = None


class AssistantImageResponseOut(BaseModel):
    mock: bool
    image_type: Literal['daily_briefing_card']
    asset_id: str
    image_url: str
    suggested_caption: str
    next_actions: list[str]


class AssistantLiveProbeResponseOut(BaseModel):
    ready: bool
    text_probe_ok: bool
    image_probe_ok: bool
    overall_ok: bool
    text_model: str
    image_model: str
    checked_at: str
    errors: list[str]
