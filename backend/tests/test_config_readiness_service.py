from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.config_readiness_service import inspect_pilot_config


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, mapping):
        self._mapping = mapping

    def query(self, model, *args, **kwargs):
        rows = self._mapping.get(getattr(model, "__name__", ""), [])
        return _FakeQuery(rows)


def test_inspect_pilot_config_reports_hard_issues_when_base_config_missing() -> None:
    db = _FakeDB(
        {
            "Workshop": [],
            "ShiftConfig": [],
            "Team": [],
            "User": [],
            "Equipment": [],
            "AttendanceSchedule": [],
        }
    )

    result = inspect_pilot_config(db, target_date=date(2026, 4, 6))

    assert result["hard_gate_passed"] is False
    hard_codes = {item["code"] for item in result["hard_issues"]}
    assert "NO_ACTIVE_WORKSHOP" in hard_codes
    assert "NO_ACTIVE_SHIFT" in hard_codes
    assert "NO_MOBILE_USER" in hard_codes
    assert "SCHEDULE_EMPTY" not in hard_codes
    warning_codes = {item["code"] for item in result["warning_issues"]}
    assert "SCHEDULE_EMPTY" in warning_codes
    assert result["checks"]["schedule"]["status"] == "warning"
    assert result["checks"]["schedule"]["action_required"] == "seed_schedule"


def test_inspect_pilot_config_passes_with_minimum_valid_setup() -> None:
    workshop = SimpleNamespace(id=1, name="铸轧车间", is_active=True)
    shift = SimpleNamespace(id=11, workshop_id=1, is_active=True)
    user = SimpleNamespace(
        id=7,
        username="leader01",
        name="张三",
        is_active=True,
        is_mobile_user=True,
        role="team_leader",
        workshop_id=1,
        team_id=None,
    )
    equipment = SimpleNamespace(
        code="ZR-01",
        name="1#机",
        workshop_id=1,
        bound_user_id=7,
        is_active=True,
    )
    schedule = SimpleNamespace(
        business_date=date(2026, 4, 6),
        shift_config_id=11,
        workshop_id=1,
        team_id=None,
    )
    db = _FakeDB(
        {
            "Workshop": [workshop],
            "ShiftConfig": [shift],
            "Team": [],
            "User": [user],
            "Equipment": [equipment],
            "AttendanceSchedule": [schedule],
        }
    )

    result = inspect_pilot_config(db, target_date=date(2026, 4, 6))

    assert result["hard_gate_passed"] is True
    assert result["hard_issues"] == []


def test_inspect_pilot_config_detects_uncovered_schedule_workshop() -> None:
    workshop1 = SimpleNamespace(id=1, name="铸轧车间", is_active=True)
    workshop2 = SimpleNamespace(id=2, name="熔铸车间", is_active=True)
    shift = SimpleNamespace(id=11, workshop_id=None, is_active=True)
    user1 = SimpleNamespace(
        id=7,
        username="leader01",
        name="张三",
        is_active=True,
        is_mobile_user=True,
        role="team_leader",
        workshop_id=1,
        team_id=None,
    )
    user2 = SimpleNamespace(
        id=8,
        username="leader02",
        name="李四",
        is_active=True,
        is_mobile_user=True,
        role="team_leader",
        workshop_id=2,
        team_id=None,
    )
    schedule = SimpleNamespace(
        business_date=date(2026, 4, 6),
        shift_config_id=11,
        workshop_id=1,
        team_id=None,
    )
    db = _FakeDB(
        {
            "Workshop": [workshop1, workshop2],
            "ShiftConfig": [shift],
            "Team": [],
            "User": [user1, user2],
            "Equipment": [],
            "AttendanceSchedule": [schedule],
        }
    )

    result = inspect_pilot_config(db, target_date=date(2026, 4, 6))

    hard_codes = {item["code"] for item in result["hard_issues"]}
    assert "SCHEDULE_WORKSHOP_UNCOVERED" in hard_codes


