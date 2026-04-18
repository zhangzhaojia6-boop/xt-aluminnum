from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import HTTPException

from app.models.imports import ImportBatch, ImportRow
from app.services.yield_matrix_canonical_service import (
    build_yield_matrix_projection,
    load_yield_matrix_snapshots,
    parse_yield_matrix_workbook,
    parse_yield_matrix_sheet,
)


def test_parse_yield_matrix_sheet_extracts_workshops_mp_and_company_total() -> None:
    frame = pd.DataFrame(
        [
            ['4月8日各车间成品率', '1450', '2050', '公司'],
            ['项目', '成品率', '成品率', '成品率'],
            ['成品率', '95.2%', '96.8%', '96.0%'],
            ['M', '88', None, None],
            ['P', '92', None, None],
        ]
    )

    parsed = parse_yield_matrix_sheet('4月8日', frame, source_batch_id=7, year_hint=2026)

    assert parsed.business_date == date(2026, 4, 8)
    assert parsed.delivery_scope == 'factory'
    assert parsed.status == 'success'
    assert parsed.mapped_data['workshop_yields']['cold_roll_1450'] == 95.2
    assert parsed.mapped_data['workshop_yields']['cold_roll_1650_2050'] == 96.8
    assert parsed.mapped_data['company_total_yield'] == 96.0
    assert parsed.mapped_data['mp_targets']['M'] == 88.0
    assert parsed.mapped_data['mp_targets']['P'] == 92.0
    assert parsed.mapped_data['quality_status'] == 'ready'


class FakeQuery:
    def __init__(self, items):
        self._items = items

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

    def query(self, model):
        if model is ImportBatch:
            return FakeQuery(self._batches)
        if model is ImportRow:
            batch_id = self._next_batch_id
            return FakeQuery(self._rows_by_batch[batch_id])
        raise AssertionError(f'unexpected model query: {model}')

    @property
    def _next_batch_id(self):
        batch = self._batches.pop(0)
        self._batches.append(batch)
        return batch.id


def test_build_yield_matrix_projection_aggregates_and_deduplicates_latest_rows() -> None:
    older_batch = SimpleNamespace(id=1)
    newer_batch = SimpleNamespace(id=2)
    rows_by_batch = {
        2: [
            SimpleNamespace(
                mapped_data={
                    'business_date': '2026-04-08',
                    'source_batch_id': 2,
                    'sheet_name': '4月8日',
                    'delivery_scope': 'factory',
                    'workshop_yields': {
                        'cold_roll_1450': 95.2,
                        'cold_roll_1650_2050': 96.8,
                    },
                    'mp_targets': {'M': 88.0, 'P': 92.0},
                    'company_total_yield': 96.0,
                    'lineage_hash': 'new',
                    'quality_status': 'ready',
                }
            )
        ],
        1: [
            SimpleNamespace(
                mapped_data={
                    'business_date': '2026-04-08',
                    'source_batch_id': 1,
                    'sheet_name': '4月8日',
                    'delivery_scope': 'factory',
                    'workshop_yields': {'cold_roll_1450': 91.5},
                    'mp_targets': {'M': 80.0},
                    'company_total_yield': 91.0,
                    'lineage_hash': 'old',
                    'quality_status': 'warning',
                }
            )
        ],
    }
    db = FakeDB([newer_batch, older_batch], rows_by_batch)

    snapshots = load_yield_matrix_snapshots(db, target_date=date(2026, 4, 8))
    projection = build_yield_matrix_projection(db, target_date=date(2026, 4, 8))

    assert len(snapshots) == 1
    assert projection['snapshot_count'] == 1
    assert projection['company_total_yield'] == 96.0
    assert projection['workshop_yields']['cold_roll_1450'] == 95.2
    assert projection['workshop_yields']['cold_roll_1650_2050'] == 96.8
    assert projection['mp_targets']['M'] == 88.0
    assert projection['mp_targets']['P'] == 92.0
    assert projection['quality_status'] == 'ready'


