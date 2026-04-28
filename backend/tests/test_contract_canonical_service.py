from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd

from app.models.imports import ImportBatch, ImportRow
from app.services.contract_canonical_service import build_contract_projection, load_contract_snapshots, parse_contract_sheet


def test_parse_contract_sheet_extracts_metrics_date_and_scope() -> None:
    frame = pd.DataFrame(
        [
            ['河南鑫泰合同报表', None],
            ['4月8日 铸锭合同', None],
            ['当日合同', '1,234.5'],
            ['月累计合同', '4,321'],
            ['当日投料', '888'],
            ['坯总量', '999'],
        ]
    )

    parsed = parse_contract_sheet('4月8日 铸锭', frame, source_batch_id=9, year_hint=2026)

    assert parsed.business_date == date(2026, 4, 8)
    assert parsed.delivery_scope == 'workshop:foundry'
    assert parsed.status == 'success'
    assert parsed.mapped_data['daily_contract_weight'] == 1234.5
    assert parsed.mapped_data['month_to_date_contract_weight'] == 4321.0
    assert parsed.mapped_data['daily_input_weight'] == 888.0
    assert parsed.mapped_data['month_to_date_input_weight'] == 999.0
    assert parsed.mapped_data['quality_status'] == 'ready'
    assert isinstance(parsed.mapped_data['lineage_hash'], str)
    assert len(parsed.mapped_data['lineage_hash']) == 64


class FakeQuery:
    def __init__(self, items):
        self._items = items

    def join(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._items)


class FakeDB:
    def __init__(self, batches, rows_by_batch):
        self._batches = batches
        self._rows_by_batch = rows_by_batch

    def query(self, *models):
        if models == (ImportBatch,):
            return FakeQuery(self._batches)
        if models == (ImportRow,):
            batch_id = self._next_batch_id
            return FakeQuery(self._rows_by_batch[batch_id])
        return FakeQuery([])

    @property
    def _next_batch_id(self):
        batch = self._batches.pop(0)
        self._batches.append(batch)
        return batch.id


def test_build_contract_projection_aggregates_and_deduplicates_latest_rows() -> None:
    older_batch = SimpleNamespace(id=1)
    newer_batch = SimpleNamespace(id=2)
    rows_by_batch = {
        2: [
            SimpleNamespace(
                mapped_data={
                    'business_date': '2026-04-08',
                    'source_batch_id': 2,
                    'sheet_name': '4月8日 铸锭',
                    'delivery_scope': 'workshop:foundry',
                    'daily_contract_weight': 120.0,
                    'month_to_date_contract_weight': 320.0,
                    'daily_input_weight': 95.0,
                    'month_to_date_input_weight': 205.0,
                    'lineage_hash': 'new',
                    'quality_status': 'ready',
                }
            ),
            SimpleNamespace(
                mapped_data={
                    'business_date': '2026-04-08',
                    'source_batch_id': 2,
                    'sheet_name': '4月8日 冷轧',
                    'delivery_scope': 'workshop:cold_roll',
                    'daily_contract_weight': 80.0,
                    'month_to_date_contract_weight': 280.0,
                    'daily_input_weight': 70.0,
                    'month_to_date_input_weight': 170.0,
                    'lineage_hash': 'cold',
                    'quality_status': 'warning',
                }
            ),
        ],
        1: [
            SimpleNamespace(
                mapped_data={
                    'business_date': '2026-04-08',
                    'source_batch_id': 1,
                    'sheet_name': '4月8日 铸锭',
                    'delivery_scope': 'workshop:foundry',
                    'daily_contract_weight': 100.0,
                    'month_to_date_contract_weight': 300.0,
                    'daily_input_weight': 90.0,
                    'month_to_date_input_weight': 200.0,
                    'lineage_hash': 'old',
                    'quality_status': 'warning',
                }
            ),
        ],
    }
    db = FakeDB([newer_batch, older_batch], rows_by_batch)

    snapshots = load_contract_snapshots(db, target_date=date(2026, 4, 8))
    projection = build_contract_projection(db, target_date=date(2026, 4, 8))

    assert len(snapshots) == 2
    assert projection['snapshot_count'] == 2
    assert projection['daily_contract_weight'] == 200.0
    assert projection['month_to_date_contract_weight'] == 600.0
    assert projection['daily_input_weight'] == 165.0
    assert projection['month_to_date_input_weight'] == 375.0
    assert projection['delivery_scopes'] == ['workshop:cold_roll', 'workshop:foundry']
    assert projection['quality_status'] == 'warning'
    assert [item['sheet_name'] for item in projection['items']] == ['4月8日 冷轧', '4月8日 铸锭']
