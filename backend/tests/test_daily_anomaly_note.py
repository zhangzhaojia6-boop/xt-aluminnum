from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base
from app.models.reports import DailyFactCorrection
from app.models.system import User
from app.services.report import daily_anomaly_note_service as service

TODAY = date(2026, 11, 10)


@pytest.fixture()
def db_session(monkeypatch) -> Iterator[Session]:
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, future=True)()
    session.add_all([
        User(id=983, username='zhang', password_hash='x', name='张兆嘉', role='admin'),
        User(id=1, username='other', password_hash='x', name='其他管理员', role='admin'),
    ])
    session.commit()
    monkeypatch.setattr(service, 'current_business_date', lambda: TODAY)
    monkeypatch.setattr(service.settings, 'ANOMALY_NOTE_AUTHOR_USER_IDS', '983')
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _user(db: Session, user_id: int) -> User:
    return db.get(User, user_id)


def test_author_saves_and_everyone_reads_the_latest_note(db_session: Session) -> None:
    author = _user(db_session, 983)
    service.save_anomaly_note(db_session, user=author, business_date=TODAY, content='1650 停机检修 4 小时')
    saved = service.save_anomaly_note(db_session, user=author, business_date=TODAY, content='  1650 停机检修 5 小时  ')

    assert saved['content'] == '1650 停机检修 5 小时'
    assert saved['author_name'] == '张兆嘉'
    assert saved['can_edit'] is True
    other_view = service.read_anomaly_note(db_session, user=_user(db_session, 1), business_date=TODAY)
    assert other_view['content'] == '1650 停机检修 5 小时'
    assert other_view['can_edit'] is False

    rows = db_session.query(DailyFactCorrection).order_by(DailyFactCorrection.id).all()
    assert [row.status for row in rows] == ['revoked', 'active']
    assert rows[-1].field_name == 'anomaly_explanation_daily'
    assert rows[-1].actor_user_id == 983
    assert rows[-1].trace_id.startswith('anomaly-note:2026-11-10:')


def test_only_the_author_can_write_today_or_yesterday(db_session: Session) -> None:
    with pytest.raises(HTTPException) as other:
        service.save_anomaly_note(db_session, user=_user(db_session, 1), business_date=TODAY, content='x')
    assert other.value.status_code == 403

    author = _user(db_session, 983)
    service.save_anomaly_note(db_session, user=author, business_date=date(2026, 11, 9), content='昨天的说明')
    with pytest.raises(HTTPException) as old:
        service.save_anomaly_note(db_session, user=author, business_date=date(2026, 11, 8), content='x')
    assert old.value.status_code == 403
    assert service.read_anomaly_note(db_session, user=author, business_date=date(2026, 11, 8))['can_edit'] is False


@pytest.mark.parametrize('content', ['', '   ', 'x' * 2001])
def test_empty_or_too_long_notes_are_rejected(db_session: Session, content: str) -> None:
    with pytest.raises(HTTPException) as error:
        service.save_anomaly_note(db_session, user=_user(db_session, 983), business_date=TODAY, content=content)
    assert error.value.status_code == 422
    assert db_session.query(DailyFactCorrection).count() == 0


def test_no_note_reads_as_empty(db_session: Session) -> None:
    view = service.read_anomaly_note(db_session, user=_user(db_session, 1), business_date=TODAY)

    assert view == {
        'business_date': '2026-11-10',
        'content': '',
        'author_name': None,
        'updated_at': None,
        'can_edit': False,
    }
