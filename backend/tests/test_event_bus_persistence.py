import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.event_bus import DatabaseEventBus
from app.models.production import RealtimeEvent


def build_sessionmaker(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'realtime-events.db'}", future=True)
    RealtimeEvent.__table__.create(engine)
    return sessionmaker(bind=engine, future=True)


def test_database_event_bus_shares_events_across_instances(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    publisher = DatabaseEventBus(sessionmaker_factory=lambda: session_factory, poll_interval=0.01)
    listener = DatabaseEventBus(sessionmaker_factory=lambda: session_factory, poll_interval=0.01)

    published = publisher.publish(
        'entry_submitted',
        {
            'tracking_card_no': 'RA260001',
            'workshop_id': 2,
            'machine': '1#',
        },
    )
    events = asyncio.run(listener.listen(after_event_id=0, limit=10, timeout=0))

    assert published is not None
    assert published['id'] == 1
    assert events == [
        {
            'id': 1,
            'event_type': 'entry_submitted',
            'payload': {
                'tracking_card_no': 'RA260001',
                'workshop_id': 2,
                'machine': '1#',
            },
            'workshop_id': 2,
            'created_at': published['created_at'],
        }
    ]


def test_database_event_bus_listen_times_out_with_empty_list(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    bus = DatabaseEventBus(sessionmaker_factory=lambda: session_factory, poll_interval=0.01)

    events = asyncio.run(bus.listen(after_event_id=0, limit=10, timeout=0.03))

    assert events == []


def test_database_event_bus_cleanup_removes_events_older_than_48_hours(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    bus = DatabaseEventBus(sessionmaker_factory=lambda: session_factory, poll_interval=0.01)
    now = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)

    with session_factory() as db:
        db.add_all(
            [
                RealtimeEvent(
                    event_type='entry_submitted',
                    payload={'tracking_card_no': 'OLD1'},
                    workshop_id=1,
                    created_at=now - timedelta(hours=49),
                ),
                RealtimeEvent(
                    event_type='entry_submitted',
                    payload={'tracking_card_no': 'NEW1'},
                    workshop_id=1,
                    created_at=now - timedelta(hours=2),
                ),
            ]
        )
        db.commit()

    removed = bus.cleanup(max_age_hours=48, now=now)

    with session_factory() as db:
        remaining = db.execute(select(RealtimeEvent).order_by(RealtimeEvent.id.asc())).scalars().all()

    assert removed == 1
    assert [item.payload['tracking_card_no'] for item in remaining] == ['NEW1']


def test_database_event_bus_publish_failure_returns_none_without_raising() -> None:
    class BrokenSession:
        def __init__(self):
            self.rolled_back = False
            self.closed = False

        def add(self, _entity):
            return None

        def commit(self):
            raise RuntimeError('db unavailable')

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    broken = BrokenSession()
    bus = DatabaseEventBus(sessionmaker_factory=lambda: (lambda: broken), poll_interval=0.01)

    published = bus.publish('entry_submitted', {'tracking_card_no': 'RA260001', 'workshop_id': 2})

    assert published is None
    assert broken.rolled_back is True
    assert broken.closed is True
