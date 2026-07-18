from __future__ import annotations

from datetime import date
from importlib import import_module
import json

from app.domain.daily_report_field_contract import normative_daily_report_fields
from app.services.report.output_skill_report_parser import parse_output_skill_daily_report


BUSINESS_DATE = date(2026, 6, 16)


def _service():
    return import_module('app.services.hermes_day1_harness_service')


def _answer(*, extra_judgment: str = '') -> str:
    judgment = '智能大脑判断单\n已对齐。已完成多源查证。'
    if extra_judgment:
        judgment += extra_judgment
    return '\n\n'.join(
        [
            judgment,
            '正式日报正文\n6月16日，车间总产量日合计328吨（外加工0吨）比昨日↑22吨，月累计5014吨（外加工月累计270吨）。',
            '各车间明细\n【2050车间】\n日产量：96吨，月累计：2103吨。',
        ]
    )


def _payload() -> dict:
    return {
        'sources': {
            'template_daily_report': {'status': 'ready'},
            'mes_wms': {'source_status': {'mes': 'ok'}},
            'audit_run': {'status': 'completed'},
            'dingtalk_evidence': [
                {
                    'recognized_text': '日报产量 328 吨',
                    'payload': {'evidence_kind': 'fact', 'file_name': '6月16日日报.txt'},
                },
                {
                    'recognized_text': '2050 停机 2 小时，影响产量',
                    'payload': {'evidence_kind': 'explanation'},
                },
                {
                    'recognized_text': '以后这份日报以这个为准',
                    'payload': {'evidence_kind': 'instruction'},
                },
                {
                    'recognized_text': '收到，谢谢',
                    'payload': {'evidence_kind': 'noise'},
                },
            ],
            'dingtalk_messages': [{'id': 1, 'text': '日报正文见附件'}],
            'rag': {'answer': '日报模板说明', 'citations': [{'source_ref': 'doc#1'}]},
            'historical_reports': [{'id': 1, 'report_date': '2026-06-15'}],
            'output_skill_alignment': {
                'status': 'passed',
                'file_name': '2026-6-16_日报正文.txt',
                'field_match_rate': 100.0,
                'matched_fields': 3,
                'expected_fields': 3,
                'difference_count': 0,
                'differences': [],
                'char_match_rate': 100.0,
                'exact_match': True,
                'threshold': 95.0,
            },
        },
        'missing_fields': [],
        'conflicts': [],
        'output_skill_alignment': {
            'status': 'passed',
            'file_name': '2026-6-16_日报正文.txt',
            'field_match_rate': 100.0,
            'matched_fields': 3,
            'expected_fields': 3,
            'difference_count': 0,
            'differences': [],
            'char_match_rate': 100.0,
            'exact_match': True,
            'threshold': 95.0,
        },
        'learning': {
            'event_recorded': True,
            'tools_called': [
                'template_daily_report',
                'mes_wms_read',
                'hermes_data_audit',
                'dingtalk_evidence_scan',
                'dingtalk_message_scan',
                'historical_reports_scan',
                'rag_query',
                'output_skill_alignment',
                'build_day1_three_part_report',
            ],
            'source_trace': [
                'template_daily_report',
                'mes_wms',
                'audit_run',
                'dingtalk_evidence',
                'dingtalk_messages',
                'rag',
                'historical_reports',
                'output_skill_alignment',
            ],
        },
        'correction_action_policy': {
            'mode': 'audit_only',
            'default_execution': 'disabled',
            'note': 'correction action 只审计设计，不默认执行',
        },
    }


def test_evaluate_day1_run_payload_passes_complete_three_part_output() -> None:
    service = _service()

    results = service.evaluate_day1_run_payload(
        _payload(),
        answer=_answer(),
    )
    summary = service.summarize_harness_results(results)

    assert [item.name for item in results] == [
        'source_coverage',
        'three_part_sections',
        'conflicts_visible',
        'missing_fields_visible',
        'dingtalk_evidence_classification',
        'learning_trace_recorded',
        'output_skill_alignment',
        'correction_action_policy',
    ]
    assert all(item.passed for item in results)
    assert summary == {
        'passed': True,
        'passed_count': 8,
        'total_count': 8,
        'failed_cases': [],
    }


def test_evaluate_day1_run_payload_fails_when_required_sections_missing() -> None:
    service = _service()

    results = service.evaluate_day1_run_payload(
        _payload(),
        answer='智能大脑判断单\n只有两段\n\n各车间明细\n缺正式正文标题',
    )

    failed = {item.name: item.detail for item in results if not item.passed}
    assert 'three_part_sections' in failed
    assert '正式日报正文' in failed['three_part_sections']


