# Xintaily Daily Report Manual Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `xintaily-mes-daily-report` generate daily total reports and workshop reports that match the actual manual/statistical daily report, while still using MES and data-hub sources as traceable evidence.

**Architecture:** Add a small facts pipeline in front of the skill renderer: parse the structured manual daily workbook, manual total-report target text, or data-hub owner facts first, fetch direct MES/WMS facts second, then reconcile and render. Treat MES process rows as process evidence unless a field has already been proven to match the manual report field. Keep every value source-tagged so mismatches are visible instead of silently patched.

**Tech Stack:** Python 3, pandas/xlrd for `.xls`, pymssql for MES SQL Server read-only queries, existing FastAPI/SQLAlchemy report facts layer for data-hub facts, local skill files under `C:\Users\xt\.agents\skills\xintaily-mes-daily-report`.

---

## Evidence From 2026-06-19

Source workbook: `C:\Users\xt\Downloads\鑫泰每日产量6月 (2).xls`

Source text: user's 2026-06-19 workshop messages and final 2026-06-19 total daily report text in this thread.

The previous generated report was a direct-MES version. The workbook and text show the real final report is a mixed-source report:

| Field | Manual/statistical value | Direct MES value generated earlier | Difference | Root cause |
| --- | ---:| ---:| ---:| --- |
| 成品库入库 | 382.208 | 382.208 | 0 | WMS 入库口径 matches manual. Keep direct WMS. |
| 成品库发货 | 185.933 | 185.933 | 0 | WMS 出库口径 matches manual. Keep direct WMS. |
| 铸二日产量 | 47.23 | 47.235 | +0.005 | Daily MES material close enough, but output should use manual/data-hub final value. |
| 铸二月累计 | 788.95 | 870.552 | +81.602 | MES material month status/time policy does not match final statistical workbook. |
| 铸三日产量 | 56.29 | 23.308 | -32.982 | MES material `ProductionDate + Status` does not match final statistical output. |
| 热轧日产量 | 250.67 | 132.13 | -118.54 | MES material record is not the same as hot rolling final workshop daily output. |
| 1650日产量 | 130.01 | 166.417 | +36.407 | MES cold rolling `EndWeight` is total process output; manual field is 成品 only. |
| 1850日产量 | 45.75 | 0 | -45.75 | Current MES path did not find 1850 machine rows; manual workbook/text has the final value. |
| 2050日产量 | 80.40 | 207.290 | +126.890 | MES cold rolling `EndWeight` includes non-final categories; manual field is 成品 only. |
| 在线退火合计 | 374.64 | 328.38 | -46.26 | MES path missed 新厂南线 and under-counted 园区北线. |
| 拉矫下机 | 64.30 | 43.20 | -21.10 | MES `Process=拉矫` did not cover all manual shift output. |
| 园区剪切包装 | 144.352 | 171.513 | +27.161 | MES 包装录入 and manual 园区剪切 packaging are different口径. |
| 园区剪切入库 | 164.994 | 145.769 | -19.225 | Manual uses workshop finished/statistical inbound, not just canonicalized WMS inbound. |

## Manual Total Report Acceptance Target

The final total report must be checked against the user's 2026-06-19 manual total-report text, not only against workshop snippets.

Use these target values for 2026-06-19 acceptance:

