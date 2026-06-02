from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.config_readiness_service import (
    build_owner_workshop_binding_plan,
    inspect_pilot_config,
)


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
        role="machine_operator",
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
        role="machine_operator",
        workshop_id=1,
        team_id=None,
    )
    user2 = SimpleNamespace(
        id=8,
        username="leader02",
        name="李四",
        is_active=True,
        is_mobile_user=True,
        role="machine_operator",
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
        role="machine_operator",
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
        role="machine_operator",
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
        role="machine_operator",
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
        role="machine_operator",
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


def test_inspect_pilot_config_does_not_hard_block_factory_wide_mobile_accounts() -> None:
    workshop = SimpleNamespace(id=1, name="铸轧车间", is_active=True)
    shift = SimpleNamespace(id=11, workshop_id=1, is_active=True)
    leader = SimpleNamespace(
        id=7,
        username="leader01",
        name="张三",
        is_active=True,
        is_mobile_user=True,
        role="machine_operator",
        workshop_id=1,
        team_id=None,
    )
    factory_manager = SimpleNamespace(
        id=8,
        username="factory-manager",
        name="厂级管理员",
        is_active=True,
        is_mobile_user=True,
        role="manager",
        workshop_id=None,
        team_id=None,
    )
    admin = SimpleNamespace(
        id=9,
        username="admin",
        name="系统管理员",
        is_active=True,
        is_mobile_user=True,
        role="admin",
        workshop_id=None,
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
            "User": [leader, factory_manager, admin],
            "Equipment": [equipment],
            "AttendanceSchedule": [schedule],
        }
    )

    result = inspect_pilot_config(db, target_date=date(2026, 4, 6))

    assert result["hard_gate_passed"] is True
    hard_codes = {item["code"] for item in result["hard_issues"]}
    warning_codes = {item["code"] for item in result["warning_issues"]}
    assert "MOBILE_USER_WORKSHOP_MISSING" not in hard_codes
    assert "MOBILE_USER_WORKSHOP_OPTIONAL" not in warning_codes


def test_inspect_pilot_config_hard_blocks_owner_roles_without_workshop() -> None:
    workshop = SimpleNamespace(id=1, name="铸轧车间", is_active=True)
    shift = SimpleNamespace(id=11, workshop_id=1, is_active=True)
    leader = SimpleNamespace(
        id=7,
        username="leader01",
        name="张三",
        is_active=True,
        is_mobile_user=True,
        role="machine_operator",
        workshop_id=1,
        team_id=None,
    )
    owner_roles = [
        SimpleNamespace(
            id=8,
            username="CPK-PL",
            name="计划科",
            is_active=True,
            is_mobile_user=True,
            role="planning_owner",
            workshop_id=None,
            team_id=None,
        ),
        SimpleNamespace(
            id=9,
            username="CPK-FS",
            name="成品库负责人",
            is_active=True,
            is_mobile_user=True,
            role="storage_owner",
            workshop_id=None,
            team_id=None,
        ),
        SimpleNamespace(
            id=10,
            username="CPK-EC",
            name="水电气负责人",
            is_active=True,
            is_mobile_user=True,
            role="energy_chief",
            workshop_id=None,
            team_id=None,
        ),
    ]
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
            "User": [leader, *owner_roles],
            "Equipment": [equipment],
            "AttendanceSchedule": [schedule],
        }
    )

    result = inspect_pilot_config(db, target_date=date(2026, 4, 6))

    assert result["hard_gate_passed"] is False
    missing = next(item for item in result["hard_issues"] if item["code"] == "MOBILE_USER_WORKSHOP_MISSING")
    assert "CPK-PL(计划科)" in missing["sample"]
    assert "CPK-FS(成品库负责人)" in missing["sample"]
    assert "CPK-EC(水电气负责人)" in missing["sample"]
    assert "check_owner_account_bindings.py --json" in missing["suggestion"]