def test_inspect_pilot_config_allows_warning_only_gate() -> None:
    workshop = SimpleNamespace(id=1, name="铸轧车间", is_active=True)
    shift = SimpleNamespace(id=11, workshop_id=1, is_active=True)
    user = SimpleNamespace(
        id=7,
        username="leader01",
        name="张三",
        is_active=True,
        is_mobile_user=True,
        role="team_leader",
        workshop_id=1,
        team_id=None,
    )
    schedule = SimpleNamespace(
        business_date=date(2026, 4, 6),
        shift_config_id=11,
        workshop_id=1,
        team_id=None,
    )
    db = _FakeDB(
        {
            "Workshop": [workshop],
            "ShiftConfig": [shift],
            "Team": [],
            "User": [user],
            "Equipment": [],
            "AttendanceSchedule": [schedule],
        }
    )

    result = inspect_pilot_config(db, target_date=date(2026, 4, 6))

    assert result["hard_gate_passed"] is True
    assert result["hard_issues"] == []
    warning_codes = {item["code"] for item in result["warning_issues"]}
    assert warning_codes == {"NO_ACTIVE_EQUIPMENT"}


def test_inspect_pilot_config_warns_when_no_equipment_user_bindings() -> None:
    workshop = SimpleNamespace(id=1, name="铸轧车间", is_active=True)
    shift = SimpleNamespace(id=11, workshop_id=1, is_active=True)
    user = SimpleNamespace(
        id=7,
        username="leader01",
        name="张三",
        is_active=True,
        is_mobile_user=True,
        role="team_leader",
        workshop_id=1,
        team_id=None,
    )
    equipment = SimpleNamespace(
        code="ZR-01",
        name="1#机",
        workshop_id=1,
        bound_user_id=None,
        is_active=True,
    )
    schedule = SimpleNamespace(
        business_date=date(2026, 4, 6),
        shift_config_id=11,
        workshop_id=1,
        team_id=None,
    )
    db = _FakeDB(
        {
            "Workshop": [workshop],
            "ShiftConfig": [shift],
            "Team": [],
            "User": [user],
            "Equipment": [equipment],
            "AttendanceSchedule": [schedule],
        }
    )

    result = inspect_pilot_config(db, target_date=date(2026, 4, 6))

    assert result["hard_gate_passed"] is True
    assert result["checks"]["equipment_binding"]["status"] == "warning"
    warning_codes = {item["code"] for item in result["warning_issues"]}
    assert "EQUIPMENT_USER_BINDING_EMPTY" in warning_codes


def test_inspect_pilot_config_errors_when_equipment_binding_points_to_missing_user() -> None:
    workshop = SimpleNamespace(id=1, name="铸轧车间", is_active=True)
    shift = SimpleNamespace(id=11, workshop_id=1, is_active=True)
    user = SimpleNamespace(
        id=7,
        username="leader01",
        name="张三",
        is_active=True,
        is_mobile_user=True,
        role="team_leader",
        workshop_id=1,
        team_id=None,
    )
    equipment = SimpleNamespace(
        code="ZR-01",
        name="1#机",
        workshop_id=1,
        bound_user_id=999,
        is_active=True,
    )
    schedule = SimpleNamespace(
        business_date=date(2026, 4, 6),
        shift_config_id=11,
        workshop_id=1,
        team_id=None,
    )
    db = _FakeDB(
        {
            "Workshop": [workshop],
            "ShiftConfig": [shift],
            "Team": [],
            "User": [user],
            "Equipment": [equipment],
            "AttendanceSchedule": [schedule],
        }
    )

    result = inspect_pilot_config(db, target_date=date(2026, 4, 6))

    assert result["hard_gate_passed"] is False
    assert result["checks"]["equipment_binding"]["status"] == "error"
    hard_codes = {item["code"] for item in result["hard_issues"]}
    assert "EQUIPMENT_USER_BINDING_INVALID" in hard_codes


