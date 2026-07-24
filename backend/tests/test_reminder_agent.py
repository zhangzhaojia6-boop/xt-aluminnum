from __future__ import annotations

from datetime import date, datetime, time, timezone
from types import SimpleNamespace

from app.agents import reminder as reminder_module
from app.agents.reminder import ReminderAgent
from app.models.agent_communication import ExternalMessageLog


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
            return _FakeQuery(first=self.leader, rows=self.admins)
        return _FakeQuery()

    def add(self, entity):
        self.added.append(entity)


def test_reminder_agent_message_template(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reminder.settings.DINGTALK_ENABLED", True, raising=False)
    sent = []
    agent = ReminderAgent()
    monkeypatch.setattr(
        agent,
        "_send_reminder_message",
        lambda userid, content, **_kwargs: sent.append((userid, content)),
    )
    db = _FakeDB(
        schedule_rows=[SimpleNamespace(business_date=date(2026, 4, 4), shift_config_id=1, workshop_id=1, team_id=None)],
        report_rows=[],
        reminder_count=0,
        leader=SimpleNamespace(id=10, name="张三", username="zhangsan", dingtalk_user_id="u_zhangsan"),
        admins=[],
    )

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert len(decisions) == 1
    assert "铸轧车间早班还没看到数据" in decisions[0].reason
    assert sent == [
        (
            db.leader,
            "铸轧车间早班还没看到数据，方便时从填报端补一下。已经提交的话不用管这条。",
        )
    ]
    assert db.added[0].reminder_channel == "dingtalk"


def test_reminder_agent_does_not_repeat_sent_escalation(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reminder.settings.DINGTALK_ENABLED", False, raising=False)
    sent = []
    existing = SimpleNamespace(
        reminder_status="sent",
        reminder_channel="system",
        reminder_count=1,
        last_reminded_at=datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
        acknowledged_at=None,
        closed_at=None,
        note="old",
    )
    agent = ReminderAgent()
    monkeypatch.setattr(
        agent,
        "_send_reminder_message",
        lambda userid, content, **_kwargs: sent.append((userid, content)),
    )
    db = _FakeDB(
        schedule_rows=[SimpleNamespace(business_date=date(2026, 4, 4), shift_config_id=1, workshop_id=1, team_id=None)],
        report_rows=[],
        reminder_count=1,
        leader=SimpleNamespace(id=10, name="张三", username="zhangsan", dingtalk_user_id=None),
        admins=[],
        existing_reminder=existing,
    )

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert decisions == []
    assert db.added == []
    assert existing.reminder_status == "sent"
    assert existing.reminder_count == 1
    assert sent == []


def test_reminder_agent_escalation_template(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reminder.settings.DINGTALK_ENABLED", True, raising=False)
    sent = []
    agent = ReminderAgent()
    monkeypatch.setattr(
        agent,
        "_send_escalation_message",
        lambda userid, content, **_kwargs: sent.append((userid, content)),
    )
    db = _FakeDB(
        schedule_rows=[SimpleNamespace(business_date=date(2026, 4, 4), shift_config_id=1, workshop_id=1, team_id=None)],
        report_rows=[],
        reminder_count=1,
        leader=SimpleNamespace(id=10, name="李四", username="lisi", dingtalk_user_id="u_lisi"),
        admins=[SimpleNamespace(id=1, name="管理员", username="admin", dingtalk_user_id="u_admin", role="admin")],
    )

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert len(decisions) == 1
    assert decisions[0].action.value == "auto_alert"
    assert "铸轧车间早班提醒后仍未补齐" in decisions[0].reason
    assert sent == [
        (
            db.admins[0],
            "铸轧车间早班（李四）提醒后仍未补齐，麻烦关注一下。有新进展我再更新。",
        )
    ]
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


def test_reminder_agent_uses_readable_reason_when_dingtalk_returns_structured_failure(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reminder.settings.AUTO_PUSH_ENABLED", True)
    monkeypatch.setattr("app.agents.reminder.settings.DINGTALK_ENABLED", True, raising=False)
    monkeypatch.setattr(
        reminder_module,
        "dingtalk_service",
        SimpleNamespace(
            send_work_notification=lambda _userid, _content: (
                False,
                {
                    "detail": "invalid userid",
                    "provider_message_id": "0",
                    "response_payload": {"errcode": 33012, "errmsg": "invalid userid"},
                },
            )
        ),
        raising=False,
    )
    user = SimpleNamespace(username="leader", name="张三", dingtalk_user_id="dt_leader")
    agent = ReminderAgent()

    ok, detail = agent._send_reminder_message(user, "催报内容")

    assert ok is True
    assert detail == "stdout_sink_after_dingtalk_failed:invalid userid"
    assert "response_payload" not in detail


def test_reminder_agent_logs_dingtalk_work_notification_when_db_is_available(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.reminder.settings.AUTO_PUSH_ENABLED", True)
    monkeypatch.setattr("app.agents.reminder.settings.DINGTALK_ENABLED", True, raising=False)
    monkeypatch.setattr(
        reminder_module,
        "dingtalk_service",
        SimpleNamespace(
            send_work_notification=lambda _userid, _content: (
                False,
                {
                    "detail": "invalid userid",
                    "provider_message_id": "0",
                    "response_payload": {"errcode": 33012, "errmsg": "invalid userid"},
                },
            )
        ),
        raising=False,
    )
    db = SimpleNamespace(added=[], add=lambda row: db.added.append(row))
    user = SimpleNamespace(username="leader", name="张三", dingtalk_user_id="dt_leader")
    agent = ReminderAgent()

    ok, detail = agent._send_reminder_message(user, "催报内容", db=db)

    assert ok is True
    assert detail == "stdout_sink_after_dingtalk_failed:invalid userid"
    logs = [row for row in db.added if isinstance(row, ExternalMessageLog)]
    assert len(logs) == 1
    assert logs[0].channel_type == "dingtalk_work_notification"
    assert logs[0].channel_key == "dt_leader"
    assert logs[0].status == "failed"
    assert logs[0].detail == "invalid userid"
    assert logs[0].provider_message_id == "0"
    assert logs[0].response_payload == {"errcode": 33012, "errmsg": "invalid userid"}


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
    monkeypatch.setattr(
        agent,
        "_send_reminder_message",
        lambda userid, content, **_kwargs: sent.append((userid, content)),
    )
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


def test_reminder_agent_skips_acknowledged_item(monkeypatch) -> None:
    sent = []
    acknowledged = SimpleNamespace(
        reminder_status="acknowledged",
        reminder_count=1,
        last_reminded_at=datetime(2026, 4, 4, 8, 0, tzinfo=timezone.utc),
        acknowledged_at=datetime(2026, 4, 4, 8, 5, tzinfo=timezone.utc),
        closed_at=None,
    )
    agent = ReminderAgent()
    monkeypatch.setattr(
        agent,
        "_send_reminder_message",
        lambda userid, content, **_kwargs: sent.append((userid, content)),
    )
    db = _FakeDB(
        schedule_rows=[SimpleNamespace(business_date=date(2026, 4, 4), shift_config_id=1, workshop_id=1, team_id=None)],
        report_rows=[],
        reminder_count=1,
        leader=SimpleNamespace(id=10, name="张三", username="zhangsan", dingtalk_user_id="u_zhangsan"),
        admins=[],
        existing_reminder=acknowledged,
    )

    assert agent.execute(db=db, target_date=date(2026, 4, 4)) == []
    assert sent == []


def test_reminder_agent_combines_multiple_items_for_same_recipient(monkeypatch) -> None:
    sent = []
    agent = ReminderAgent()
    monkeypatch.setattr(
        agent,
        "_send_reminder_message",
        lambda userid, content, **_kwargs: sent.append((userid, content)),
    )
    leader = SimpleNamespace(id=10, name="张三", username="zhangsan", dingtalk_user_id="u_zhangsan")
    db = _FakeDB(
        schedule_rows=[
            SimpleNamespace(business_date=date(2026, 4, 4), shift_config_id=1, workshop_id=1, team_id=None),
            SimpleNamespace(business_date=date(2026, 4, 4), shift_config_id=1, workshop_id=2, team_id=None),
        ],
        report_rows=[],
        reminder_count=0,
        leader=leader,
        admins=[],
    )

    decisions = agent.execute(db=db, target_date=date(2026, 4, 4))

    assert len(decisions) == 2
    assert len(sent) == 1
    assert sent[0][0] is leader
    assert sent[0][1].startswith("今天还有2项没看到数据：")
    assert "铸轧车间早班" in sent[0][1]
    assert "车间2早班" in sent[0][1]
