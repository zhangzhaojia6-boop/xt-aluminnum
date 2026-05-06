from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from fastapi import UploadFile

from app.services.daily_production_canonical_service import (
    ParsedDailyProductionSheet,
    daily_production_row_summary_fields,
)
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


def test_store_import_file_daily_production_report_uses_parsed_rows(monkeypatch, tmp_path) -> None:
    upload = UploadFile(filename='鑫泰每日产量5月.xls', file=BytesIO(b'fake-workbook'))
    stored_path = tmp_path / 'daily-production.xls'
    stored_path.write_bytes(b'fake-workbook')

    monkeypatch.setattr(
        'app.services.import_service._save_upload_file',
        lambda _upload: (stored_path, b'fake-workbook', 'daily-production.xls'),
    )
    monkeypatch.setattr(
        'app.services.import_service.parse_daily_production_workbook',
        lambda *_args, **_kwargs: [
            ParsedDailyProductionSheet(
                sheet_name='综合报表',
                business_date=None,
                mapped_data={
                    'business_date': '2026-05-03',
                    'source_batch_id': 1,
                    'sheet_name': '综合报表',
                    'source_unit': 't',
                    'row_count': 16,
                    'daily_input_tons': 1985.674,
                    'month_to_date_input_tons': 11325.379,
                    'daily_output_tons': 1935.649,
                    'month_to_date_output_tons': 11258.775,
                    'daily_scrap_tons': 50.025,
                    'month_to_date_scrap_tons': 66.604,
                    'lineage_hash': 'hash-ready',
                    'quality_status': 'ready',
                    'issues': [],
                },
                raw_data={'sheet_name': '综合报表'},
                status='success',
                error_msg=None,
            ),
            ParsedDailyProductionSheet(
                sheet_name='综合报表-异常',
                business_date=None,
                mapped_data={
                    'business_date': '2026-05-04',
                    'source_batch_id': 1,
                    'sheet_name': '综合报表-异常',
                    'source_unit': 't',
                    'row_count': 1,
                    'daily_input_tons': 149510.0,
                    'month_to_date_input_tons': 149510.0,
                    'daily_output_tons': 120460.0,
                    'month_to_date_output_tons': 120460.0,
                    'daily_scrap_tons': 18050.0,
                    'month_to_date_scrap_tons': 18050.0,
                    'lineage_hash': 'hash-warning',
                    'quality_status': 'warning',
                    'issues': [
                        {
                            'code': 'suspicious_daily_output_tons',
                            'message': '每日产量日报值超过 10000t，请核对是否把 kg 当作 t。',
                            'row_index': 3,
                            'workshop_label': '冷轧',
                            'project_label': '2050',
                            'value': 120460.0,
                        }
                    ],
                },
                raw_data={'sheet_name': '综合报表-异常'},
                status='success',
                error_msg=None,
            ),
            ParsedDailyProductionSheet(
                sheet_name='综合报表-缺日期',
                business_date=None,
                mapped_data={
                    'business_date': None,
                    'source_batch_id': 1,
                    'sheet_name': '综合报表-缺日期',
                    'source_unit': 't',
                    'row_count': 0,
                    'daily_input_tons': 0.0,
                    'month_to_date_input_tons': 0.0,
                    'daily_output_tons': 0.0,
                    'month_to_date_output_tons': 0.0,
                    'daily_scrap_tons': 0.0,
                    'month_to_date_scrap_tons': 0.0,
                    'lineage_hash': 'hash-blocked',
                    'quality_status': 'blocked',
                    'issues': [],
                },
                raw_data={'sheet_name': '综合报表-缺日期'},
                status='failed',
                error_msg='每日产量表未识别出日期或有效生产行，请检查表头和综合报表格式。',
            ),
        ],
    )

    batch = SimpleNamespace(
        id=1,
        import_type='daily_production_report',
        batch_no='IMP-DAILY',
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
    result = store_import_file(upload, db=db, current_user=None, import_type='daily_production_report')
    rows = sorted(db.rows, key=lambda item: item.row_number)

    assert result.summary['columns'] == daily_production_row_summary_fields()
    assert result.summary['total_rows'] == 3
    assert result.summary['success_rows'] == 2
    assert result.summary['failed_rows'] == 1
    assert batch.import_type == 'daily_production_report'
    assert batch.error_summary == '每日产量表未识别出日期或有效生产行，请检查表头和综合报表格式。'
    assert [row.status for row in rows] == ['success', 'success', 'failed']
    assert rows[0].mapped_data['source_unit'] == 't'
    assert rows[0].mapped_data['daily_output_tons'] == 1935.649
    assert rows[1].mapped_data['quality_status'] == 'warning'
    assert rows[1].mapped_data['issues'][0]['code'] == 'suspicious_daily_output_tons'
    assert rows[2].error_msg == '每日产量表未识别出日期或有效生产行，请检查表头和综合报表格式。'


def test_store_import_file_daily_production_report_fails_when_no_summary_sheet(monkeypatch, tmp_path) -> None:
    upload = UploadFile(filename='鑫泰每日产量5月.xls', file=BytesIO(b'fake-workbook'))
    stored_path = tmp_path / 'daily-production.xls'
    stored_path.write_bytes(b'fake-workbook')

    monkeypatch.setattr(
        'app.services.import_service._save_upload_file',
        lambda _upload: (stored_path, b'fake-workbook', 'daily-production.xls'),
    )
    monkeypatch.setattr('app.services.import_service.parse_daily_production_workbook', lambda *_args, **_kwargs: [])

    batch = SimpleNamespace(
        id=1,
        import_type='daily_production_report',
        batch_no='IMP-DAILY',
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
    result = store_import_file(upload, db=db, current_user=None, import_type='daily_production_report')
    rows = sorted(db.rows, key=lambda item: item.row_number)

    assert result.summary['total_rows'] == 1
    assert result.summary['success_rows'] == 0
    assert result.summary['failed_rows'] == 1
    assert batch.error_summary == '每日产量工作簿未找到综合报表，请检查是否为生产系统综合日报表。'
    assert rows[0].status == 'failed'
    assert rows[0].raw_data == {'file_name': '鑫泰每日产量5月.xls', 'expected_sheet': '综合报表'}
    assert rows[0].mapped_data is None
    assert rows[0].error_msg == '每日产量工作簿未找到综合报表，请检查是否为生产系统综合日报表。'
