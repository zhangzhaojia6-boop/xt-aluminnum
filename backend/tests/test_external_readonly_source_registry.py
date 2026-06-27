from app.services.external_readonly_source_registry import (
    ExternalReadonlyHealth,
    build_external_readonly_sources,
    health_check_sources,
)


def test_registry_declares_mes_as_production_domain_readonly_fact_source() -> None:
    sources = build_external_readonly_sources()
    mes = next(item for item in sources if item.source_key == "mes_readonly")

    assert mes.domain == "production"
    assert mes.readonly is True
    assert mes.priority == 20
    assert mes.fact_role == "domain_fact_source"


def test_registry_keeps_future_energy_slot_without_claiming_it_is_connected() -> None:
    sources = build_external_readonly_sources(energy_dsn="")
    energy = next(item for item in sources if item.source_key == "energy_readonly")

    assert energy.domain == "energy"
    assert energy.readonly is True
    assert energy.enabled is False
    assert energy.fact_role == "future_domain_fact_source"


def test_health_check_reports_mes_probe_result_without_writing_data() -> None:
    sources = build_external_readonly_sources(energy_dsn="")

    def probe(source):
        if source.source_key == "mes_readonly":
            return ExternalReadonlyHealth(
                source_key=source.source_key,
                domain=source.domain,
                status="ok",
                readonly=True,
                last_success_at="2026-06-27T10:00:00+08:00",
                failure_reason=None,
            )
        return None

    result = health_check_sources(sources, probe=probe)

    assert result["mes_readonly"]["status"] == "ok"
    assert result["mes_readonly"]["readonly"] is True
    assert result["energy_readonly"]["status"] == "disabled"
