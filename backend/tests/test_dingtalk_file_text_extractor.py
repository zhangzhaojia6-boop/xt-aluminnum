from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace

import openpyxl

from app.services import dingtalk_file_text_extractor as extractor


def test_text_file_extracts_chinese_content_with_gb18030_fallback() -> None:
    content = '一车间 2026-06-28 产量 32 吨'.encode('gb18030')

    result = extractor.extract_dingtalk_file_text('日报.txt', content, max_bytes=1024)

    assert result.status == 'text_captured'
    assert result.text == '一车间 2026-06-28 产量 32 吨'
    assert result.detail == 'encoding=gb18030'


def test_csv_extracts_rows() -> None:
    content = '日期,车间,产量\n2026-06-28,二车间,45\n'.encode()

    result = extractor.extract_dingtalk_file_text('产量.csv', content, max_bytes=1024)

    assert result.status == 'text_captured'
    assert result.text == '日期\t车间\t产量\n2026-06-28\t二车间\t45'


def test_xlsx_extracts_sheet_names_and_cell_text() -> None:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = '日报'
    worksheet.append(['日期', '产量'])
    worksheet.append(['2026-06-28', 32])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()

    result = extractor.extract_dingtalk_file_text('日报.xlsx', buffer.getvalue(), max_bytes=100_000)

    assert result.status == 'text_captured'
    assert '[日报]' in result.text
    assert '日期\t产量' in result.text
    assert '2026-06-28\t32' in result.text


def test_xls_extracts_rows_when_xlrd_is_available(monkeypatch) -> None:
    class FakeSheet:
        name = '日报'
        nrows = 2
        ncols = 2

        def cell_value(self, row_index, column_index):
            return [
                ['日期', '入库'],
                ['2026-06-28', 18],
            ][row_index][column_index]

    fake_workbook = SimpleNamespace(datemode=0, sheets=lambda: [FakeSheet()])
    monkeypatch.setattr(extractor.xlrd, 'open_workbook', lambda *, file_contents: fake_workbook)

    result = extractor.extract_dingtalk_file_text('日报.xls', b'fake-xls', max_bytes=1024)

    assert result.status == 'text_captured'
    assert result.text == '[日报]\n日期\t入库\n2026-06-28\t18'


def test_pdf_is_unsupported_without_fake_text() -> None:
    result = extractor.extract_dingtalk_file_text('日报.pdf', b'%PDF-1.4 fake', max_bytes=1024)

    assert result.status == 'unsupported_file_type'
    assert result.text == ''
    assert result.detail == 'unsupported_suffix=.pdf'


def test_oversized_file_returns_too_large_without_text() -> None:
    content = b'123456789'

    result = extractor.extract_dingtalk_file_text('日报.txt', content, max_bytes=8)

    assert result.status == 'too_large'
    assert result.text == ''
    assert result.content_hash == sha256(content).hexdigest()


def test_content_hash_is_stable_for_same_bytes() -> None:
    content = b'factory report'

    first = extractor.extract_dingtalk_file_text('a.txt', content, max_bytes=1024)
    second = extractor.extract_dingtalk_file_text('b.csv', content, max_bytes=1024)

    assert first.content_hash == second.content_hash == sha256(content).hexdigest()
