from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from app.services.report import _utils as _utils
from app.services.report import dashboard_builder as dashboard_builder
from app.services.report import lane_builders as lane_builders
from app.services.report import report_generation as report_generation

_MODULES = (_utils, report_generation, lane_builders, dashboard_builder)
_PUBLIC_ALL = ['generate_daily_reports', 'review_report', 'publish_report', 'finalize_report', 'run_daily_pipeline', 'resolve_report_delivery_payload', 'list_reports', 'get_report', 'build_factory_dashboard', 'build_workshop_dashboard', 'build_statistics_dashboard', 'build_delivery_status']


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
