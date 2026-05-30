from __future__ import annotations

from datetime import date, time
from types import SimpleNamespace

from app.agents import reminder as reminder_module
from app.agents.reminder import ReminderAgent


class _FakeQuery:
    def __init__(self, *, rows=None, first=None, count_value=0):
        self._rows = rows or []
        self._first = first
        self._count = count_value

    def filter(self, *args, **kwargs):
        return self

    def distinct(self):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._first

    def count(self):
        return self._count


class _FakeDB:
    def __init__(self, *, schedule_rows, report_rows, reminder_count, leader, admins, existing_reminder=None):
        self.schedule_rows = schedule_rows
        self.report_rows = report_rows
        self.reminder_count = reminder_count
        self.leader = leader
        self.admins = admins
        self.existing_reminder = existing_reminder
        self.added = []
        self._user_query_call = 0

    def query(self, *entities):
        head = entities[0]
        model_name = getattr(getattr(head, "class_", None), "__name__", None) or getattr(head, "__name__", None)
        if model_name == "AttendanceSchedule":
            return _FakeQuery(rows=self.schedule_rows)
        if model_name == "MobileShiftReport":
            return _FakeQuery(rows=self.report_rows)
        if model_name == "Workshop":
            return _FakeQuery(rows=[SimpleNamespace(id=1, name="铸轧车间")])
        if model_name == "ShiftConfig":
            return _FakeQuery(rows=[SimpleNamespace(id=1, name="早班", code="A", end_time=time(8, 0), start_time=time(0, 0), business_day_offset=0, is_cross_day=False)])
        if model_name == "MobileReminderRecord":
            return _FakeQuery(first=self.existing_reminder, count_value=self.reminder_count)
        if model_name == "User":
            self._user_query_call += 1
            if self._user_query_call <= 1:
                return _FakeQuery(first=self.leader)
            return _FakeQuery(rows=self.admins)
        return _FakeQuery()

    def add(self, entity):
        self.added.append(entity)