def test_owner_workshop_binding_plan_targets_unscoped_factory_owner_accounts() -> None:
    cpk = SimpleNamespace(id=11, code="CPK", name="成品库", is_active=True)
    admin = SimpleNamespace(
        id=1,
        username="admin",
        name="系统管理员",
        is_active=True,
        is_mobile_user=True,
        role="admin",
        workshop_id=None,
        team_id=None,
        data_scope_type="all",
    )
    bound_owner = SimpleNamespace(
        id=2,
        username="CPK-A-FS",
        name="成品库白班",
        is_active=True,
        is_mobile_user=True,
        role="storage_owner",
        workshop_id=11,
        team_id=None,
        data_scope_type="self_workshop",
    )
    factory_owners = [
        SimpleNamespace(
            id=3,
                username="CPK-PL",
                name="计划科",
                is_active=True,
                is_mobile_user=True,
                role="planning_owner",
            workshop_id=None,
            team_id=None,
            data_scope_type="factory",
        ),
        SimpleNamespace(
            id=4,
                username="CPK-FS",
                name="成品库负责人",
                is_active=True,
                is_mobile_user=True,
                role="storage_owner",
            workshop_id=None,
            team_id=None,
            data_scope_type="factory",
        ),
        SimpleNamespace(
            id=5,
                username="CPK-EC",
                name="水电气负责人",
                is_active=True,
                is_mobile_user=True,
                role="energy_chief",
            workshop_id=None,
            team_id=None,
            data_scope_type="factory",
        ),
    ]
    unknown_owner = SimpleNamespace(
        id=6,
        username="UNSCOPED-PLAN",
        name="未知计划账号",
        is_active=True,
        is_mobile_user=True,
        role="planning_owner",
        workshop_id=None,
        team_id=None,
        data_scope_type="factory",
    )
    db = _FakeDB({"Workshop": [cpk], "User": [admin, bound_owner, *factory_owners, unknown_owner]})

    result = build_owner_workshop_binding_plan(db, target_workshop_code="CPK")

    assert result["target_workshop"] == {"id": 11, "code": "CPK", "name": "成品库"}
    assert result["needs_repair"] is True
    assert result["can_apply"] is True
    assert [item["username"] for item in result["repairs"]] == ["CPK-PL", "CPK-FS", "CPK-EC"]
    assert {item["target_workshop_code"] for item in result["repairs"]} == {"CPK"}
    assert unknown_owner.workshop_id is None


def test_apply_owner_workshop_binding_plan_only_updates_repair_candidates() -> None:
    cpk = SimpleNamespace(id=11, code="CPK", name="成品库", is_active=True)
    admin = SimpleNamespace(
        id=1,
        username="admin",
        name="系统管理员",
        is_active=True,
        is_mobile_user=True,
        role="admin",
        workshop_id=None,
        team_id=None,
        data_scope_type="all",
    )
    owner = SimpleNamespace(
        id=3,
        username="CPK-PL",
        name="计划科",
        is_active=True,
        is_mobile_user=True,
        role="planning_owner",
        workshop_id=None,
        team_id=None,
        data_scope_type="factory",
    )
    db = _FakeDB({"Workshop": [cpk], "User": [admin, owner]})

    result = build_owner_workshop_binding_plan(db, target_workshop_code="CPK", apply=True)

    assert result["applied"] is True
    assert result["applied_count"] == 1
    assert owner.workshop_id == 11
    assert owner.data_scope_type == "self_workshop"
    assert admin.workshop_id is None
    assert admin.data_scope_type == "all"


def test_apply_owner_workshop_binding_plan_does_not_write_when_target_missing() -> None:
    owner = SimpleNamespace(
        id=3,
        username="FACTORY-CT",
        name="计划科",
        is_active=True,
        is_mobile_user=True,
        role="contracts",
        workshop_id=None,
        team_id=None,
        data_scope_type="factory",
    )
    db = _FakeDB({"Workshop": [], "User": [owner]})

    result = build_owner_workshop_binding_plan(db, target_workshop_code="CPK", apply=True)

    assert result["can_apply"] is False
    assert result["applied"] is False
    assert result["applied_count"] == 0
    assert owner.workshop_id is None
    assert owner.data_scope_type == "factory"
    assert [item["code"] for item in result["blockers"]] == ["TARGET_WORKSHOP_NOT_FOUND"]


def test_inspect_pilot_config_errors_when_schedule_exists_but_target_date_is_empty() -> None:
    workshop = SimpleNamespace(id=1, name="铸轧车间", is_active=True)
    shift = SimpleNamespace(id=11, workshop_id=1, is_active=True)
    user = SimpleNamespace(
        id=7,
        username="leader01",
        name="张三",
        is_active=True,
        is_mobile_user=True,
        role="machine_operator",
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
        role="machine_operator",
        workshop_id=1,
        team_id=None,
    )
    leader = SimpleNamespace(
        id=8,
        username="leader01",
        name="张三",
        is_active=True,
        is_mobile_user=True,
        role="energy_stat",
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
