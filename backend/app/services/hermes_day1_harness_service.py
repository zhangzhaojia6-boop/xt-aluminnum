from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
from typing import Any

from app.services.hermes_day1_evidence_service import classify_dingtalk_evidence
from app.services.report.output_skill_reconciliation import reconcile_rendered_daily_report


_ALIGNMENT_KEYS = (
    'status',
    'file_name',
    'field_match_rate',
    'matched_fields',
    'expected_fields',
    'difference_count',
    'differences',
    'char_match_rate',
    'exact_match',
    'threshold',
)
_SECTION_TITLES = ('工厂大脑判断单', '正式日报正文', '各车间明细')
_TEXT_ENCODINGS = ('utf-8-sig', 'utf-8', 'gb18030', 'gbk')


@dataclass(frozen=True, slots=True)
class HarnessCaseResult:
    name: str
    passed: bool
    detail: str


def evaluate_day1_run_payload(
    payload: dict[str, Any],
    *,
    answer: str,
    output_skill_expected_text: str | None = None,
    min_field_match_rate: float = 95.0,
) -> list[HarnessCaseResult]:
    payload_map = _as_mapping(payload)
    sources = _as_mapping(payload_map.get('sources'))
    conflicts = _as_list(payload_map.get('conflicts'))
    missing_fields = [str(item) for item in _as_list(payload_map.get('missing_fields')) if str(item).strip()]
    alignment = _resolve_alignment(
        payload_map,
        sources=sources,
        answer=answer,
        output_skill_expected_text=output_skill_expected_text,
        min_field_match_rate=min_field_match_rate,
    )
    learning = _as_mapping(payload_map.get('learning'))
    correction_policy = _as_mapping(payload_map.get('correction_action_policy'))

    return [
        _evaluate_source_coverage(payload_map, sources=sources),
        _evaluate_three_part_sections(answer),
        _evaluate_conflicts(conflicts=conflicts, answer=answer),
        _evaluate_missing_fields(missing_fields=missing_fields, answer=answer),
        _evaluate_dingtalk_evidence_classification(payload_map, sources=sources),
        _evaluate_learning_trace(learning),
        _evaluate_output_skill_alignment(alignment=alignment, answer=answer, min_field_match_rate=min_field_match_rate),
        _evaluate_correction_action_policy(correction_policy),
    ]


def summarize_harness_results(results: list[HarnessCaseResult]) -> dict[str, Any]:
    failed_cases = [item.name for item in results if not item.passed]
    return {
        'passed': not failed_cases,
        'passed_count': len(results) - len(failed_cases),
        'total_count': len(results),
        'failed_cases': failed_cases,
    }


def load_output_skill_daily_text(root: str | Path | None, business_date: date) -> str | None:
    matched_file = _find_output_skill_daily_file(root, business_date)
    if matched_file is None:
        return None
    return _read_text_file(matched_file)


def build_output_skill_alignment(
    actual_text: str,
    root: str | Path | None,
    business_date: date,
    min_field_match_rate: float = 95.0,
) -> dict[str, Any]:
    threshold = _normalise_threshold(min_field_match_rate)
    matched_file = _find_output_skill_daily_file(root, business_date)
    if matched_file is None:
        return _missing_alignment_summary(threshold)

    expected_text = _read_text_file(matched_file)
    if expected_text is None:
        return _missing_alignment_summary(threshold)

    reconciled = reconcile_rendered_daily_report(actual_text or '', expected_text)
    field_match_rate = _normalise_rate(reconciled.get('field_match_rate'))
    status = 'passed' if field_match_rate is not None and field_match_rate >= threshold else 'review_needed'
    return {
        'status': status,
        'file_name': matched_file.name,
        'field_match_rate': field_match_rate,
        'matched_fields': reconciled.get('matched_fields'),
        'expected_fields': reconciled.get('expected_fields'),
        'difference_count': len(reconciled.get('differences') or []),
        'differences': [
            {
                'field': str(item.get('field')),
                'actual': item.get('actual'),
                'expected': item.get('expected'),
            }
            for item in reconciled.get('differences') or []
        ],
        'char_match_rate': _normalise_rate(reconciled.get('char_match_rate')),
        'exact_match': bool(reconciled.get('exact_match')),
        'threshold': threshold,
    }


