from app.services.hermes_capability_registry import list_factory_capabilities


def test_capability_priority_prefers_structured_sources_before_browser() -> None:
    capabilities = list_factory_capabilities()
    by_name = {capability.name: capability for capability in capabilities}

    assert by_name['sql-api-file'].priority < by_name['browse-research'].priority
    assert by_name['browse-research'].priority < by_name['computer-use-operator'].priority
    assert by_name['image-generation'].capability_type == 'image'
