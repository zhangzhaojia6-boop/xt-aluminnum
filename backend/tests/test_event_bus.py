import asyncio
import time

from app.core.event_bus import InMemoryEventBus


def test_in_memory_event_bus_async_listen_wakes_immediately_on_publish() -> None:
    bus = InMemoryEventBus()

    async def scenario():
        listener = asyncio.create_task(bus.listen(after_event_id=0, limit=10, timeout=1.0))
        await asyncio.sleep(0.05)
        started = time.perf_counter()
        bus.publish('entry_submitted', {'tracking_card_no': 'RA260001'})
        events = await listener
        return time.perf_counter() - started, events

    elapsed, events = asyncio.run(scenario())

    assert elapsed < 0.2
    assert [item['event_type'] for item in events] == ['entry_submitted']
    assert events[0]['payload']['tracking_card_no'] == 'RA260001'


def test_in_memory_event_bus_async_listen_times_out_with_empty_list() -> None:
    bus = InMemoryEventBus()

    async def scenario():
        return await bus.listen(after_event_id=0, limit=10, timeout=0.05)

    events = asyncio.run(scenario())

    assert events == []