def _evaluate_source_coverage(payload: Mapping[str, Any], *, sources: Mapping[str, Any]) -> HarnessCaseResult:
    required = (
        'template_daily_report',
        'mes_wms',
        'audit_run',
        'dingtalk_evidence',
        'dingtalk_messages',
        'rag',
        'historical_reports',
        'output_skill_alignment',
    )
    missing = [
        name
        for name in required
        if name != 'output_skill_alignment'
        and name not in sources
    ]
    if 'output_skill_alignment' not in sources and 'output_skill_alignment' not in payload:
        missing.append('output_skill_alignment')
    if not missing:
        return HarnessCaseResult('source_coverage', True, '已覆盖数据中枢、MES/WMS、审计、钉钉证据/文本、RAG、历史日报、输出 skill。')
    return HarnessCaseResult('source_coverage', False, f'缺少查证来源：{"、".join(missing)}。')


def _evaluate_three_part_sections(answer: str) -> HarnessCaseResult:
    missing = [title for title in _SECTION_TITLES if title not in answer]
    if not missing:
        return HarnessCaseResult('three_part_sections', True, '三段式标题完整。')
    return HarnessCaseResult('three_part_sections', False, f'缺少三段式标题：{"、".join(missing)}。')


def _evaluate_conflicts(*, conflicts: list[Any], answer: str) -> HarnessCaseResult:
    if not conflicts:
        return HarnessCaseResult('conflicts_visible', True, '本次没有冲突。')
    judgment = _extract_section(answer, '工厂大脑判断单', '正式日报正文')
    if '冲突' in judgment or '冲突' in answer:
        return HarnessCaseResult('conflicts_visible', True, '冲突已进入工厂大脑判断单。')
    return HarnessCaseResult('conflicts_visible', False, '存在 conflicts，但工厂大脑判断单没有明确写出“冲突”。')


def _evaluate_missing_fields(*, missing_fields: list[str], answer: str) -> HarnessCaseResult:
    if not missing_fields:
        return HarnessCaseResult('missing_fields_visible', True, '本次没有缺字段。')
    formal_text = _extract_section(answer, '正式日报正文', '各车间明细')
    if any(keyword in formal_text for keyword in ('缺失', '缺字段')) or any(keyword in answer for keyword in ('缺失', '缺字段')):
        return HarnessCaseResult('missing_fields_visible', True, '缺字段已在正式正文或整体回复里说明。')
    return HarnessCaseResult('missing_fields_visible', False, f'存在缺字段 {",".join(missing_fields)}，但正式正文没有明确说明缺失/缺字段。')


def _evaluate_dingtalk_evidence_classification(payload: Mapping[str, Any], *, sources: Mapping[str, Any]) -> HarnessCaseResult:
    rows = []
    if isinstance(sources.get('dingtalk_evidence'), list):
        rows = list(sources.get('dingtalk_evidence') or [])
    elif isinstance(payload.get('dingtalk_evidence'), list):
        rows = list(payload.get('dingtalk_evidence') or [])
    checkable = 0
    mismatches: list[str] = []
    for row in rows:
        row_map = _as_mapping(row)
        payload_map = _as_mapping(row_map.get('payload'))
        stored_kind = str(payload_map.get('evidence_kind') or row_map.get('evidence_kind') or '').strip()
        recognized_text = str(row_map.get('recognized_text') or '')
        file_name = payload_map.get('file_name') or row_map.get('file_name')
        if not stored_kind:
            continue
        checkable += 1
        actual = classify_dingtalk_evidence(recognized_text, file_name=str(file_name) if file_name else None)
        if actual.evidence_kind != stored_kind:
            mismatches.append(f'{stored_kind}->{actual.evidence_kind}')
    if checkable == 0:
        return HarnessCaseResult('dingtalk_evidence_classification', True, '本次没有可校验的钉钉证据样本。')
    if not mismatches:
        return HarnessCaseResult('dingtalk_evidence_classification', True, f'已校验 {checkable} 条钉钉证据分类。')
    return HarnessCaseResult('dingtalk_evidence_classification', False, f'钉钉证据分类不一致：{"；".join(mismatches)}。')


