from __future__ import annotations

import importlib

from app.services import report, report_service, work_order, work_order_service
from app.services.report import dashboard_builder
from app.services.work_order import entry


def test_report_service_shim_resolves_to_report_package() -> None:
    compat_module = importlib.import_module('app.services.report_service')

    assert compat_module is report
    assert report_service is report
    for public_name in report.__all__:
        assert getattr(compat_module, public_name) is getattr(report, public_name)


def test_report_service_shim_monkeypatch_propagates(monkeypatch) -> None:
    def fake_delivery_status(*_args, **_kwargs):
        return {'delivery_ready': True}

    monkeypatch.setattr(report_service, 'build_delivery_status', fake_delivery_status)

    assert dashboard_builder.build_delivery_status is fake_delivery_status
    assert report.build_delivery_status is fake_delivery_status


def test_work_order_service_shim_resolves_to_work_order_package() -> None:
    compat_module = importlib.import_module('app.services.work_order_service')

    assert compat_module is work_order
    assert work_order_service is work_order
    for public_name in work_order.__all__:
        assert getattr(compat_module, public_name) is getattr(work_order, public_name)


def test_work_order_service_shim_monkeypatch_propagates(monkeypatch) -> None:
    def fake_submit_entry(*_args, **_kwargs):
        return {'id': 1}

    monkeypatch.setattr(work_order_service, 'submit_entry', fake_submit_entry)

    assert entry.submit_entry is fake_submit_entry
    assert work_order.submit_entry is fake_submit_entry
