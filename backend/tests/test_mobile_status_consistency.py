from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.mobile_report_service import save_or_submit_report


class _FakeQuery:
    def __init__(self, row):
        self._row = row

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._row


class _FakeDB:
    def __init__(self, *, shift, report, shift_data):
        self._shift = shift
        self.report = report
        self.shift_data = shift_data

    def get(self, _model, _key):
        return self._shift

    def query(self, model, *args, **kwargs):
        model_name = getattr(model, "__name__", "")
        if model_name == "MobileShiftReport":
            return _FakeQuery(self.report)
        if model_name == "ShiftProductionData":
            return _FakeQuery(self.shift_data)
        return _FakeQuery(None)

    def add(self, _entity):
        return None

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, _entity):
        return None


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        id=11,
        role="team_leader",
        workshop_id=1,
        team_id=10,
        data_scope_type="self_team",
        assigned_shift_ids=[],
        is_mobile_user=True,
        is_reviewer=False,
        is_manager=False,
        name="班长",
        dingtalk_user_id="wx-leader-11",
        dingtalk_union_id="union-11",
    )


def _report() -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        business_date=date(2026, 4, 6),
        shift_config_id=1,
        workshop_id=1,
        team_id=10,
        owner_user_id=11,
        leader_user_id=11,
        leader_name="班长",
        dingtalk_user_id="wx-leader-11",
        dingtalk_union_id="union-11",
        report_status="draft",
        submitted_by_user_id=None,
        last_action_by_user_id=None,
        attendance_count=None,
        input_weight=None,
        output_weight=None,
        scrap_weight=None,
        storage_prepared=None,
        storage_finished=None,
        shipment_weight=None,
        contract_received=None,
        electricity_daily=None,
        gas_daily=None,
        has_exception=False,
        exception_type=None,
        note=None,
        optional_photo_url=None,
        last_saved_at=None,
        submitted_at=None,
        returned_reason=None,
        linked_production_data_id=None,
    )


def _shift_data() -> SimpleNamespace:
    return SimpleNamespace(
        id=101,
        data_status="pending",
        notes=None,
    )


def _patch_common(monkeypatch, *, workshop, team):
    monkeypatch.setattr("app.services.mobile_report_service.assert_mobile_user_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.services.mobile_report_service._resolve_workshop_team", lambda *_args, **_kwargs: (workshop, team))
    monkeypatch.setattr("app.services.mobile_report_service.assert_scope_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.services.mobile_report_service.assert_mobile_report_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.services.mobile_report_service._model_to_dict", lambda entity: dict(entity.__dict__))
    monkeypatch.setattr("app.services.mobile_report_service.record_entity_change", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "app.services.mobile_report_service._serialize_mobile_report",
        lambda _db, report, **_kwargs: {
            "id": report.id,
            "report_status": report.report_status,
            "returned_reason": report.returned_reason,
        },
    )


def test_submit_valid_report_changes_status_to_approved(monkeypatch) -> None:
    shift = SimpleNamespace(id=1, is_active=True, code="D", name="白班")
    workshop = SimpleNamespace(id=1, code="ZR1", name="铸轧")
    team = SimpleNamespace(id=10, name="甲班")
    report = _report()
    shift_data = _shift_data()
    db = _FakeDB(shift=shift, report=report, shift_data=shift_data)

    _patch_common(monkeypatch, workshop=workshop, team=team)
    monkeypatch.setattr("app.services.mobile_report_service._find_mobile_report", lambda *_args, **_kwargs: report)

    def _sync_stub(_db, *, report, shift, workshop, team):
        report.linked_production_data_id = shift_data.id
        shift_data.data_status = "pending"
        return shift_data

    monkeypatch.setattr("app.services.mobile_report_service._sync_to_shift_production", _sync_stub)

    payload = save_or_submit_report(
        db,
        payload={
            "business_date": date(2026, 4, 6),
            "shift_id": 1,
            "attendance_count": 12,
            "input_weight": 100.0,
            "output_weight": 95.0,
            "scrap_weight": 2.0,
        },
        current_user=_user(),
        submit=True,
    )

    assert payload["report_status"] == "approved"
    assert report.report_status == "approved"
    assert shift_data.data_status == "confirmed"


def test_submit_invalid_report_changes_status_to_returned(monkeypatch) -> None:
    shift = SimpleNamespace(id=1, is_active=True, code="D", name="白班")
    workshop = SimpleNamespace(id=1, code="ZR1", name="铸轧")
    team = SimpleNamespace(id=10, name="甲班")
    report = _report()
    shift_data = _shift_data()
    db = _FakeDB(shift=shift, report=report, shift_data=shift_data)

    _patch_common(monkeypatch, workshop=workshop, team=team)
    monkeypatch.setattr("app.services.mobile_report_service._find_mobile_report", lambda *_args, **_kwargs: report)

    def _sync_stub(_db, *, report, shift, workshop, team):
        report.linked_production_data_id = shift_data.id
        shift_data.data_status = "pending"
        return shift_data

    monkeypatch.setattr("app.services.mobile_report_service._sync_to_shift_production", _sync_stub)

    payload = save_or_submit_report(
        db,
        payload={
            "business_date": date(2026, 4, 6),
            "shift_id": 1,
            "attendance_count": 12,
            "input_weight": 80.0,
            "output_weight": 100.0,
            "scrap_weight": 2.0,
        },
        current_user=_user(),
        submit=True,
    )

    assert payload["report_status"] == "returned"
    assert report.report_status == "returned"
    assert "产出重量大于投入重量" in (report.returned_reason or "")
    assert shift_data.data_status == "pending"