def _evaluate_learning_trace(learning: Mapping[str, Any]) -> HarnessCaseResult:
    tools_called = [str(item) for item in _as_list(learning.get('tools_called')) if str(item).strip()]
    source_trace = [str(item) for item in _as_list(learning.get('source_trace')) if str(item).strip()]
    required_tools = (
        'template_daily_report',
        'mes_wms_read',
        'hermes_data_audit',
        'dingtalk_evidence_scan',
        'dingtalk_message_scan',
        'historical_reports_scan',
        'rag_query',
        'output_skill_alignment',
        'build_day1_three_part_report',
    )
    missing_tools = [name for name in required_tools if name not in tools_called]
    if learning.get('event_recorded') and tools_called and source_trace and not missing_tools:
        return HarnessCaseResult('learning_trace_recorded', True, 'payload 已记录学习事件和工具调用路径。')
    if missing_tools:
        return HarnessCaseResult('learning_trace_recorded', False, f'tools_called 缺少必需来源级工具：{"、".join(missing_tools)}。')
    return HarnessCaseResult('learning_trace_recorded', False, 'payload 没有完整记录 learning event 或 tools_called/source_trace。')


def _evaluate_output_skill_alignment(
    *,
    alignment: Mapping[str, Any],
    answer: str,
    min_field_match_rate: float,
) -> HarnessCaseResult:
    threshold = _normalise_threshold(min_field_match_rate)
    field_match_rate = _normalise_rate(alignment.get('field_match_rate'))
    if field_match_rate is None:
        return HarnessCaseResult('output_skill_alignment', False, '没有可用的输出 skill 对齐结果。')
    if field_match_rate >= threshold:
        return HarnessCaseResult('output_skill_alignment', True, f'字段匹配率 {field_match_rate:.1f}% 达到阈值。')
    detail = f'字段匹配率 {field_match_rate:.1f}% 低于阈值 {threshold:.1f}%。'
    difference_fields = [
        str(item.get('field'))
        for item in _as_list(alignment.get('differences'))
        if isinstance(item, Mapping) and str(item.get('field') or '').strip()
    ]
    if difference_fields:
        detail += f' 差异字段：{"、".join(difference_fields)}。'
        missing_names = [name for name in difference_fields if name not in answer]
        if missing_names:
            detail += f' 判断单缺少字段名：{"、".join(missing_names)}。'
    if '已对齐' in answer:
        detail += ' 低于阈值时不能写“已对齐”。'
    return HarnessCaseResult('output_skill_alignment', False, detail)


def _evaluate_correction_action_policy(correction_policy: Mapping[str, Any]) -> HarnessCaseResult:
    mode = str(correction_policy.get('mode') or '').strip().lower()
    default_execution = str(correction_policy.get('default_execution') or '').strip().lower()
    execution_enabled = correction_policy.get('execution_enabled')
    if mode == 'audit_only' or default_execution in {'disabled', 'audit_only'} or execution_enabled is False:
        return HarnessCaseResult('correction_action_policy', True, 'correction action 只审计设计，不默认执行。')
    return HarnessCaseResult('correction_action_policy', False, '没有明确表达 correction action 只审计设计，不默认执行。')


