from __future__ import annotations

from types import SimpleNamespace

from app.agents.validator import ValidatorAgent


class _FakeQuery:
    def __init__(self, row):
        self._row = row

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._row


class _FakeDB:
    def __init__(self, *, report, shift_data):
        self._report = report
        self._shift_data = shift_data

    def query(self, model, *args, **kwargs):
        model_name = getattr(model, "__name__", "")
        if model_name == "MobileShiftReport":
            return _FakeQuery(self._report)
        if model_name == "ShiftProductionData":
            return _FakeQuery(self._shift_data)
        return _FakeQuery(None)


def test_validator_returns_actionable_reason_when_blocked() -> None:
    report = SimpleNamespace(
        id=101,
        linked_production_data_id=None,
        report_status="submitted",
        returned_reason=None,
    )
    db = _FakeDB(report=report, shift_data=None)
    agent = ValidatorAgent()

    decisions = agent.execute(
        db=db,
        report_id=101,
        report_data={
            "attendance_count": 10,
            "input_weight": 50.0,
            "output_weight": 80.0,
        },
    )

    assert len(decisions) == 1
    assert decisions[0].action.value == "auto_reject"
    assert report.report_status == "returned"
    assert report.returned_reason is not None
    assert report.returned_reason.startswith("请按以下内容修改后再提交：")
    assert "1." in report.returned_reason
    assert "产出重量大于投入重量" in report.returned_reason


def test_validator_keeps_warning_as_non_blocking() -> None:
    report = SimpleNamespace(
        id=202,
        linked_production_data_id=9,
        report_status="submitted",
        returned_reason="旧原因",
    )
    shift_data = SimpleNamespace(
        id=9,
        data_status="pending",
        notes=None,
    )
    db = _FakeDB(report=report, shift_data=shift_data)
    agent = ValidatorAgent()

    decisions = agent.execute(
        db=db,
        report_id=202,
        report_data={
            "attendance_count": 55,
            "input_weight": 100.0,
            "output_weight": 95.0,
        },
    )

    assert len(decisions) == 1
    assert decisions[0].action.value == "auto_confirm"
    assert report.report_status == "approved"
    assert report.returned_reason is None
    assert shift_data.data_status == "confirmed"
    assert "自动校验通过" in (shift_data.notes or "")
