from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.legacy_data_profile_service import (
    classify_legacy_file,
    profile_historical_directory,
    profile_historical_path,
)


def test_classify_legacy_file_detects_daily_production() -> None:
    assert classify_legacy_file("鑫泰每日产量新48(1).xls") == "daily_production_report"


def test_classify_legacy_file_detects_contract_report() -> None:
    assert classify_legacy_file("河南鑫泰合同报表_39550_949(1).xlsx") == "contract_report"


def test_classify_legacy_file_detects_yield_rate_matrix() -> None:
    assert classify_legacy_file("4月份各车间成品率.xlsx") == "yield_rate_matrix"


def test_classify_legacy_file_detects_energy_usage_report() -> None:
    assert classify_legacy_file("4月份各车间能耗统计表.xls") == "energy_usage_report"


def test_classify_legacy_file_detects_gas_usage_report() -> None:
    assert classify_legacy_file("4月份各车间天然气用量统计表.xls") == "gas_usage_report"


def test_classify_legacy_file_detects_daily_gas_usage_report() -> None:
    assert classify_legacy_file("每日气耗.xls") == "gas_usage_report"


def test_classify_legacy_file_detects_consumable_usage_report() -> None:
    assert classify_legacy_file("耗材表.xls") == "consumable_usage_report"


def test_classify_legacy_file_detects_utility_power_report() -> None:
    assert classify_legacy_file("园区电+新厂电.xls") == "utility_power_report"


def test_classify_legacy_file_detects_average_daily_report() -> None:
    assert classify_legacy_file("2026-5-5_日均报表.xls") == "average_daily_report"


def test_classify_legacy_file_detects_park_cutting_transfer_report() -> None:
    assert classify_legacy_file("转 园区剪切_69833_644.xls") == "park_cutting_transfer_report"


def test_classify_legacy_file_detects_shipping_image() -> None:
    assert classify_legacy_file("微信图片_20260404090555_292_22.png") == "shipping_image_capture"


def test_profile_historical_path_profiles_xlsx(tmp_path: Path) -> None:
    path = tmp_path / "鑫泰每日产量测试.xlsx"
    pd.DataFrame([{"车间": "铸锭", "日产量": 123.4}]).to_excel(path, index=False)

    payload = profile_historical_path(path)

    assert payload["status"] == "profiled"
    assert payload["kind"] == "daily_production_report"
    assert payload["sheets"][0]["columns"] == ["车间", "日产量"]


def test_profile_historical_path_blocks_xls_without_xlrd(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "历史日报.xls"
    path.write_bytes(b"not-a-real-xls")

    monkeypatch.setattr(
        "app.services.legacy_data_profile_service.importlib.import_module",
        lambda name: (_ for _ in ()).throw(ModuleNotFoundError()) if name == "xlrd" else None,
    )

    payload = profile_historical_path(path)

    assert payload["status"] == "blocked"
    assert payload["issues"][0]["code"] == "xlrd_missing"


def test_profile_historical_directory_counts_items(tmp_path: Path) -> None:
    workbook = tmp_path / "河南鑫泰合同报表.xlsx"
    image = tmp_path / "微信图片.png"
    pd.DataFrame([{"合同量": 10}]).to_excel(workbook, index=False)
    image.write_bytes(b"fake-image")

    payload = profile_historical_directory(tmp_path)

    assert payload["total_files"] == 2
    assert payload["kind_counts"]["contract_report"] == 1
    assert payload["kind_counts"]["shipping_image_capture"] == 1


def test_profile_historical_directory_supports_recursive_scan(tmp_path: Path) -> None:
    day_dir = tmp_path / "5.5"
    day_dir.mkdir()
    workbook = day_dir / "鑫泰每日产量5月.xlsx"
    pd.DataFrame([{"车间": "铸锭", "日产量": 123.4}]).to_excel(workbook, index=False)

    shallow = profile_historical_directory(tmp_path)
    recursive = profile_historical_directory(tmp_path, recursive=True)

    assert shallow["total_files"] == 0
    assert recursive["total_files"] == 1
    assert recursive["items"][0]["relative_path"] == "5.5/鑫泰每日产量5月.xlsx"
    assert recursive["items"][0]["kind"] == "daily_production_report"


def test_profile_historical_path_adds_contract_preview_for_contract_report(tmp_path: Path) -> None:
    workbook = tmp_path / "河南鑫泰合同报表.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                ["河南鑫泰合同报表", None],
                ["4月8日 铸锭合同", None],
                ["当日合同", "12"],
                ["月累计合同", "34"],
                ["当日投料", "10"],
                ["坯总量", "20"],
            ]
        ).to_excel(writer, sheet_name="4月8日 铸锭", header=False, index=False)

    payload = profile_historical_path(workbook)

    assert payload["kind"] == "contract_report"
    assert payload["sheets"][0]["contract_preview"]["delivery_scope"] == "workshop:foundry"
    assert payload["sheets"][0]["contract_preview"]["daily_contract_weight"] == 12.0
    assert payload["sheets"][0]["contract_preview"]["month_to_date_input_weight"] == 20.0


def test_profile_historical_path_adds_yield_matrix_preview_for_yield_rate_matrix(tmp_path: Path) -> None:
    workbook = tmp_path / "4月份各车间成品率.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                ["4月8日各车间成品率", "1450", "2050", "公司"],
                ["项目", "成品率", "成品率", "成品率"],
                ["成品率", "95.2%", "96.8%", "96.0%"],
                ["M", "88", None, None],
                ["P", "92", None, None],
            ]
        ).to_excel(writer, sheet_name="4月8日", header=False, index=False)

    payload = profile_historical_path(workbook)

    assert payload["kind"] == "yield_rate_matrix"
    assert payload["sheets"][0]["yield_matrix_preview"]["company_total_yield"] == 96.0
    assert payload["sheets"][0]["yield_matrix_preview"]["workshop_yields"]["cold_roll_1450"] == 95.2
    assert payload["sheets"][0]["yield_matrix_preview"]["mp_targets"]["M"] == 88.0


def test_profile_historical_path_adds_daily_production_preview(tmp_path: Path) -> None:
    workbook = tmp_path / "鑫泰每日产量5月.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                ["河南鑫泰铝业生产系统综合日报表               2026年5月3日", None, None, None, None, None, None, None, None, None, None, None],
                ["车间   项目", None, "投料量", None, "日产量", None, "日均", "产生废料", None, "月成品率", "指标", "对比"],
                [None, None, "日合", "累计", "日合", "累计", None, "日合", "累计", None, None, None],
                ["铸轧", "铸二", 25, 63, 24.18, 61.86, None, 0.82, 1.14, 0.9819, 0.949, 0.0329],
            ]
        ).to_excel(writer, sheet_name="综合报表", header=False, index=False)

    payload = profile_historical_path(workbook)

    assert payload["kind"] == "daily_production_report"
    assert payload["sheets"][0]["daily_production_preview"]["business_date"] == "2026-05-03"
    assert payload["sheets"][0]["daily_production_preview"]["daily_output_tons"] == 24.18
    assert payload["sheets"][0]["daily_production_preview"]["source_unit"] == "t"