def test_inspect_pilot_config_warns_when_no_schedule_data_exists() -> None:
    workshop = SimpleNamespace(id=1, name="铸轧车间", is_active=True)
    shift = SimpleNamespace(id=11, workshop_id=1, is_active=True)
    user = SimpleNamespace(
        id=7,
        username="leader01",
        name="张三",
        is_active=True,
        is_mobile_user=True,
        role="team_leader",
        workshop_id=1,
        team_id=None,
    )
    equipment = SimpleNamespace(
        code="ZR-01",
        name="1#机",
        workshop_id=1,
        bound_user_id=7,
        is_active=True,
    )
    db = _FakeDB(
        {
            "Workshop": [workshop],
            "ShiftConfig": [shift],
            "Team": [],
            "User": [user],
            "Equipment": [equipment],
            "AttendanceSchedule": [],
        }
    )

    result = inspect_pilot_config(db, target_date=date(2026, 4, 6))

    assert result["hard_gate_passed"] is True
    assert result["checks"]["schedule"]["status"] == "warning"
    assert result["checks"]["schedule"]["action_required"] == "seed_schedule"
    warning_codes = {item["code"] for item in result["warning_issues"]}
    assert "SCHEDULE_EMPTY" in warning_codes


def test_inspect_pilot_config_errors_when_schedule_exists_but_target_date_is_empty() -> None:
    workshop = SimpleNamespace(id=1, name="铸轧车间", is_active=True)
    shift = SimpleNamespace(id=11, workshop_id=1, is_active=True)
    user = SimpleNamespace(
        id=7,
        username="leader01",
        name="张三",
        is_active=True,
        is_mobile_user=True,
        role="team_leader",
        workshop_id=1,
        team_id=None,
    )
    equipment = SimpleNamespace(
        code="ZR-01",
        name="1#机",
        workshop_id=1,
        bound_user_id=7,
        is_active=True,
    )
    old_schedule = SimpleNamespace(
        business_date=date(2026, 4, 5),
        shift_config_id=11,
        workshop_id=1,
        team_id=None,
    )
    db = _FakeDB(
        {
            "Workshop": [workshop],
            "ShiftConfig": [shift],
            "Team": [],
            "User": [user],
            "Equipment": [equipment],
            "AttendanceSchedule": [old_schedule],
        }
    )

    result = inspect_pilot_config(db, target_date=date(2026, 4, 6))

    assert result["hard_gate_passed"] is False
    assert result["checks"]["schedule"]["status"] == "error"
    hard_codes = {item["code"] for item in result["hard_issues"]}
    assert "SCHEDULE_EMPTY" in hard_codes


def test_inspect_pilot_config_accepts_inactive_same_workshop_machine_binding() -> None:
    workshop = SimpleNamespace(id=1, name="铸轧车间", is_active=True)
    shift = SimpleNamespace(id=11, workshop_id=1, is_active=True)
    machine_user = SimpleNamespace(
        id=7,
        username="ZR-01",
        name="1#机",
        is_active=False,
        is_mobile_user=True,
        role="shift_leader",
        workshop_id=1,
        team_id=None,
    )
    leader = SimpleNamespace(
        id=8,
        username="leader01",
        name="张三",
        is_active=True,
        is_mobile_user=True,
        role="team_leader",
        workshop_id=1,
        team_id=None,
    )
    equipment = SimpleNamespace(
        code="ZR-01",
        name="1#机",
        workshop_id=1,
        bound_user_id=7,
        is_active=True,
    )
    schedule = SimpleNamespace(
        business_date=date(2026, 4, 6),
        shift_config_id=11,
        workshop_id=1,
        team_id=None,
    )
    db = _FakeDB(
        {
            "Workshop": [workshop],
            "ShiftConfig": [shift],
            "Team": [],
            "User": [machine_user, leader],
            "Equipment": [equipment],
            "AttendanceSchedule": [schedule],
        }
    )

    result = inspect_pilot_config(db, target_date=date(2026, 4, 6))

    hard_codes = {item["code"] for item in result["hard_issues"]}
    assert "EQUIPMENT_USER_BINDING_INVALID" not in hard_codes
