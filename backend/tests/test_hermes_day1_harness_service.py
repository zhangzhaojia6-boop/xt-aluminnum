from __future__ import annotations

from datetime import date
from importlib import import_module


BUSINESS_DATE = date(2026, 6, 16)


def _service():
    return import_module('app.services.hermes_day1_harness_service')


def _answer(*, extra_judgment: str = '') -> str:
    judgment = '工厂大脑判断单\n已对齐。已完成多源查证。'
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
            'tools_called': ['collect_day1_sources', 'build_day1_three_part_report'],
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
        answer='工厂大脑判断单\n只有两段\n\n各车间明细\n缺正式正文标题',
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
        answer='工厂大脑判断单\n继续生成。\n\n正式日报正文\n这里不应该编造。\n\n各车间明细\n暂无。',
    )

    failed = {item.name: item.detail for item in results if not item.passed}
    assert 'missing_fields_visible' in failed
    assert '缺失' in failed['missing_fields_visible'] or '缺字段' in failed['missing_fields_visible']
