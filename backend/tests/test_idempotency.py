from datetime import timedelta

from app.core.idempotency import InMemoryIdempotencyStore


def test_in_memory_idempotency_store_returns_active_record() -> None:
    store = InMemoryIdempotencyStore(default_ttl_seconds=60)
    store.put(scope='entry-create:1', key='abc', fingerprint='fp-1', value={'entry_id': 9})

    record = store.get(scope='entry-create:1', key='abc')

    assert record is not None
    assert record.value == {'entry_id': 9}
    assert record.fingerprint == 'fp-1'


def test_in_memory_idempotency_store_drops_expired_record() -> None:
    store = InMemoryIdempotencyStore(default_ttl_seconds=60)
    store.put(scope='entry-create:1', key='abc', fingerprint='fp-1', value={'entry_id': 9})

    expired_at = store._now() + timedelta(seconds=61)
    record = store.get(scope='entry-create:1', key='abc', now=expired_at)

    assert record is None
