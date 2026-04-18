from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from fastapi import UploadFile

from app.services.import_service import store_import_file
from app.services.yield_matrix_canonical_service import ParsedYieldMatrixSheet, yield_matrix_row_summary_fields


class FakeDB:
    def __init__(self):
        self.rows = []

    def add(self, item):
        if hasattr(item, 'row_number'):
            self.rows.append(item)

    def commit(self):
        return None

    def refresh(self, _item):
        return None


def test_store_import_file_yield_matrix_uses_parsed_rows(monkeypatch, tmp_path) -> None:
    upload = UploadFile(filename='4月份各车间成品率.xlsx', file=BytesIO(b'fake-workbook'))
    stored_path = tmp_path / 'yield-matrix.xlsx'
    stored_path.write_bytes(b'fake-workbook')

    monkeypatch.setattr(
        'app.services.import_service._save_upload_file',
        lambda _upload: (stored_path, b'fake-workbook', 'yield-matrix.xlsx'),
    )
    monkeypatch.setattr(
        'app.services.import_service.parse_yield_matrix_workbook',
        lambda *_args, **_kwargs: [
            ParsedYieldMatrixSheet(
                sheet_name='4月8日',
                business_date=None,
                delivery_scope='factory',
                mapped_data={
                    'business_date': '2026-04-08',
                    'source_batch_id': 1,
                    'sheet_name': '4月8日',
                    'delivery_scope': 'factory',
                    'workshop_yields': {'cold_roll_1450': 95.2},
                    'mp_targets': {'M': 88.0, 'P': 92.0},
                    'company_total_yield': 96.0,
                    'lineage_hash': 'hash-1',
                    'quality_status': 'ready',
                },
                raw_data={'sheet_name': '4月8日'},
                status='success',
                error_msg=None,
            ),
            ParsedYieldMatrixSheet(
                sheet_name='4月9日',
                business_date=None,
                delivery_scope='factory',
                mapped_data={
                    'business_date': '2026-04-09',
                    'source_batch_id': 1,
                    'sheet_name': '4月9日',
                    'delivery_scope': 'factory',
                    'workshop_yields': {},
                    'mp_targets': {},
                    'company_total_yield': None,
                    'lineage_hash': 'hash-2',
                    'quality_status': 'blocked',
                },
                raw_data={'sheet_name': '4月9日'},
                status='failed',
                error_msg='成品率矩阵未识别出足够字段，请检查表头、样本或多级列结构。',
            ),
        ],
    )

    batch = SimpleNamespace(
        id=1,
        import_type='yield_rate_matrix',
        batch_no='IMP-YIELD',
        total_rows=0,
        success_rows=0,
        failed_rows=0,
        skipped_rows=0,
        error_summary=None,
        created_at=SimpleNamespace(year=2026),
    )
    monkeypatch.setattr('app.services.import_service._create_batch', lambda *args, **kwargs: batch)
    monkeypatch.setattr(
        'app.services.import_service._finalize_batch',
        lambda _db, *, batch, total_rows, success_rows, failed_rows, skipped_rows, error_summary: (
            setattr(batch, 'total_rows', total_rows),
            setattr(batch, 'success_rows', success_rows),
            setattr(batch, 'failed_rows', failed_rows),
            setattr(batch, 'skipped_rows', skipped_rows),
            setattr(batch, 'error_summary', error_summary),
        ),
    )

    db = FakeDB()
    result = store_import_file(upload, db=db, current_user=None, import_type='yield_rate_matrix')
    rows = sorted(db.rows, key=lambda item: item.row_number)

    assert result.summary['columns'] == yield_matrix_row_summary_fields()
    assert result.summary['total_rows'] == 2
    assert result.summary['success_rows'] == 1
    assert result.summary['failed_rows'] == 1
    assert batch.import_type == 'yield_rate_matrix'
    assert batch.error_summary == '成品率矩阵未识别出足够字段，请检查表头、样本或多级列结构。'
    assert [row.status for row in rows] == ['success', 'failed']
    assert rows[0].mapped_data['company_total_yield'] == 96.0
