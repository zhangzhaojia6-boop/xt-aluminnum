from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from typing import Callable


@dataclass(frozen=True, slots=True)
class ExternalReadonlySource:
    source_key: str
    domain: str
    priority: int
    readonly: bool
    enabled: bool
    fact_role: str
    health_query_key: str | None = None


@dataclass(frozen=True, slots=True)
class ExternalReadonlyHealth:
    source_key: str
    domain: str
    status: str
    readonly: bool
    last_success_at: str | None
    failure_reason: str | None


HealthProbe = Callable[[ExternalReadonlySource], ExternalReadonlyHealth | None]


def build_external_readonly_sources(*, energy_dsn: str | None = None) -> tuple[ExternalReadonlySource, ...]:
    energy_value = os.getenv("ENERGY_READONLY_DSN", "") if energy_dsn is None else energy_dsn
    return (
        ExternalReadonlySource(
            source_key="mes_readonly",
            domain="production",
            priority=20,
            readonly=True,
            enabled=True,
            fact_role="domain_fact_source",
            health_query_key="workshop_process_records",
        ),
        ExternalReadonlySource(
            source_key="energy_readonly",
            domain="energy",
            priority=20,
            readonly=True,
            enabled=bool(str(energy_value or "").strip()),
            fact_role="future_domain_fact_source",
            health_query_key=None,
        ),
    )


def health_check_sources(
    sources: tuple[ExternalReadonlySource, ...] | list[ExternalReadonlySource],
    *,
    probe: HealthProbe,
) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for source in sources:
        if not source.enabled:
            result[source.source_key] = asdict(
                ExternalReadonlyHealth(
                    source_key=source.source_key,
                    domain=source.domain,
                    status="disabled",
                    readonly=source.readonly,
                    last_success_at=None,
                    failure_reason="source_not_configured",
                )
            )
            continue
        checked = probe(source)
        if checked is None:
            checked = ExternalReadonlyHealth(
                source_key=source.source_key,
                domain=source.domain,
                status="unknown",
                readonly=source.readonly,
                last_success_at=None,
                failure_reason="probe_not_registered",
            )
        result[source.source_key] = asdict(checked)
    return result
