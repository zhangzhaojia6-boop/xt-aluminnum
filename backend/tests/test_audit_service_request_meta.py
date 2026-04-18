from types import SimpleNamespace
from datetime import datetime, timezone

from app.services.audit_service import record_entity_change


class _DummyDB:
    def __init__(self):
        self.added = []

    def add(self, entity):
        self.added.append(entity)

    def flush(self):
        return None


def test_record_entity_change_stores_user_agent_and_ip_address() -> None:
    db = _DummyDB()

    record_entity_change(
        db,
        user=SimpleNamespace(id=7, name='审计员'),
        module='work_orders',
        entity_type='work_order_entries',
        entity_id=9,
        action='update',
        old_value={'input_weight': 9500},
        new_value={'input_weight': 9520},
        ip_address='10.0.0.9',
        user_agent='pytest-audit',
        auto_commit=False,
    )

    assert db.added[0].ip_address == '10.0.0.9'
    assert db.added[0].user_agent == 'pytest-audit'


def test_record_entity_change_normalizes_datetime_payload_for_json_fields() -> None:
    db = _DummyDB()
    now = datetime(2026, 4, 1, 9, 45, tzinfo=timezone.utc)

    record_entity_change(
        db,
        user=SimpleNamespace(id=1, name='管理员'),
        module='users',
        entity_type='users',
        entity_id=1,
        action='update',
        old_value={'last_login': now},
        new_value={'last_login': now},
        auto_commit=False,
    )

    assert db.added[0].old_value['last_login'] == now.isoformat()
    assert db.added[0].new_value['last_login'] == now.isoformat()
