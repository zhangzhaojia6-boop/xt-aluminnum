# `D:\鑫泰报表` Read-Only Source Audit - 2026-05-06

## Scope

- Source folder: `D:\鑫泰报表`
- Scan mode: recursive
- Sampling limit: first 2 sheets, first 2 rows per workbook
- Database writes: none
- Import batches created: none

This audit only classifies and samples historical report files before any data is applied to `数据中枢`.

## Audit Command

PowerShell stdin converted the Chinese path to `????`, so the live audit used a Unicode-escaped path in the Python probe:

```powershell
@'
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd() / "backend"))
from app.services.legacy_data_profile_service import profile_historical_directory

base = Path("D:/\u946b\u6cf0\u62a5\u8868")
payload = profile_historical_directory(base, recursive=True, max_sheets=2, max_rows=2)
print(payload["total_files"], payload["kind_counts"], payload["blocked_files"])
'@ | python -
```

## Result

- Total files: 307
- Profiled files: 270
- Skipped unsupported files: 37
- Blocked files: 0
- Suffix counts: `.xls` 142, `.png` 92, `.xlsx` 36, `.txt` 27, `.json` 6, `.md` 3, `.docx` 1

| Kind | Count | Representative paths |
| --- | ---: | --- |
| `shipping_image_capture` | 92 | `4.20/_right_block.png`; `4.20/微信图片_20260421082646_5_381.png` |
| `energy_usage_report` | 31 | `4.20/4月份各车间能耗统计表.xls`; `4.22/铸三4月22日能耗表.xls` |
| `gas_usage_report` | 21 | `4.20/4月份各车间天然气用量统计表(7).xls`; `5.4/每日气耗.xls` |
| `daily_production_report` | 20 | `4.20/鑫泰每日产量4月20日.xls`; `4.23/鑫泰每日产量(1).xls` |
| `average_daily_report` | 19 | `发领导/日均报表.xls`; `输出skill/2026-4-16_日均报表.xls` |
| `utility_power_report` | 19 | `4.20/园区电+新厂电.xls`; `4.24/园区电+新厂电.xls` |
| `contract_report` | 18 | `4.20/河南鑫泰合同报表_36838_541.xlsx`; `4.24/河南鑫泰合同报表_02721_523.xlsx` |
| `yield_rate_matrix` | 18 | `4.20/4月份各车间成品率(20).xlsx`; `4.24/4月份各车间成品率(25).xlsx` |
| `consumable_usage_report` | 17 | `4.20/耗材表.xls`; `4.25/耗材表.xls` |
| `park_cutting_transfer_report` | 14 | `4.20/转 园区剪切_69833_644.xls`; `4.24/转 园区剪切_53578_710.xls` |
| `unknown` | 38 | See unresolved list below |

## Unresolved Items

Most unknown items are intentionally skipped side artifacts:

- `.txt`: 27 files, mostly daily scratch notes such as `4.22/新建 Text Document.txt`
- `.json`: 6 files, `输出skill/delivery_override_*.json`
- `.md`: 3 files, such as `4.20/4月20日日报.md`
- `.docx`: 1 file, `4.30/4月份坯料产量扣除(3).docx`

Only one workbook remains unclassified:

- `发领导/粉红表.xls`
  - Sheet preview: `能耗`
  - Header signals: `日产量`, `月产量`, `电耗`, `天燃气/气耗`, `液化气吨耗`, `钛丝吨耗`, `液压油`, `齿轮油`
  - Treatment: keep out of automated import until its business role is confirmed as either a leader summary, energy matrix, or consumable/oil matrix.

## Import Readiness Notes

- Current audit proves the runtime can read legacy `.xls` and `.xlsx` sources in this folder; no `xlrd_missing` or read blocker appeared.
- `daily_production_report`, `contract_report`, and `yield_rate_matrix` already have the strongest parser anchors and should be first candidates for dry-run mapping.
- Energy, gas, utility power, consumable, average daily, and park-cutting transfer reports are now classified but still need field-level mapping tests before import.
- Images remain `shipping_image_capture`; they require OCR/manual structuring and should not be auto-imported as structured rows.
- Next step before any database write: build a dry-run mapper for one locked report date, normalize units explicitly, emit row-level validation issues, then import only after review approval.

## Verification

- `python -m pytest backend/tests/test_legacy_data_profile_service.py -q` -> 17 passed
- Live read-only audit: 307 files scanned, 0 blocked, no database writes
