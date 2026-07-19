from __future__ import annotations

from datetime import date
from importlib import import_module
import json
from pathlib import Path

from app.domain.daily_report_field_contract import normative_daily_report_fields
from app.services.report.output_skill_report_parser import parse_output_skill_daily_report

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

    assert summary | {"field_tolerances": None} == {
        'status': 'passed',
        'file_name': '2026-6-16_日报正文.txt',
        'field_match_rate': 100.0,
        'matched_fields': 130,
        'expected_fields': 130,
        'numeric_tolerance': None,
        'tolerance_matched_fields': 0,
        'difference_count': 0,
        'differences': [],
        'char_match_rate': 100.0,
        'exact_match': True,
        'threshold': 95.0,
        'reference_present_fields': 125,
        'declared_na_fields': [],
        'invalid_na_fields': [],
        'reference_absent_fields': [],
        'reference_absent_count': 0,
        'normative_fields': 125,
        'normative_denominator': 125,
        'normative_matched_fields': 125,
        'normative_coverage_rate': 100.0,
        'field_tolerances': None,
    }
    assert summary['field_tolerances']['total_output_daily'] == 20.0
    assert summary['field_tolerances']['daily_yield_rate'] == 0.2


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
    assert all(set(item) == {'field', 'actual', 'expected', 'delta', 'tolerance'} for item in summary['differences'])
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
        'numeric_tolerance': None,
        'field_tolerances': {},
        'tolerance_matched_fields': None,
        'difference_count': None,
        'differences': [],
        'char_match_rate': None,
        'exact_match': False,
        'threshold': 95.0,
        'reference_present_fields': None,
        'declared_na_fields': [],
        'invalid_na_fields': [],
        'reference_absent_fields': [],
        'reference_absent_count': None,
        'normative_fields': 125,
        'normative_denominator': None,
        'normative_matched_fields': None,
        'normative_coverage_rate': None,
    }


def test_alignment_blocks_undeclared_reference_gaps_and_accepts_explicit_na(tmp_path) -> None:
    service = _service()
    expected_text = '6月16日，车间总产量日合计328吨。'
    report_path = tmp_path / '2026-6-16_日报正文.txt'
    report_path.write_text(expected_text, encoding='utf-8')
    normative_fields = normative_daily_report_fields()
    parsed_fields = set(parse_output_skill_daily_report(expected_text))
    absent_fields = [field_name for field_name in normative_fields if field_name not in parsed_fields]

    blocked = service.build_output_skill_alignment(expected_text, tmp_path, FIXTURE_DATE)

    assert blocked['status'] == 'blocked'
    assert blocked['reference_present_fields'] == len(normative_fields) - len(absent_fields)
    assert blocked['reference_absent_fields'] == absent_fields
    assert blocked['reference_absent_count'] == len(absent_fields)
    assert blocked['normative_denominator'] == 125

    sidecar = report_path.with_suffix('.na.json')
    sidecar.write_text(json.dumps({'not_applicable': absent_fields}), encoding='utf-8')
    passed = service.build_output_skill_alignment(expected_text, tmp_path, FIXTURE_DATE)

    assert passed['status'] == 'passed'
    assert passed['declared_na_fields'] == absent_fields
    assert passed['invalid_na_fields'] == []
    assert passed['reference_absent_fields'] == []
    assert passed['normative_denominator'] == len(parsed_fields & set(normative_fields))
    assert passed['normative_coverage_rate'] == 100.0


def test_alignment_blocks_unknown_and_duplicate_na_fields(tmp_path) -> None:
    service = _service()
    expected_text = '6月16日，车间总产量日合计328吨。'
    report_path = tmp_path / '2026-6-16_日报正文.txt'
    report_path.write_text(expected_text, encoding='utf-8')
    normative_fields = normative_daily_report_fields()
    parsed_fields = set(parse_output_skill_daily_report(expected_text))
    duplicate = next(field_name for field_name in normative_fields if field_name not in parsed_fields)
    report_path.with_suffix('.na.json').write_text(
        json.dumps({'not_applicable': [duplicate, duplicate, 'not_a_daily_report_field']}),
        encoding='utf-8',
    )

    summary = service.build_output_skill_alignment(expected_text, tmp_path, FIXTURE_DATE)

    assert summary['status'] == 'blocked'
    assert summary['declared_na_fields'] == []
    assert summary['invalid_na_fields'] == [duplicate, 'not_a_daily_report_field']
    assert duplicate in summary['reference_absent_fields']