def _resolve_alignment(
    payload: Mapping[str, Any],
    *,
    sources: Mapping[str, Any],
    answer: str,
    output_skill_expected_text: str | None,
    min_field_match_rate: float,
) -> Mapping[str, Any]:
    direct = _as_mapping(payload.get('output_skill_alignment'))
    if direct:
        return direct
    nested = _as_mapping(sources.get('output_skill_alignment'))
    if nested:
        return nested
    if not output_skill_expected_text:
        return {}
    formal_text = _extract_section(answer, '正式日报正文', '各车间明细') or answer
    reconciled = reconcile_rendered_daily_report(formal_text, output_skill_expected_text)
    return {
        'status': 'passed' if _normalise_rate(reconciled.get('field_match_rate')) >= _normalise_threshold(min_field_match_rate) else 'review_needed',
        'file_name': None,
        'field_match_rate': _normalise_rate(reconciled.get('field_match_rate')),
        'matched_fields': reconciled.get('matched_fields'),
        'expected_fields': reconciled.get('expected_fields'),
        'difference_count': len(reconciled.get('differences') or []),
        'differences': reconciled.get('differences') or [],
        'char_match_rate': _normalise_rate(reconciled.get('char_match_rate')),
        'exact_match': bool(reconciled.get('exact_match')),
        'threshold': _normalise_threshold(min_field_match_rate),
    }


def _find_output_skill_daily_file(root: str | Path | None, business_date: date) -> Path | None:
    root_path = _coerce_root(root)
    if root_path is None:
        return None
    candidates = [
        path
        for path in root_path.rglob('*.txt')
        if '日报' in path.name and _matches_business_date(path.name, business_date)
    ]
    if not candidates:
        return None
    return sorted(candidates, key=_output_skill_file_sort_key)[0]


def _coerce_root(root: str | Path | None) -> Path | None:
    if root is None:
        return None
    path = Path(root)
    if not path.exists() or not path.is_dir():
        return None
    return path


def _output_skill_file_sort_key(path: Path) -> tuple[int, int, str]:
    name = path.name
    if name.endswith('_日报正文.txt'):
        priority = 0
    elif '日报正文' in name:
        priority = 1
    else:
        priority = 2
    return (priority, len(name), str(path))


def _matches_business_date(file_name: str, business_date: date) -> bool:
    month = business_date.month
    day = business_date.day
    patterns = (
        rf'(?<!\d){business_date.year}[-_.]0?{month}[-_.]0?{day}(?!\d)',
        rf'(?<!\d){business_date.year}年0?{month}月0?{day}日',
        rf'(?<!\d)0?{month}月0?{day}日',
    )
    return any(re.search(pattern, file_name) for pattern in patterns)


def _read_text_file(path: Path) -> str | None:
    for encoding in _TEXT_ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    try:
        return path.read_text(encoding='utf-8', errors='ignore')
    except OSError:
        return None


def _missing_alignment_summary(min_field_match_rate: float) -> dict[str, Any]:
    return {
        'status': 'missing',
        'file_name': None,
        'field_match_rate': None,
        'matched_fields': None,
        'expected_fields': None,
        'difference_count': None,
        'differences': [],
        'char_match_rate': None,
        'exact_match': False,
        'threshold': _normalise_threshold(min_field_match_rate),
    }


def _extract_section(text: str, start_title: str, end_title: str | None) -> str:
    clean = str(text or '')
    start_marker = f'{start_title}\n'
    start = clean.find(start_marker)
    if start == -1:
        return ''
    start += len(start_marker)
    if end_title is None:
        return clean[start:].strip()
    end_marker = f'\n\n{end_title}\n'
    end = clean.find(end_marker, start)
    if end == -1:
        return clean[start:].strip()
    return clean[start:end].strip()


def _normalise_rate(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 1.0:
        return round(number * 100, 3)
    return round(number, 3)


def _normalise_threshold(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 95.0
    if number <= 1.0:
        return round(number * 100, 3)
    return round(number, 3)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]
