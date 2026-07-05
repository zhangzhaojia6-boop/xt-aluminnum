from __future__ import annotations

from datetime import date
from importlib import import_module
from pathlib import Path


FIXTURE_DATE = date(2026, 6, 16)


def _service():
    return import_module('app.services.hermes_day1_harness_service')


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parent / 'fixtures' / 'output_skill_daily_reports'


def _fixture_text() -> str:
    return (_fixture_dir() / '2026-6-16_日报正文.txt').read_text(encoding='utf-8')


def test_load_output_skill_daily_text_matches_unpadded_file_name() -> None:
    service = _service()

    text = service.load_output_skill_daily_text(_fixture_dir(), FIXTURE_DATE)

    assert text is not None
    assert '6月16日，车间总产量日合计328吨' in text


def test_load_output_skill_daily_text_matches_zero_padded_report_name(tmp_path) -> None:
    service = _service()
    report = tmp_path / '2026-06-16_生产日报正文_v2.txt'
    report.write_text('zero padded report', encoding='utf-8')

    text = service.load_output_skill_daily_text(tmp_path, FIXTURE_DATE)

    assert text == 'zero padded report'


def test_build_output_skill_alignment_returns_100_with_fixture() -> None:
    service = _service()

    summary = service.build_output_skill_alignment(
        _fixture_text(),
        _fixture_dir(),
        FIXTURE_DATE,
    )

    assert summary == {
        'status': 'passed',
        'file_name': '2026-6-16_日报正文.txt',
        'field_match_rate': 100.0,
        'matched_fields': 130,
        'expected_fields': 130,
        'numeric_tolerance': 20.0,
        'tolerance_matched_fields': 0,
        'difference_count': 0,
        'differences': [],
        'char_match_rate': 100.0,
        'exact_match': True,
        'threshold': 95.0,
    }


def test_build_output_skill_alignment_returns_diff_summary_without_raw_text() -> None:
    service = _service()
    actual_text = '6月16日，日报正文严重缺失，只保留一句。'

    summary = service.build_output_skill_alignment(
        actual_text,
        _fixture_dir(),
        FIXTURE_DATE,
    )

    assert summary['status'] == 'review_needed'
    assert summary['file_name'] == '2026-6-16_日报正文.txt'
    assert summary['field_match_rate'] < 100.0
    assert summary['difference_count'] >= 1
    assert all(set(item) == {'field', 'actual', 'expected', 'delta'} for item in summary['differences'])
    assert '6月16日，车间总产量日合计328吨' not in str(summary)
    assert '当天在制料879吨' not in str(summary)


def test_build_output_skill_alignment_returns_missing_when_root_missing() -> None:
    service = _service()

    summary = service.build_output_skill_alignment(
        '6月16日日报正文',
        None,
        FIXTURE_DATE,
    )

    assert summary == {
        'status': 'missing',
        'file_name': None,
        'field_match_rate': None,
        'matched_fields': None,
        'expected_fields': None,
        'difference_count': None,
        'differences': [],
        'char_match_rate': None,
        'exact_match': False,
        'threshold': 95.0,
    }
