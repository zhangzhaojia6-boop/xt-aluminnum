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
