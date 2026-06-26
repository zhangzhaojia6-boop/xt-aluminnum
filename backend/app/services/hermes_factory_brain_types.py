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


@dataclass(frozen=True, slots=True)
class FactoryBrainDataReference:
    metric: str
    value: Any
    unit: str | None
    business_date: date | None
    source: str
    business_definition: str | None
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FactoryBrainNormalizedRequest:
    intent: FactoryBrainIntent
    normalized_text: str
    business_date: date | None
    scope: str
    org_units: list[str]
    metrics: list[str]
    data_sources: list[str]
    output_mode: str
    needs_artifact: bool = False


@dataclass(frozen=True, slots=True)
class FactoryBrainProgress:
    stage: str
    title: str
    details: list[str]
    trace_id: str


@dataclass(frozen=True, slots=True)
class FactoryBrainToolPlanStep:
    tool: str
    purpose: str
    priority: int
    required: bool


@dataclass(frozen=True, slots=True)
class FactoryBrainArtifactRequest:
    artifact_type: str
    title: str
    format: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FactoryBrainSkillPackagePlan:
    skill_name: str
    reason: str
    files: list[str]
    references: list[str]
    tests: list[str]


@dataclass(frozen=True, slots=True)
class FactoryBrainCapability:
    name: str
    capability_type: str
    priority: int
    enabled: bool
    use_when: str
