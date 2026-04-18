from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from fastapi import UploadFile

from app.services.contract_canonical_service import ParsedContractSheet, contract_row_summary_fields
from app.services.import_service import store_import_file


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


def test_store_import_file_contract_report_uses_parsed_rows(monkeypatch, tmp_path) -> None:
    upload = UploadFile(filename='河南鑫泰合同报表.xlsx', file=BytesIO(b'fake-workbook'))
    stored_path = tmp_path / 'stored.xlsx'
    stored_path.write_bytes(b'fake-workbook')

    monkeypatch.setattr(
        'app.services.import_service._save_upload_file',
        lambda _upload: (stored_path, b'fake-workbook', 'stored.xlsx'),
    )
    monkeypatch.setattr(
        'app.services.import_service.parse_contract_workbook',
        lambda *_args, **_kwargs: [
            ParsedContractSheet(
                sheet_name='4月8日 铸锭',
                business_date=None,
                delivery_scope='workshop:foundry',
                mapped_data={
                    'business_date': '2026-04-08',
                    'source_batch_id': 1,
                    'sheet_name': '4月8日 铸锭',
                    'delivery_scope': 'workshop:foundry',
                    'daily_contract_weight': 12.0,
                    'month_to_date_contract_weight': 34.0,
                    'daily_input_weight': 10.0,
                    'month_to_date_input_weight': 20.0,
                    'lineage_hash': 'hash-1',
                    'quality_status': 'ready',
                },
                raw_data={'sheet_name': '4月8日 铸锭'},
                status='success',
                error_msg=None,
            ),
            ParsedContractSheet(
                sheet_name='4月8日 冷轧',
                business_date=None,
                delivery_scope='workshop:cold_roll',
                mapped_data={
                    'business_date': '2026-04-08',
                    'source_batch_id': 1,
                    'sheet_name': '4月8日 冷轧',
                    'delivery_scope': 'workshop:cold_roll',
                    'daily_contract_weight': None,
                    'month_to_date_contract_weight': None,
                    'daily_input_weight': None,
                    'month_to_date_input_weight': None,
                    'lineage_hash': 'hash-2',
                    'quality_status': 'blocked',
                },
                raw_data={'sheet_name': '4月8日 冷轧'},
                status='failed',
                error_msg='合同表未识别出足够字段，请检查表头或样本格式。',
            ),
            ],
        )

    batch = SimpleNamespace(
        id=1,
        import_type='contract_report',
        batch_no='IMP-CONTRACT',
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
    result = store_import_file(upload, db=db, current_user=None, import_type='contract_report')
    rows = sorted(db.rows, key=lambda item: item.row_number)

    assert result.summary['columns'] == contract_row_summary_fields()
    assert result.summary['total_rows'] == 2
    assert result.summary['success_rows'] == 1
    assert result.summary['failed_rows'] == 1
    assert batch.import_type == 'contract_report'
    assert batch.error_summary == '合同表未识别出足够字段，请检查表头或样本格式。'
    assert [row.status for row in rows] == ['success', 'failed']
    assert rows[0].mapped_data['delivery_scope'] == 'workshop:foundry'
    assert rows[1].error_msg == '合同表未识别出足够字段，请检查表头或样本格式。'
