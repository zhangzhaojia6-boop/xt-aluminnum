from datetime import date, datetime
from hashlib import sha256
from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

from openpyxl import Workbook

from app.services.dingtalk_verified_fact_extractor import extract_verified_file_fact_updates


MODIFIED_TAG = '{http://purl.org/dc/terms/}modified'


def _set_workbook_modified(content: bytes, modified: datetime | None) -> bytes:
    output = BytesIO()
    with ZipFile(BytesIO(content), 'r') as source, ZipFile(output, 'w') as target:
        for item in source.infolist():
            value = source.read(item.filename)
            if item.filename == 'docProps/core.xml':
                root = ElementTree.fromstring(value)
                node = root.find(MODIFIED_TAG)
                if node is not None and modified is None:
                    root.remove(node)
                elif node is not None:
                    node.text = modified.isoformat(timespec='seconds') + 'Z'
                value = ElementTree.tostring(root, encoding='utf-8', xml_declaration=True)
            target.writestr(item, value)
    return output.getvalue()


def _workbook_bytes(
    *,
    month: int = 7,
    include_total_header: bool = True,
    value=0.8381,
    modified: datetime | None = datetime(2026, 7, 12),
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = '成品率'
    sheet['A1'] = f'{month}月份各车间成品率车间指标'
    sheet['A2'] = '日期'
    sheet.merge_cells('A2:A5')
    sheet['AB2'] = '公司'
    sheet.merge_cells('AB2:AK2')
    if include_total_header:
        sheet['AJ3'] = '总成品率92%'
        sheet.merge_cells('AJ3:AK4')
    sheet['AJ5'] = '日合计'
    sheet['AK5'] = '月累计'
    sheet['A6'] = 12
    sheet['AJ6'] = value
    output = BytesIO()
    workbook.save(output)
    return _set_workbook_modified(output.getvalue(), modified)


def _extract(content: bytes) -> dict:
    return extract_verified_file_fact_updates(
        file_name='各车间成品率.xlsx',
        content=content,
        business_date=date(2026, 7, 12),
        file_sha256=sha256(content).hexdigest(),
    )


def test_verified_yield_extractor_requires_matching_month() -> None:
    assert _extract(_workbook_bytes(month=6)) == {}


def test_verified_yield_extractor_requires_total_yield_header() -> None:
    assert _extract(_workbook_bytes(include_total_header=False)) == {}


def test_verified_yield_extractor_rejects_non_numeric_target_cell() -> None:
    assert _extract(_workbook_bytes(value='/')) == {}


def test_verified_yield_extractor_returns_cell_traceable_fact() -> None:
    result = _extract(_workbook_bytes())

    assert result['daily_yield_rate']['value'] == 83.81
    assert result['daily_yield_rate']['source_ref']['workbook_modified_date'] == '2026-07-12'


def test_verified_yield_extractor_requires_complete_matching_workbook_date() -> None:
    assert _extract(_workbook_bytes(modified=None)) == {}
    assert _extract(_workbook_bytes(modified=datetime(2025, 7, 12))) == {}


def test_verified_yield_extractor_rejects_duplicate_business_date_rows() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = '成品率'
    workbook.properties.modified = datetime(2026, 7, 12)
    sheet['A1'] = '7月份各车间成品率车间指标'
    sheet['A2'] = '日期'
    sheet.merge_cells('A2:A5')
    sheet['AJ3'] = '总成品率92%'
    sheet.merge_cells('AJ3:AK4')
    sheet['AJ5'] = '日合计'
    sheet['A6'] = 12
    sheet['AJ6'] = 0.8381
    sheet['A7'] = 12
    sheet['AJ7'] = 0.9
    output = BytesIO()
    workbook.save(output)
    content = _set_workbook_modified(output.getvalue(), datetime(2026, 7, 12))

    assert _extract(content) == {}