| Field | Target |
| --- | ---: |
| 车间总产量日合计 | 366t |
| 外加工日合计 | 31t |
| 车间总产量比昨日 | +125t |
| 车间总产量月累计 | 5971t |
| 外加工月累计 | 370t |
| 铸轧分厂日产量 / 月累计 | 104t / 1662t |
| 铸锭日产量 / 月累计 | 261t / 5576t |
| 热轧日产量 / 月累计 | 251t / 5230t |
| 1650日产量 / 月累计 / 日道次 / 月道次 | 130t / 2819t / 67 / 969 |
| 1850日产量 / 月累计 / 日道次 / 月道次 | 46t / 816t / 33 / 418 |
| 2050日产量 / 月累计 / 日道次 / 月道次 | 80t / 2422t / 58 / 1404 |
| 轧机日产量 / 月累计 / 日道次 / 月道次 | 256t / 6056t / 158 / 2791 |
| 在线退火日产量 / 月累计 | 375t / 6274t |
| 拉矫日产量 / 月累计 | 64t / 2677t |
| 精整日产量 / 月累计 | 37t / 1592t |
| 剪切日产量 / 月累计 | 144t / 1609t |
| 彩涂日产量 / 月累计 | 0t / 0t |
| 回收日产量 / 月累计 | 67t / 1332t |
| 大修磨辊日 / 月 | 10根 / 172根 |
| 当天在制料 | 1189t |
| 1650/2050冷轧在制 | 522.5t |
| 1850冷轧在制 | 7.5t |
| 铣床在制 | 0t |
| 退火分厂在制 | 142.5t |
| 退火分厂在制拆分 | 新厂北线109.5t, 新厂南线16.5t, 园区退火16.5t |
| 精整分厂在制 | 516.5t |
| 精整分厂在制拆分 | 拉矫378t, 精整95.5t, 园区精整43t |
| 热轧中厚板剪切 / 彩涂在制 | 0t / 0t |
| 全厂高压总用电量 / 分项用电 | 146500度 / 144993度 |
| 全厂燃气合计 | 50578m³ |
| 入库成品日合计 / 寄存 / 月累计 | 366t / 201t / 5971t |
| 当天接合同 / 热轧合同 | 10t / 10t |
| 冷轧日投料 / 2050投 / 1850投 / 外加工 | 505t / 469t / 6t / 30t |
| 中厚板 | 0t |
| 总余合同量 / 比昨日 | 2320t / -412t |
| 日成品率 / 比昨日 | 84.87% / -1.22% |
| 热轧成品率 / 比昨日 | 84.95% / +1.01% |
| 月成品率 | 85.97% |
| 铸轧 / 普板卷 / 热轧月成品率 | 92.06% / 92.06% / 84.51% |
| 电费 / 气费 / 已核合计 | 11.72万元 / 18.21万元 / 29.93万元 |
| 成本折算重量 / 吨成本 | 366.210t / 817元/t |

Acceptance rule:
- Numeric comparison should use exact decimal facts before rounding.
- Text rendering should round the same way as the manual report: most production values in the total paragraph are whole tons, while cost uses `366.210吨` and `817元/吨`.
- If a generated value differs from this table, the reconciliation output must say which source won and why.

## Final Source Priority

Use this priority for final rendered daily report values:

1. **Manual structured report / data-hub owner daily facts**: final workshop output, monthly output, pass counts, electricity/gas consumption, unit consumption, notes, outages, furnace counts, and workshop-specific template fields.
2. **Direct WMS from MES SQL Server**: 成品库入库 and 发货, because 2026-06-19 matches exactly.
3. **Direct MES process/material rows**: trace, cross-check, and fallback only for fields proven to align. Do not use direct MES process throughput as final report output for cold rolling, online anneal, hot rolling, cast rolling monthly totals, 拉矫, 精整, or 园区剪切 without a matching manual field rule.
4. **Missing**: if a field is absent from manual/data-hub and not proven from MES, render `缺失`, not guessed MES throughput.

## Files

- Modify: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\SKILL.md`
- Modify: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\business-time-and-metrics.md`
- Modify: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\direct-mes-source-map.md`
- Modify: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\workshop-report-templates.md`
- Create: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\manual-alignment-source-priority.md`
- Create: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\2026-06-19-manual-reconciliation.md`
- Create: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\2026-06-19-total-report-target.md`
- Create: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\2026-06-19-total-report-target.json`
- Modify: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\fetch_direct_mes_daily.py`
- Create: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\extract_manual_daily_facts.py`
- Create: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\build_aligned_daily_report.py`
- Create: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\check_total_report_alignment.py`
- Mirror after changes: `C:\Users\xt\.codex\skills\xintaily-mes-daily-report\...`
- Optional app integration later: `D:\zzj Claude code\aluminum-bypass\backend\app\services\report\template_daily_fact_sources.py`
- Optional app tests later: `D:\zzj Claude code\aluminum-bypass\backend\tests\test_template_daily_fact_sources.py`

---

### Task 1: Capture The 2026-06-19 Alignment Baseline

**Files:**
- Create: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\2026-06-19-manual-reconciliation.md`
- Create: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\manual-alignment-source-priority.md`
- Create: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\2026-06-19-total-report-target.md`
- Create: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\2026-06-19-total-report-target.json`

- [ ] **Step 1: Write the reconciliation reference**

Create `2026-06-19-manual-reconciliation.md` with this content:

```markdown
# 2026-06-19 Manual Reconciliation

Manual source:
- `C:\Users\xt\Downloads\鑫泰每日产量6月 (2).xls`
- User-provided workshop daily text for 2026-06-19

Known exact matches:
- 成品库入库: manual 382.208t = WMS_InStock 382.208t
- 成品库发货: manual 185.933t = WMS_OutStockDetail 185.933t
- 铸二日产量: manual 47.23t ~= MES_Material 47.235t

Known non-matches:
- Cold rolling direct MES EndWeight is process output, not final 成品 output.
- 1850 is missing from the current MES process path for 2026-06-19.
- Online anneal direct MES misses 新厂南线 and under-counts 园区北线.
- 铸二/铸三/热轧 monthly MES_Material totals do not match the final workbook monthly totals.
- 园区剪切 packaging/inbound/report fields are not the same as direct MES 包装录入 or WMS 入库.

Rule:
Final rendered report values must prefer manual workbook or data-hub owner facts for workshop output, pass count, energy, gas, and line-specific templates. MES/WMS remains evidence and fallback only where proven.
```

- [ ] **Step 2: Write the total-report target reference**

Create `2026-06-19-total-report-target.md`:

```markdown
# 2026-06-19 Total Report Target

This is the manual total daily report acceptance target supplied by the user.

The generated total report must align with these facts:

- 车间总产量日合计: 366t
- 外加工日合计: 31t
- 车间总产量比昨日: +125t
- 车间总产量月累计: 5971t
- 外加工月累计: 370t
- 铸轧分厂: 日产量104t, 月累计1662t, 开机5条
- 铸锭车间: 日产量261t, 月累计5576t
- 热轧车间: 日产量251t, 月累计5230t
- 1650: 日产量130t, 月累计2819t, 日道次67, 月道次969
- 1850: 日产量46t, 月累计816t, 日道次33, 月道次418
- 2050: 日产量80t, 月累计2422t, 日道次58, 月道次1404
- 轧机: 日产量256t, 月累计6056t, 日道次158, 月道次2791
- 在线退火: 日产量375t, 月累计6274t
- 拉矫: 日产量64t, 月累计2677t
- 精整: 日产量37t, 月累计1592t
- 剪切: 日产量144t, 月累计1609t
- 彩涂: 日产量0t, 月累计0t
- 回收: 日产量67t, 月累计1332t
- 大修磨辊: 日10根, 月172根
- 在制料: 总计1189t, 1650/2050冷轧522.5t, 1850冷轧7.5t, 铣床0t
- 退火在制: 合计142.5t, 新厂北线109.5t, 新厂南线16.5t, 园区退火16.5t
- 精整在制: 合计516.5t, 拉矫378t, 精整95.5t, 园区精整43t, 热轧中厚板剪切0t, 彩涂0t
- 高压用电: 总计146500度, 分项用电144993度
- 燃气: 总计50578m³
- 入库成品: 日合计366t, 寄存201t, 月累计5971t
- 合同: 当天接合同10t, 其中热轧10t, 总余合同2320t, 比昨日-412t
- 投料: 冷轧日投料505t, 2050投469t, 1850投6t, 外加工30t, 中厚板0t
- 成品率: 日成品率84.87%, 热轧成品率84.95%, 月成品率85.97%
- 月成品率拆分: 铸轧92.06%, 普板卷92.06%, 热轧84.51%
- 成本: 电费11.72万元, 气费18.21万元, 已核29.93万元, 折算重量366.210t, 吨成本817元/t

Rendering rule:
- The final text may use the exact manual wording or equivalent wording.
- Numbers must match after the same rounding policy.
- Missing fields must be printed as `缺失`; do not fill them from an unverified MES process value.
```

- [ ] **Step 3: Write the machine-checkable target JSON**

Create `2026-06-19-total-report-target.json`:

```json
{
  "date": "2026-06-19",
  "total_output_daily_t": 366,
  "external_processing_daily_t": 31,
  "total_output_delta_t": 125,
  "total_output_month_t": 5971,
  "external_processing_month_t": 370,
  "cast_rolling": {"running_lines": 5, "daily_t": 104, "month_t": 1662},
  "foundry": {"daily_t": 261, "month_t": 5576},
  "hot_rolling": {"daily_t": 251, "month_t": 5230},
  "cold_1650": {"daily_t": 130, "month_t": 2819, "pass_daily": 67, "pass_month": 969},
  "cold_1850": {"daily_t": 46, "month_t": 816, "pass_daily": 33, "pass_month": 418},
  "cold_2050": {"daily_t": 80, "month_t": 2422, "pass_daily": 58, "pass_month": 1404},
  "rolling_total": {"daily_t": 256, "month_t": 6056, "pass_daily": 158, "pass_month": 2791},
  "online_anneal": {"daily_t": 375, "month_t": 6274},
  "straightening": {"daily_t": 64, "month_t": 2677},
  "finishing": {"daily_t": 37, "month_t": 1592},
  "shearing": {"daily_t": 144, "month_t": 1609},
  "coating": {"daily_t": 0, "month_t": 0},
  "recycling": {"daily_t": 67, "month_t": 1332},
  "roll_grinding": {"daily_count": 10, "month_count": 172},
  "wip": {
    "total_t": 1189,
    "cold_1650_2050_t": 522.5,
    "cold_1850_t": 7.5,
    "milling_t": 0,
    "anneal_total_t": 142.5,
    "anneal_new_north_t": 109.5,
    "anneal_new_south_t": 16.5,
    "anneal_park_t": 16.5,
    "finishing_total_t": 516.5,
    "straightening_t": 378,
    "finishing_t": 95.5,
    "park_finishing_t": 43,
    "hot_plate_shearing_t": 0,
    "coating_t": 0
  },
  "energy": {
    "high_voltage_total_kwh": 146500,
    "line_item_kwh": 144993,
    "gas_total_m3": 50578,
    "electricity_fee_10k_cny": 11.72,
    "gas_fee_10k_cny": 18.21,
    "verified_cost_10k_cny": 29.93,
    "cost_weight_t": 366.210,
    "cost_cny_per_t": 817
  },
  "finished_goods": {"inbound_daily_t": 366, "consigned_daily_t": 201, "inbound_month_t": 5971},
  "contracts": {
    "new_contract_daily_t": 10,
    "hot_rolling_contract_daily_t": 10,
    "cold_feed_daily_t": 505,
    "cold_2050_feed_t": 469,
    "cold_1850_feed_t": 6,
    "external_processing_feed_t": 30,
    "medium_plate_t": 0,
    "remaining_contract_t": 2320,
    "remaining_contract_delta_t": -412
  },
  "yield": {
    "daily_percent": 84.87,
    "daily_delta_percent": -1.22,
    "hot_rolling_percent": 84.95,
    "hot_rolling_delta_percent": 1.01,
    "month_percent": 85.97,
    "cast_rolling_month_percent": 92.06,
    "plate_coil_month_percent": 92.06,
    "hot_rolling_month_percent": 84.51
  }
}
```

- [ ] **Step 4: Write the source priority reference**

Create `manual-alignment-source-priority.md`:

```markdown
# Manual Alignment Source Priority

## Final Value Priority

1. Manual daily workbook / data-hub owner daily facts.
2. Direct WMS facts for 成品库入库 and 发货.
3. Direct MES process/material facts only where a field is proven aligned.
4. `缺失`.

## Field Rules

| Field group | Final source | MES use |
| --- | --- | --- |
| 总日报车间产量、月累计、道次 | manual workbook or data-hub owner daily | trace only unless exact field mapping is proven |
| 冷轧 1650/1850/2050 产量、道次、成品/中退/开坯、电耗 | manual workbook or data-hub owner daily | trace only unless final category mapping exists |
| 在线退火新厂南线/北线、园区北线、电耗 | manual workbook or data-hub owner daily | trace only |
| 铸二/铸三/热轧产量和月累计 | manual workbook or data-hub owner daily | audit only until month status/time matches |
| 园区剪切飞剪、重卷、包装、入库、退火板、吨耗 | manual workbook/text or data-hub owner daily | trace only |
| 成品库入库、发货 | direct WMS SQL Server | final source |
| 在制料 | direct MES current WIP snapshot | final source unless manual override exists |
| 高压总用电、分项用电、燃气、吨耗、成本 | data-hub energy/inner-office facts or manual workbook | MES is not final source |
| 合同、投料、总余合同量 | data-hub owner daily or manually verified MES contract pages | MES trace only until page/table mapping is proven |
| 成品率 | data-hub final daily report facts or manual workbook | MES raw values are not enough |

Do not use MES process throughput as a final report value just because it has the same workshop name.
```

- [ ] **Step 5: Verify references are readable**

Run:

```powershell
Get-Content 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\2026-06-19-manual-reconciliation.md'
Get-Content 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\manual-alignment-source-priority.md'
Get-Content 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\2026-06-19-total-report-target.md'
Get-Content 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\2026-06-19-total-report-target.json'
```

Expected: all files print without mojibake.

---

### Task 2: Add Manual Workbook Fact Extraction

