"""5.6 现场原始数据 dry-run 回放脚本。

用法:
    python backend/scripts/import_5_6_dry_run.py [--workbook PATH] [--report PATH]

不写库，只输出 markdown 报告。报告与现场事实底对账。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

DEFAULT_DATA_DIR = Path('C:/Users/xt/Desktop/5.6')

GROUND_TRUTH = {
    '铸锭': 369.746,
    '铸二': 24.25,
    '铸三': 39.06,
    '热轧': 92.4,
    '1650': 220.3,
    '1850': 41.2,
    '2050': 59.0,
    '冷轧合计': 320.5,
}

SUMMARY_WORKBOOK = '鑫泰每日产量5月.xls'


def load_summary_sheet(path: Path) -> pd.DataFrame:
    try:
        xls = pd.ExcelFile(path)
    except Exception as exc:
        print(f'[ERROR] 打开 {path} 失败: {exc}', file=sys.stderr)
        sys.exit(2)
    sheet_candidates = [name for name in xls.sheet_names if '综合' in name or '报表' in name]
    if not sheet_candidates:
        print(f'[ERROR] {path} 找不到综合报表 sheet', file=sys.stderr)
        sys.exit(2)
    return xls.parse(sheet_candidates[0], header=None)


def parse_with_canonical_service(frame: pd.DataFrame, sheet_name: str = '5-6'):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.services.daily_production_canonical_service import parse_daily_production_sheet
    return parse_daily_production_sheet(sheet_name, frame, source_batch_id=None, year_hint=2026)


def run_mapping_preview(rows: list[dict]) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.services.daily_production_mapping_service import DAILY_PRODUCTION_MAPPING_RULES, _normalize_label

    summary: dict = {'total': 0, 'ready': 0, 'unresolved': 0, 'needs_equipment_mapping': 0, 'unresolved_labels': []}
    for row in rows:
        summary['total'] += 1
        key = (_normalize_label(row.get('workshop_label')), _normalize_label(row.get('project_label')))
        rule = DAILY_PRODUCTION_MAPPING_RULES.get(key)
        if rule is None:
            summary['unresolved'] += 1
            summary['unresolved_labels'].append(key)
        elif rule.equipment_required and not rule.equipment_code:
            summary['needs_equipment_mapping'] += 1
        else:
            summary['ready'] += 1
    return summary


def reconcile_against_truth(rows: list[dict]) -> list[tuple[str, float, float, float]]:
    actuals: dict[str, float] = {}
    cold_rolling_total = 0.0
    for row in rows:
        ws = (row.get('workshop_label') or '').strip()
        proj = (row.get('project_label') or '').strip()
        out = float(row.get('daily_output_tons') or 0)
        if ws == '铸锭':
            actuals['铸锭'] = actuals.get('铸锭', 0) + out
        elif ws == '铸轧' and proj == '铸二':
            actuals['铸二'] = actuals.get('铸二', 0) + out
        elif ws == '铸轧' and proj == '铸三':
            actuals['铸三'] = actuals.get('铸三', 0) + out
        elif ws == '热轧' and proj == '热轧':
            actuals['热轧'] = actuals.get('热轧', 0) + out
        elif ws == '冷轧' and proj == '1650':
            actuals['1650'] = actuals.get('1650', 0) + out
            cold_rolling_total += out
        elif ws == '冷轧' and proj == '1850':
            actuals['1850'] = actuals.get('1850', 0) + out
            cold_rolling_total += out
        elif ws == '冷轧' and proj == '2050':
            actuals['2050'] = actuals.get('2050', 0) + out
            cold_rolling_total += out

    actuals['冷轧合计'] = cold_rolling_total

    rows_out = []
    for label, expected in GROUND_TRUTH.items():
        actual = actuals.get(label, 0.0)
        rows_out.append((label, float(expected), round(actual, 2), round(actual - expected, 2)))
    return rows_out


def render_report(args, parsed, mapping_summary, recon_rows) -> str:
    lines = []
    lines.append('# 5.6 dry-run 验收报告')
    lines.append('')
    lines.append(f'- 工作簿: `{args.workbook}`')
    lines.append(f'- 解析行数: {parsed.mapped_data.get("row_count", 0)}')
    lines.append(f'- 业务日期: {parsed.mapped_data.get("business_date")}')
    lines.append(f'- 质量状态: {parsed.status}')
    lines.append('')
    lines.append('## 映射规则覆盖')
    lines.append(f'- 总行数: {mapping_summary["total"]}')
    lines.append(f'- ready: {mapping_summary["ready"]}')
    lines.append(f'- needs_equipment_mapping: {mapping_summary["needs_equipment_mapping"]}')
    lines.append(f'- unresolved: {mapping_summary["unresolved"]}')
    if mapping_summary['unresolved_labels']:
        lines.append('  - 未解析 labels:')
        for label in mapping_summary['unresolved_labels']:
            lines.append(f'    - `{label}`')
    lines.append('')
    lines.append('## 事实底对账（单位：吨）')
    lines.append('| 口径 | 期望 | 实际 | 差额 | 状态 |')
    lines.append('| --- | --- | --- | --- | --- |')
    for label, expected, actual, diff in recon_rows:
        tolerance = max(expected * 0.05, 5)
        status = 'OK' if abs(diff) <= tolerance else 'FAIL'
        lines.append(f'| {label} | {expected:.1f} | {actual:.2f} | {diff:+.2f} | {status} |')
    lines.append('')
    issues = parsed.mapped_data.get('issues') or []
    if issues:
        lines.append('## 数据质量 issue')
        for item in issues:
            lines.append(f'- `{item.get("code")}` {item.get("message")}')
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workbook', type=Path, default=DEFAULT_DATA_DIR / SUMMARY_WORKBOOK)
    parser.add_argument('--report', type=Path, default=Path('tmp') / 'import_5_6_dry_run.md')
    args = parser.parse_args(argv)

    if not args.workbook.exists():
        print(f'[ERROR] workbook 不存在: {args.workbook}', file=sys.stderr)
        return 2

    frame = load_summary_sheet(args.workbook)
    parsed = parse_with_canonical_service(frame)
    rows = parsed.mapped_data.get('workshop_rows') or []
    mapping_summary = run_mapping_preview(rows)
    recon_rows = reconcile_against_truth(rows)
    report = render_report(args, parsed, mapping_summary, recon_rows)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding='utf-8')
    print(report)
    print(f'\n[OK] 报告已写入 {args.report}')

    failed = [item for item in recon_rows if abs(item[3]) > max(item[1] * 0.05, 5)]
    if failed or mapping_summary['unresolved'] > 2:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