def test_build_yield_matrix_projection_does_not_promote_warning_snapshot_to_formal_truth() -> None:
    batch = SimpleNamespace(id=2)
    rows_by_batch = {
        2: [
            SimpleNamespace(
                mapped_data={
                    'business_date': '2026-04-08',
                    'source_batch_id': 2,
                    'sheet_name': '4月8日',
                    'delivery_scope': 'factory',
                    'workshop_yields': {'cold_roll_1450': 95.2},
                    'mp_targets': {'M': 88.0},
                    'company_total_yield': 96.0,
                    'lineage_hash': 'warning',
                    'quality_status': 'warning',
                }
            )
        ]
    }
    db = FakeDB([batch], rows_by_batch)

    projection = build_yield_matrix_projection(db, target_date=date(2026, 4, 8))

    assert projection['candidate_snapshot_count'] == 1
    assert projection['snapshot_count'] == 0
    assert projection['company_total_yield'] is None
    assert projection['workshop_yields'] == {}
    assert projection['mp_targets'] == {}
    assert projection['quality_status'] == 'warning'


def test_parse_yield_matrix_workbook_blocks_xls_without_xlrd(monkeypatch, tmp_path) -> None:
    workbook = tmp_path / '4月份各车间成品率.xls'
    workbook.write_bytes(b'fake-xls')

    monkeypatch.setattr(
        'app.services.yield_matrix_canonical_service.importlib.import_module',
        lambda name: (_ for _ in ()).throw(ModuleNotFoundError()) if name == 'xlrd' else None,
    )

    with pytest.raises(HTTPException) as exc_info:
        parse_yield_matrix_workbook(workbook)

    assert exc_info.value.status_code == 400
    assert '当前运行环境不支持直接读取历史 .xls' in exc_info.value.detail


def test_build_yield_matrix_projection_prefers_factory_scope_when_multiple_ready_scopes_exist() -> None:
    newer_batch = SimpleNamespace(id=3)
    older_batch = SimpleNamespace(id=2)
    rows_by_batch = {
        3: [
            SimpleNamespace(
                mapped_data={
                    'business_date': '2026-04-08',
                    'source_batch_id': 3,
                    'sheet_name': '4月8日全厂',
                    'delivery_scope': 'factory',
                    'workshop_yields': {'cold_roll_1450': 95.2},
                    'mp_targets': {'M': 88.0, 'P': 92.0},
                    'company_total_yield': 96.0,
                    'lineage_hash': 'factory',
                    'quality_status': 'ready',
                }
            )
        ],
        2: [
            SimpleNamespace(
                mapped_data={
                    'business_date': '2026-04-08',
                    'source_batch_id': 2,
                    'sheet_name': '4月8日1450',
                    'delivery_scope': 'workshop:cold_roll_1450',
                    'workshop_yields': {'cold_roll_1450': 94.0},
                    'mp_targets': {},
                    'company_total_yield': None,
                    'lineage_hash': 'workshop',
                    'quality_status': 'ready',
                }
            )
        ],
    }
    db = FakeDB([newer_batch, older_batch], rows_by_batch)

    projection = build_yield_matrix_projection(db, target_date=date(2026, 4, 8))

    assert projection['primary_delivery_scope'] == 'factory'
    assert projection['selection_status'] == 'prefer_factory_scope'
    assert projection['company_total_yield'] == 96.0
    assert projection['workshop_yields']['cold_roll_1450'] == 95.2


def test_build_yield_matrix_projection_blocks_conflicting_ready_snapshots() -> None:
    newer_batch = SimpleNamespace(id=4)
    older_batch = SimpleNamespace(id=3)
    rows_by_batch = {
        4: [
            SimpleNamespace(
                mapped_data={
                    'business_date': '2026-04-08',
                    'source_batch_id': 4,
                    'sheet_name': '4月8日A',
                    'delivery_scope': 'factory',
                    'workshop_yields': {'cold_roll_1450': 95.2},
                    'mp_targets': {'M': 88.0, 'P': 92.0},
                    'company_total_yield': 96.0,
                    'lineage_hash': 'a',
                    'quality_status': 'ready',
                }
            )
        ],
        3: [
            SimpleNamespace(
                mapped_data={
                    'business_date': '2026-04-08',
                    'source_batch_id': 3,
                    'sheet_name': '4月8日B',
                    'delivery_scope': 'factory',
                    'workshop_yields': {'cold_roll_1450': 94.8},
                    'mp_targets': {'M': 88.0, 'P': 92.0},
                    'company_total_yield': 95.8,
                    'lineage_hash': 'b',
                    'quality_status': 'ready',
                }
            )
        ],
    }
    db = FakeDB([newer_batch, older_batch], rows_by_batch)

    projection = build_yield_matrix_projection(db, target_date=date(2026, 4, 8))

    assert projection['selection_status'] == 'conflicting_ready_snapshots'
    assert projection['quality_status'] == 'warning'
    assert projection['company_total_yield'] is None
    assert projection['workshop_yields'] == {}
