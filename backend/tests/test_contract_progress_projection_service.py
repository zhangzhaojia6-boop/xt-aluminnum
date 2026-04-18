from datetime import UTC, date, datetime
from types import SimpleNamespace

from app.services.contract_progress_projection_service import build_contract_progress_projection


class _FakeQuery:
    def __init__(self, value):
        self._value = value

    def all(self):
        return self._value


class _FakeDB:
    def __init__(self, snapshots, work_orders, entries):
        self._snapshots = snapshots
        self._work_orders = work_orders
        self._entries = entries

    def query(self, model):
        if model.__name__ == 'MesCoilSnapshot':
            return _FakeQuery(self._snapshots)
        if model.__name__ == 'WorkOrder':
            return _FakeQuery(self._work_orders)
        if model.__name__ == 'WorkOrderEntry':
            return _FakeQuery(self._entries)
        raise AssertionError(model)


def test_build_contract_progress_projection_groups_contracts():
    snapshots = [
        SimpleNamespace(
            coil_id='coil-1',
            tracking_card_no='RA260001',
            contract_no='HT-1',
            workshop_code='ZR2',
            process_code='casting',
            status='in_progress',
            updated_from_mes_at=datetime(2026, 4, 11, 2, 0, tzinfo=UTC),
            event_time=datetime(2026, 4, 11, 2, 0, tzinfo=UTC),
        ),
        SimpleNamespace(
            coil_id='coil-2',
            tracking_card_no='RA260002',
            contract_no='HT-1',
            workshop_code='ZR3',
            process_code='casting',
            status='in_progress',
            updated_from_mes_at=datetime(2026, 4, 10, 2, 0, tzinfo=UTC),
            event_time=datetime(2026, 4, 10, 2, 0, tzinfo=UTC),
        ),
    ]
    work_orders = [
        SimpleNamespace(id=1, tracking_card_no='RA260001', contract_weight=1000.0),
        SimpleNamespace(id=2, tracking_card_no='RA260002', contract_weight=800.0),
    ]
    entries = [
        SimpleNamespace(work_order_id=1, verified_output_weight=None, output_weight=980.0, approved_at=None, verified_at=None, submitted_at=datetime(2026, 4, 11, 2, 0, tzinfo=UTC), updated_at=datetime(2026, 4, 11, 2, 0, tzinfo=UTC), created_at=datetime(2026, 4, 11, 2, 0, tzinfo=UTC)),
        SimpleNamespace(work_order_id=2, verified_output_weight=None, output_weight=760.0, approved_at=None, verified_at=None, submitted_at=datetime(2026, 4, 10, 2, 0, tzinfo=UTC), updated_at=datetime(2026, 4, 10, 2, 0, tzinfo=UTC), created_at=datetime(2026, 4, 10, 2, 0, tzinfo=UTC)),
    ]
    db = _FakeDB(snapshots, work_orders, entries)

    payload = build_contract_progress_projection(db, target_date=date(2026, 4, 11))

    assert payload['active_contract_count'] == 1
    assert payload['stalled_contract_count'] == 1
    assert payload['active_coil_count'] == 2
    assert payload['today_advanced_weight'] == 980.0
    assert payload['contracts'][0]['contract_no'] == 'HT-1'