**Files:**
- Create: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\extract_manual_daily_facts.py`

- [ ] **Step 1: Write the extractor**

Create `extract_manual_daily_facts.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _num(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() in {"", "/"}:
        return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _cell(df: pd.DataFrame, row_1: int, col_1: int) -> Any:
    value = df.iat[row_1 - 1, col_1 - 1]
    return None if pd.isna(value) else value


def extract_manual_daily_facts(path: str | Path) -> dict[str, Any]:
    df = pd.read_excel(path, sheet_name=0, header=None, dtype=object)
    return {
        "source_path": str(path),
        "report_title": str(_cell(df, 1, 1) or ""),
        "values": {
            "foundry_daily": _num(_cell(df, 4, 5)),
            "foundry_month": _num(_cell(df, 4, 6)),
            "cast_2_daily": _num(_cell(df, 5, 5)),
            "cast_2_month": _num(_cell(df, 5, 6)),
            "cast_3_daily": _num(_cell(df, 6, 5)),
            "cast_3_month": _num(_cell(df, 6, 6)),
            "hot_roll_daily": _num(_cell(df, 11, 5)),
            "hot_roll_month": _num(_cell(df, 11, 6)),
            "cold_1650_daily": _num(_cell(df, 52, 2)),
            "cold_1650_month": _num(_cell(df, 52, 3)),
            "cold_1650_pass_daily": _num(_cell(df, 52, 4)),
            "cold_1650_pass_month": _num(_cell(df, 52, 5)),
            "cold_1850_daily": _num(_cell(df, 53, 2)),
            "cold_1850_month": _num(_cell(df, 53, 3)),
            "cold_1850_pass_daily": _num(_cell(df, 53, 4)),
            "cold_1850_pass_month": _num(_cell(df, 53, 5)),
            "cold_2050_daily": _num(_cell(df, 54, 2)),
            "cold_2050_month": _num(_cell(df, 54, 3)),
            "cold_2050_pass_daily": _num(_cell(df, 54, 4)),
            "cold_2050_pass_month": _num(_cell(df, 54, 5)),
            "online_anneal_daily": _num(_cell(df, 55, 2)),
            "online_anneal_month": _num(_cell(df, 55, 3)),
            "online_new_south_daily": _num(_cell(df, 25, 5)),
            "online_new_south_month": _num(_cell(df, 25, 6)),
            "online_new_north_daily": _num(_cell(df, 26, 5)),
            "online_new_north_month": _num(_cell(df, 26, 6)),
            "online_park_north_daily": _num(_cell(df, 28, 5)),
            "online_park_north_month": _num(_cell(df, 28, 6)),
            "straightening_daily": _num(_cell(df, 56, 2)),
            "straightening_month": _num(_cell(df, 56, 3)),
            "finishing_daily": _num(_cell(df, 57, 2)),
            "finishing_month": _num(_cell(df, 57, 3)),
            "park_shearing_daily": _num(_cell(df, 58, 2)),
            "park_shearing_month": _num(_cell(df, 58, 3)),
            "finished_inbound_daily": _num(_cell(df, 40, 29)),
            "finished_inbound_month": _num(_cell(df, 40, 30)),
            "finished_outbound_daily": _num(_cell(df, 40, 31)),
            "finished_outbound_month": _num(_cell(df, 40, 32)),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook")
    args = parser.parse_args()
    print(json.dumps(extract_manual_daily_facts(args.workbook), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the extractor on the provided workbook**

Run:

```powershell
python 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\extract_manual_daily_facts.py' 'C:\Users\xt\Downloads\鑫泰每日产量6月 (2).xls'
```

Expected key values:

```json
{
  "cast_2_daily": 47.23,
  "cast_3_daily": 56.29,
  "hot_roll_daily": 250.67,
  "cold_1650_daily": 130.01,
  "cold_1850_daily": 45.75,
  "cold_2050_daily": 80.4,
  "online_anneal_daily": 374.64,
  "finished_inbound_daily": 382.208,
  "finished_outbound_daily": 185.933
}
```

---

### Task 3: Keep Direct MES/WMS Fetching But Mark It As Evidence

**Files:**
- Modify: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\fetch_direct_mes_daily.py`

- [ ] **Step 1: Add source roles to direct MES output**

Add this constant:

```python
FINAL_SOURCE_KEYS = {
    "finished_inbound_daily": "final",
    "finished_outbound_daily": "final",
    "wip_current": "final_unless_manual_override",
    "packaging_by_workshop": "evidence",
    "process_by_workshop": "evidence",
    "material_by_workshop": "evidence",
}
```

- [ ] **Step 2: Add a reconciliation helper**

Add:

```python
def classify_difference(field: str, manual_value: float | None, mes_value: float | None) -> str:
    if manual_value is None:
        return "manual_missing"
    if mes_value is None:
        return "MES未取到对应工序"
    delta = round(float(mes_value) - float(manual_value), 3)
    if abs(delta) <= 0.01:
        return "已对齐"
    if field in {"finished_inbound_daily", "finished_outbound_daily"}:
        return "别名已归并后仍差异"
    if field.startswith(("cold_", "online_", "park_shearing", "straightening", "finishing")):
        return "口径不同：人工最终产量 / MES过程下机量"
    if field.startswith(("cast_", "hot_roll")):
        return "口径不同：人工综合报表 / MES坯料明细状态时间"
    return "口径不同：包装录入 / 成品调拨 / 成品库入库"
```

- [ ] **Step 3: Verify the helper with a quick Python command**

Run:

```powershell
$code = @'
from pathlib import Path
import importlib.util
path = Path(r'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\fetch_direct_mes_daily.py')
spec = importlib.util.spec_from_file_location('m', path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.classify_difference('cold_1650_daily', 130.01, 166.417) == '口径不同：人工最终产量 / MES过程下机量'
assert m.classify_difference('finished_inbound_daily', 382.208, 382.208) == '已对齐'
print('ok')
'@
$code | python -
```

Expected: `ok`.

---

### Task 4: Build The Aligned Daily Report Renderer And Target Checker

**Files:**
- Create: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\build_aligned_daily_report.py`
- Create: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\check_total_report_alignment.py`

- [ ] **Step 1: Write a minimal aligned builder**

Create:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from extract_manual_daily_facts import extract_manual_daily_facts


def pick(values: dict, key: str) -> str:
    value = values.get(key)
    if value is None:
        return "缺失"
    return f"{value:g}"


def render_total_report(manual_payload: dict) -> str:
    v = manual_payload["values"]
    rolling_daily = sum(float(v.get(k) or 0) for k in ("cold_1650_daily", "cold_1850_daily", "cold_2050_daily"))
    rolling_month = sum(float(v.get(k) or 0) for k in ("cold_1650_month", "cold_1850_month", "cold_2050_month"))
    rolling_pass_daily = sum(float(v.get(k) or 0) for k in ("cold_1650_pass_daily", "cold_1850_pass_daily", "cold_2050_pass_daily"))
    rolling_pass_month = sum(float(v.get(k) or 0) for k in ("cold_1650_pass_month", "cold_1850_pass_month", "cold_2050_pass_month"))
    return (
        "6月19日，按人工统计/数据中枢优先口径："
        f"铸锭{pick(v, 'foundry_daily')}吨，铸二{pick(v, 'cast_2_daily')}吨，铸三{pick(v, 'cast_3_daily')}吨，"
        f"热轧{pick(v, 'hot_roll_daily')}吨，1650为{pick(v, 'cold_1650_daily')}吨，"
        f"1850为{pick(v, 'cold_1850_daily')}吨，2050为{pick(v, 'cold_2050_daily')}吨，"
        f"轧机合计{rolling_daily:g}吨、{rolling_pass_daily:g}道；"
        f"在线退火{pick(v, 'online_anneal_daily')}吨，拉矫{pick(v, 'straightening_daily')}吨，"
        f"精整{pick(v, 'finishing_daily')}吨，园区剪切{pick(v, 'park_shearing_daily')}吨；"
        f"成品库入库{pick(v, 'finished_inbound_daily')}吨，发货{pick(v, 'finished_outbound_daily')}吨。"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manual-workbook", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    manual = extract_manual_daily_facts(Path(args.manual_workbook))
    if args.json:
        print(json.dumps(manual, ensure_ascii=False, indent=2))
    else:
        print(render_total_report(manual))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the aligned builder**

Run:

```powershell
python 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\build_aligned_daily_report.py' --manual-workbook 'C:\Users\xt\Downloads\鑫泰每日产量6月 (2).xls'
```

Expected output includes:

```text
铸二47.23吨，铸三56.29吨，热轧250.67吨，1650为130.01吨，1850为45.75吨，2050为80.4吨
```

- [ ] **Step 3: Write the total report alignment checker**

Create `check_total_report_alignment.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _flatten(prefix: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _flatten(f"{prefix}.{key}" if prefix else key, child, out)
    else:
        out[prefix] = value


def flatten(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    _flatten("", payload, out)
    return out


def close_enough(expected: Any, actual: Any) -> bool:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) <= 0.01
    return expected == actual


def compare_target(target: dict[str, Any], actual: dict[str, Any]) -> list[dict[str, Any]]:
    target_flat = flatten(target)
    actual_flat = flatten(actual)
    differences: list[dict[str, Any]] = []
    for key, expected in target_flat.items():
        actual_value = actual_flat.get(key)
        if not close_enough(expected, actual_value):
            differences.append({"field": key, "expected": expected, "actual": actual_value})
    return differences


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--actual", required=True)
    args = parser.parse_args()
    target = json.loads(Path(args.target).read_text(encoding="utf-8"))
    actual = json.loads(Path(args.actual).read_text(encoding="utf-8"))
    differences = compare_target(target, actual)
    result = {"ok": not differences, "differences": differences}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if differences:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the checker self-test against the 2026-06-19 target**

Run the checker with the target as both expected and actual. This proves the checker works before the real renderer is wired to every data source.

```powershell
python 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\check_total_report_alignment.py' `
  --target 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\2026-06-19-total-report-target.json' `
  --actual 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\2026-06-19-total-report-target.json'
```

Expected:

```json
{
  "ok": true,
  "differences": []
}
```

---

### Task 5: Update Skill Instructions To Prevent Wrong MES-Only Output

**Files:**
- Modify: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\SKILL.md`
- Modify: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\business-time-and-metrics.md`
- Modify: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\direct-mes-source-map.md`
- Modify: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\workshop-report-templates.md`

- [ ] **Step 1: Add the manual priority rule to `SKILL.md`**

Add under Overview:

```markdown
Important: final daily report output is not MES-only. For workshop final output, monthly totals, pass counts, energy, gas, and workshop template fields, prefer manual structured workbook or data-hub owner daily facts. Use direct MES process rows as trace evidence unless a field has a proven alignment rule.
```

- [ ] **Step 2: Add the new required reference**

Add to Required References:

```markdown
- `references/manual-alignment-source-priority.md`
- `references/2026-06-19-manual-reconciliation.md` when checking alignment against actual manual statistics
```

- [ ] **Step 3: Update workshop templates**

In the cold rolling section, add:

```markdown
For 1650/1850/2050, `日产量` is manual/data-hub 成品 output, not raw MES `EndWeight`. MES process rows can be used for trace and pass evidence only after category mapping separates 成品、中退、开坯.
```

In the online anneal section, add:

```markdown
Line values 新厂南线、新厂北线、园区北线 must come from manual/data-hub facts when MES process records miss a line.
```

In the billet section, add:

```markdown
MES_Material is audit evidence for 铸二、铸三、热轧. Final report output and month totals must use manual/data-hub final values unless MES monthly status/time policy has been reconciled for that date.
```

- [ ] **Step 4: Read the edited skill**

Run:

```powershell
Get-Content 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\SKILL.md'
```

Expected: the skill clearly says daily report output is not MES-only.

---

### Task 6: Mirror The Skill To The Codex Skill Directory

**Files:**
- Mirror source: `C:\Users\xt\.agents\skills\xintaily-mes-daily-report`
- Mirror target: `C:\Users\xt\.codex\skills\xintaily-mes-daily-report`

- [ ] **Step 1: Copy the updated skill**

Run:

```powershell
Copy-Item -Path 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\*' -Destination 'C:\Users\xt\.codex\skills\xintaily-mes-daily-report' -Recurse -Force
```

- [ ] **Step 2: Verify both skill files exist**

Run:

```powershell
Test-Path 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\SKILL.md'
Test-Path 'C:\Users\xt\.codex\skills\xintaily-mes-daily-report\SKILL.md'
```

Expected:

```text
True
True
```

---

### Task 7: Add Data-Hub Integration As The Next Stable Source

**Files:**
- Modify: `D:\zzj Claude code\aluminum-bypass\backend\app\services\report\template_daily_fact_sources.py`
- Test: `D:\zzj Claude code\aluminum-bypass\backend\tests\test_template_daily_fact_sources.py`

- [ ] **Step 1: Add a test that manual/data-hub facts beat MES**

Add this test:

```python
def test_manual_owner_daily_wins_over_mes_process_output(db):
    seed_owner_daily_payload(db, {
        "cold_1650_daily": 130.01,
        "cold_1850_daily": 45.75,
        "cold_2050_daily": 80.4,
    })
    seed_mes_process(db, workshop_name="2050车间", process_name="冷轧", device_name="1650冷轧（WAN）", output_weight_tons=166.417)
    seed_mes_process(db, workshop_name="2050车间", process_name="冷轧", device_name="2050冷轧（WAN）", output_weight_tons=207.29)

    facts = collect_template_daily_facts(db, target_date=date(2026, 6, 19))

    assert facts.values["cold_1650_daily"] == 130.01
    assert facts.values["cold_1850_daily"] == 45.75
    assert facts.values["cold_2050_daily"] == 80.4
    assert facts.sources["cold_1650_daily"]["source_type"] == "owner_daily"
```

- [ ] **Step 2: Run the test to see it fail**

Run:

```powershell
cd 'D:\zzj Claude code\aluminum-bypass\backend'
python -m pytest tests/test_template_daily_fact_sources.py::test_manual_owner_daily_wins_over_mes_process_output -q
```

Expected: FAIL until the source priority is implemented.

- [ ] **Step 3: Implement source priority in `template_daily_fact_sources.py`**

Add a priority helper:

```python
SOURCE_PRIORITY = {
    "owner_daily": 100,
    "manual_workbook": 95,
    "wms_direct": 90,
    "mes_verified": 70,
    "mes_evidence": 20,
}


def should_replace_source(existing: dict | None, new_source_type: str) -> bool:
    if existing is None:
        return True
    return SOURCE_PRIORITY.get(new_source_type, 0) >= SOURCE_PRIORITY.get(existing.get("source_type"), 0)
```

Use it inside the fact setter so owner/manual facts do not get overwritten by MES evidence.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
cd 'D:\zzj Claude code\aluminum-bypass\backend'
python -m pytest tests/test_template_daily_fact_sources.py -q
```

Expected: PASS.

---

### Task 8: Final Verification

**Files:**
- No new files unless a test fails.

- [ ] **Step 1: Run skill script checks**

Run:

```powershell
python 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\fetch_direct_mes_daily.py' --self-test
python 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\extract_manual_daily_facts.py' 'C:\Users\xt\Downloads\鑫泰每日产量6月 (2).xls'
python 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\build_aligned_daily_report.py' --manual-workbook 'C:\Users\xt\Downloads\鑫泰每日产量6月 (2).xls'
python 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\check_total_report_alignment.py' `
  --target 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\references\2026-06-19-total-report-target.json' `
  --actual 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\out\2026-06-19-aligned-facts.json'
```

Expected:

- fetch direct MES self-test passes.
- extracted facts include the 2026-06-19 manual values.
- aligned report uses manual/data-hub values for workshop output.
- total report alignment checker returns `"ok": true`.

- [ ] **Step 2: Run Python compile checks**

Run:

```powershell
python -m py_compile 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\fetch_direct_mes_daily.py'
python -m py_compile 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\extract_manual_daily_facts.py'
python -m py_compile 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\build_aligned_daily_report.py'
python -m py_compile 'C:\Users\xt\.agents\skills\xintaily-mes-daily-report\scripts\check_total_report_alignment.py'
```

Expected: no output and exit code 0.

- [ ] **Step 3: Re-run 2026-06-19 alignment**

Expected aligned facts:

```text
成品库入库 382.208
成品库发货 185.933
铸二 47.23
铸三 56.29
热轧 250.67
1650 130.01
1850 45.75
2050 80.4
在线退火 374.64
拉矫 64.3
精整 36.714
园区剪切 144.235 或 workshop text override 144.352
车间总产量日合计 366
外加工日合计 31
入库成品日合计 366
寄存 201
高压总用电 146500
燃气合计 50578
成本 817元/吨
```

For `园区剪切`, prefer user workshop text if present because the text has the detailed fields `飞剪/重卷/包装/退火板/合计`; otherwise use workbook row 58.

---

## Self-Review

Spec coverage:

- Compares manual statistics with generated MES-only data: covered in Evidence section.
- Finds root causes: covered in Evidence and source priority.
- Optimizes取数方案: covered by final source priority and tasks 2-7.
- Allows data-hub energy/owner facts: covered by Task 7.
- Avoids MES-only output: covered by Task 5.
- Keeps MES/WMS where correct: WMS inbound/outbound remain final source.

Placeholder scan:

- No placeholder red flags remain.

Type consistency:

- Manual extractor returns `{"values": {...}}`.
- Aligned builder reads the same shape.
- Source priority names are consistent: `owner_daily`, `manual_workbook`, `wms_direct`, `mes_verified`, `mes_evidence`.
