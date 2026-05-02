from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from app.services.mobile_report import _utils as _utils
from app.services.mobile_report import lifecycle as lifecycle
from app.services.mobile_report import shift_context as shift_context
from app.services.mobile_report import summary as summary

_MODULES = (_utils, lifecycle, shift_context, summary)
_PUBLIC_ALL = ['save_or_submit_report', 'upload_report_photo', 'store_report_photo', 'get_report_detail', 'list_report_history', 'sync_mobile_status_from_review', 'calculate_mobile_report_metrics', 'get_current_shift', 'get_mobile_bootstrap', 'summarize_mobile_reporting', 'summarize_mobile_inventory', 'recent_mobile_exceptions', 'count_linked_open_production_exceptions', 'list_coil_entries', 'create_coil_entry']


def _all_names() -> set[str]:
    names: set[str] = set()
    for module in _MODULES:
        names.update(
            name for name in module.__dict__
            if not name.startswith('__') and name != 'annotations'
        )
    return names


def _refresh_exports() -> None:
    names = _all_names()
    namespace: dict[str, Any] = {}
    for name in names:
        for module in _MODULES:
            if name in module.__dict__:
                namespace[name] = module.__dict__[name]
                break
    for module in _MODULES:
        for name, value in namespace.items():
            module.__dict__.setdefault(name, value)
    globals().update(namespace)


class _CompatModule(ModuleType):
    def __getattr__(self, name: str) -> Any:
        for module in _MODULES:
            if name in module.__dict__:
                return module.__dict__[name]
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        for module in _MODULES:
            if name in module.__dict__:
                module.__dict__[name] = value
        globals()[name] = value
        super().__setattr__(name, value)


_refresh_exports()
sys.modules[__name__].__class__ = _CompatModule

__all__ = _PUBLIC_ALL
