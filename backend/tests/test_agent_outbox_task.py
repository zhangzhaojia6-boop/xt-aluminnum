from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.tasks import agent_outbox as task_module


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_dispatch_due_agent_outbox_messages_commits(monkeypatch) -> None:
    session = FakeSession()

    def fake_dispatch(db):
        assert db is session
        return [SimpleNamespace(), SimpleNamespace()]

    monkeypatch.setattr(task_module, 'get_sessionmaker', lambda: lambda: session)
    monkeypatch.setattr(
        task_module.agent_communication_service,
        'dispatch_due_outbox_messages',
        fake_dispatch,
    )

    result = task_module.dispatch_due_agent_outbox_messages()

    assert result == {'status': 'ok', 'total': 2}
    assert session.commits == 1
    assert session.rollbacks == 0


def test_dispatch_due_agent_outbox_messages_rolls_back_on_error(monkeypatch) -> None:
    session = FakeSession()

    def fake_dispatch(_db):
        raise RuntimeError('dispatch failed')

    monkeypatch.setattr(task_module, 'get_sessionmaker', lambda: lambda: session)
    monkeypatch.setattr(
        task_module.agent_communication_service,
        'dispatch_due_outbox_messages',
        fake_dispatch,
    )

    with pytest.raises(RuntimeError, match='dispatch failed'):
        task_module.dispatch_due_agent_outbox_messages()

    assert session.commits == 0
    assert session.rollbacks == 1