def test_reminder_agent_message_template(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reminder.settings.DINGTALK_ENABLED", True, raising=False)
    sent = []
    agent = ReminderAgent()
    monkeypatch.setattr(agent, "_send_reminder_message", lambda userid, content: sent.append((userid, content)))
    db = _FakeDB(
        schedule_rows=[SimpleNamespace(business_date=date(2026, 4, 4), shift_config_id=1, workshop_id=1, team_id=None)],
        report_rows=[],
        reminder_count=0,
        leader=SimpleNamespace(id=10, name="张三", username="zhangsan", dingtalk_user_id="u_zhangsan"),
        admins=[],
    )

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert len(decisions) == 1
    assert "【催报提醒】铸轧车间 早班 的生产数据尚未提交" in decisions[0].reason
    assert "第1次提醒" in decisions[0].reason
    assert sent and "第1次提醒" in sent[0][1]
    assert db.added[0].reminder_channel == "dingtalk"
    assert "钉钉" in decisions[0].reason


def test_reminder_agent_updates_existing_record_instead_of_inserting(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reminder.settings.DINGTALK_ENABLED", False, raising=False)
    sent = []
    existing = SimpleNamespace(
        reminder_status="pending",
        reminder_channel="system",
        reminder_count=1,
        last_reminded_at=None,
        note="old",
    )
    agent = ReminderAgent()
    monkeypatch.setattr(agent, "_send_reminder_message", lambda userid, content: sent.append((userid, content)))
    db = _FakeDB(
        schedule_rows=[SimpleNamespace(business_date=date(2026, 4, 4), shift_config_id=1, workshop_id=1, team_id=None)],
        report_rows=[],
        reminder_count=1,
        leader=SimpleNamespace(id=10, name="张三", username="zhangsan", dingtalk_user_id=None),
        admins=[],
        existing_reminder=existing,
    )

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert len(decisions) == 1
    assert db.added == []
    assert existing.reminder_status == "sent"
    assert existing.reminder_count == 2
    assert existing.note is None
    assert sent and "第2次提醒" in sent[0][1]


def test_reminder_agent_escalation_template(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reminder.settings.DINGTALK_ENABLED", True, raising=False)
    sent = []
    agent = ReminderAgent()
    monkeypatch.setattr(agent, "_send_escalation_message", lambda userid, content: sent.append((userid, content)))
    db = _FakeDB(
        schedule_rows=[SimpleNamespace(business_date=date(2026, 4, 4), shift_config_id=1, workshop_id=1, team_id=None)],
        report_rows=[],
        reminder_count=3,
        leader=SimpleNamespace(id=10, name="李四", username="lisi", dingtalk_user_id="u_lisi"),
        admins=[SimpleNamespace(id=1, name="管理员", username="admin", dingtalk_user_id="u_admin", role="admin")],
    )

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert len(decisions) == 1
    assert decisions[0].action.value == "auto_alert"
    assert "【催报升级】铸轧车间 早班 已催报4次未响应" in decisions[0].reason
    assert sent and "负责人：李四" in sent[0][1]
    assert db.added[0].reminder_channel == "dingtalk"


def test_reminder_agent_sends_dingtalk_notification_when_user_is_bound(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reminder.settings.AUTO_PUSH_ENABLED", True)
    monkeypatch.setattr("app.agents.reminder.settings.DINGTALK_ENABLED", True, raising=False)
    calls = []
    monkeypatch.setattr(
        reminder_module,
        "dingtalk_service",
        SimpleNamespace(send_work_notification=lambda userid, content: calls.append((userid, content)) or (True, "dingtalk_stub")),
        raising=False,
    )
    user = SimpleNamespace(username="leader", name="张三", dingtalk_user_id="dt_leader")
    agent = ReminderAgent()

    ok, detail = agent._send_reminder_message(user, "催报内容")

    assert ok is True
    assert detail == "dingtalk_stub"
    assert calls == [("dt_leader", "催报内容")]


def test_reminder_agent_falls_back_to_stdout_when_dingtalk_fails(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reminder.settings.AUTO_PUSH_ENABLED", True)
    monkeypatch.setattr("app.agents.reminder.settings.DINGTALK_ENABLED", True, raising=False)
    monkeypatch.setattr(
        reminder_module,
        "dingtalk_service",
        SimpleNamespace(send_work_notification=lambda _userid, _content: (False, "timeout")),
        raising=False,
    )
    user = SimpleNamespace(username="leader", name="张三", dingtalk_user_id="dt_leader")
    agent = ReminderAgent()

    ok, detail = agent._send_reminder_message(user, "催报内容")

    assert ok is True
    assert detail == "stdout_sink_after_dingtalk_failed:timeout"


def test_reminder_agent_falls_back_to_stdout_sink_without_dingtalk_identity(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reminder.settings.AUTO_PUSH_ENABLED", True)
    monkeypatch.setattr("app.agents.reminder.settings.DINGTALK_ENABLED", True, raising=False)
    user = SimpleNamespace(username="leader", name="张三", dingtalk_user_id=None)
    agent = ReminderAgent()

    ok, detail = agent._send_reminder_message(user, "催报内容")

    assert ok is True
    assert detail == "stdout_sink"


def test_reminder_agent_treats_auto_confirmed_as_ready(monkeypatch) -> None:
    sent = []
    agent = ReminderAgent()
    monkeypatch.setattr(agent, "_send_reminder_message", lambda userid, content: sent.append((userid, content)))
    db = _FakeDB(
        schedule_rows=[SimpleNamespace(business_date=date(2026, 4, 4), shift_config_id=1, workshop_id=1, team_id=None)],
        report_rows=[
            SimpleNamespace(
                business_date=date(2026, 4, 4),
                shift_config_id=1,
                workshop_id=1,
                team_id=None,
                report_status="auto_confirmed",
            )
        ],
        reminder_count=0,
        leader=SimpleNamespace(id=10, name="张三", username="zhangsan", dingtalk_user_id="u_zhangsan"),
        admins=[],
    )

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert decisions == []
    assert db.added == []
    assert sent == []