def test_evaluate_day1_run_payload_requires_conflict_word_when_conflicts_exist() -> None:
    service = _service()
    payload = _payload()
    payload['conflicts'] = [{'field': 'total_output_daily', 'message': '数据中枢与输出 skill 不一致'}]

    results = service.evaluate_day1_run_payload(
        payload,
        answer=_answer(),
    )

    failed = {item.name: item.detail for item in results if not item.passed}
    assert 'conflicts_visible' in failed
    assert '冲突' in failed['conflicts_visible']


def test_evaluate_day1_run_payload_requires_missing_field_note() -> None:
    service = _service()
    payload = _payload()
    payload['missing_fields'] = ['total_output_daily']

    results = service.evaluate_day1_run_payload(
        payload,
        answer='智能大脑判断单\n继续生成。\n\n正式日报正文\n这里不应该编造。\n\n各车间明细\n暂无。',
    )

    failed = {item.name: item.detail for item in results if not item.passed}
    assert 'missing_fields_visible' in failed
    assert '缺失' in failed['missing_fields_visible'] or '缺字段' in failed['missing_fields_visible']


def test_evaluate_day1_run_payload_fails_when_required_tools_missing() -> None:
    service = _service()
    payload = _payload()
    payload['learning']['tools_called'] = [
        'template_daily_report',
        'hermes_data_audit',
        'dingtalk_evidence_scan',
        'dingtalk_message_scan',
        'historical_reports_scan',
        'rag_query',
        'build_day1_three_part_report',
    ]

    results = service.evaluate_day1_run_payload(
        payload,
        answer=_answer(),
    )

    failed = {item.name: item.detail for item in results if not item.passed}
    assert 'learning_trace_recorded' in failed
    assert 'mes_wms_read' in failed['learning_trace_recorded']
    assert 'output_skill_alignment' in failed['learning_trace_recorded']


def test_evaluate_day1_run_payload_requires_difference_fields_when_alignment_low() -> None:
    service = _service()
    payload = _payload()
    payload['sources']['output_skill_alignment'] = {
        'status': 'review_needed',
        'file_name': '2026-6-16_日报正文.txt',
        'field_match_rate': 82.0,
        'matched_fields': 2,
        'expected_fields': 4,
        'difference_count': 2,
        'differences': [
            {'field': 'total_output_daily', 'actual': 328, 'expected': 320},
            {'field': 'cost_per_ton', 'actual': 1044, 'expected': 999},
        ],
        'char_match_rate': 91.0,
        'exact_match': False,
        'threshold': 95.0,
    }
    payload['output_skill_alignment'] = payload['sources']['output_skill_alignment']

    results = service.evaluate_day1_run_payload(
        payload,
        answer='智能大脑判断单\n字段匹配率低于 95%。\n\n正式日报正文\n这里仍然给正文。\n\n各车间明细\n暂无。',
    )

    failed = {item.name: item.detail for item in results if not item.passed}
    assert 'output_skill_alignment' in failed
    assert 'total_output_daily' in failed['output_skill_alignment']
    assert 'cost_per_ton' in failed['output_skill_alignment']


def test_evaluate_day1_run_payload_prefers_stored_evidence_kind_over_truncated_snippet() -> None:
    service = _service()
    payload = _payload()
    payload['sources']['dingtalk_evidence'][2] = {
        'recognized_text': '以后这份日报...',
        'payload': {'evidence_kind': 'instruction'},
    }

    results = service.evaluate_day1_run_payload(
        payload,
        answer=_answer(),
    )

    by_name = {item.name: item for item in results}
    assert by_name['dingtalk_evidence_classification'].passed is True


def test_fallback_alignment_uses_structured_reference_na_metadata(tmp_path) -> None:
    service = _service()
    formal_text = _answer().split('正式日报正文\n', 1)[1].split('\n\n各车间明细', 1)[0]
    present_fields = set(parse_output_skill_daily_report(formal_text))
    declared_na_fields = [
        field_name
        for field_name in normative_daily_report_fields()
        if field_name not in present_fields
    ]
    report_path = tmp_path / '2026-6-16_日报正文.txt'
    report_path.write_text(formal_text, encoding='utf-8')
    report_path.with_suffix('.na.json').write_text(
        json.dumps({'not_applicable': declared_na_fields}),
        encoding='utf-8',
    )

    built_alignment = service.build_output_skill_alignment(formal_text, tmp_path, BUSINESS_DATE)
    reference = service.load_output_skill_daily_reference(tmp_path, BUSINESS_DATE)
    payload = _payload()
    payload.pop('output_skill_alignment')
    payload['sources'].pop('output_skill_alignment')
    results = service.evaluate_day1_run_payload(
        payload,
        answer=_answer(),
        output_skill_reference=reference,
    )

    assert built_alignment['status'] == 'passed'
    assert built_alignment['declared_na_fields'] == declared_na_fields
    assert reference is not None
    by_name = {item.name: item for item in results}
    assert by_name['output_skill_alignment'].passed is True
