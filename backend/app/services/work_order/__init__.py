from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from app.services.work_order import _access as _access
from app.services.work_order import _utils as _utils
from app.services.work_order import amendment as amendment
from app.services.work_order import crud as crud
from app.services.work_order import entry as entry

_MODULES = (_utils, _access, entry, crud, amendment)
_PUBLIC_ALL = ['create_work_order', 'update_work_order', 'list_work_orders', 'get_work_order_by_tracking_card', 'list_entries_for_work_order', 'add_entry', 'update_entry', 'submit_entry', 'build_previous_stage_output', 'split_entry_form_payload', 'mask_table_payload', 'filter_entry_payloads_for_scope', 'request_amendment', 'approve_amendment', 'parse_process_route_code']


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
