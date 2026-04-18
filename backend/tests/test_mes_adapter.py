from datetime import date

import pytest

from app.adapters.mes_adapter import NullMesAdapter, get_mes_adapter, set_mes_adapter
from app.main import create_mes_adapter


class _StubMesAdapter(NullMesAdapter):
    pass


def test_null_mes_adapter_returns_empty_values() -> None:
    adapter = NullMesAdapter()

    assert adapter.get_tracking_card_info('RA260001') is None
    assert adapter.get_daily_schedule(date(2026, 3, 28), 'hot_rolling') == []
    assert adapter.push_completion('RA260001', 9220, 97.2) is False


def test_mes_adapter_provider_can_be_overridden() -> None:
    original = get_mes_adapter()
    replacement = _StubMesAdapter()

    try:
        set_mes_adapter(replacement)
        assert get_mes_adapter() is replacement
    finally:
        set_mes_adapter(original)


def test_create_mes_adapter_returns_null_adapter(monkeypatch) -> None:
    monkeypatch.setattr('app.main.settings.MES_ADAPTER', 'null', raising=False)

    adapter = create_mes_adapter()

    assert isinstance(adapter, NullMesAdapter)


def test_create_mes_adapter_rejects_unknown_adapter(monkeypatch) -> None:
    monkeypatch.setattr('app.main.settings.MES_ADAPTER', 'vendor-x', raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        create_mes_adapter()

    assert 'Unsupported MES_ADAPTER' in str(exc_info.value)
