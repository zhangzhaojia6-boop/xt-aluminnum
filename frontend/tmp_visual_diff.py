from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageChops, ImageFilter, ImageStat


REFERENCE_UI_TARGET_IMAGE = "C:/Users/xt/Downloads/cb3b60f0-1a5d-43e4-94bc-9d4cf4274aa5.png"
DIFF_THRESHOLD_PERCENT = 10.0


@dataclass(frozen=True)
class TargetPanel:
    module_id: str
    title: str
    screenshot: str
    box: tuple[int, int, int, int]


TARGET_PANELS: tuple[TargetPanel, ...] = (
    TargetPanel("01", "系统总览主视图", "01-review-overview.png", (12, 8, 596, 283)),
    TargetPanel("02", "登录与角色入口", "02-login-role-handoff.png", (606, 8, 955, 283)),
    TargetPanel("03", "独立填报终端首页", "03-entry-terminal.png", (967, 8, 1307, 283)),
    TargetPanel("04", "填报流程页", "04-entry-flow.png", (1317, 8, 1660, 283)),
    TargetPanel("05", "工厂作业看板", "05-factory-board.png", (12, 291, 363, 523)),
    TargetPanel("06", "数据接入与字段映射中心", "06-admin-ingestion.png", (374, 291, 820, 523)),
    TargetPanel("07", "审阅中心", "07-review-tasks.png", (831, 291, 1244, 523)),
    TargetPanel("08", "日报与交付中心", "08-reports.png", (1254, 291, 1660, 523)),
    TargetPanel("09", "质量与告警中心", "09-quality.png", (12, 533, 407, 718)),
    TargetPanel("10", "成本核算与效益中心", "10-cost.png", (418, 533, 820, 718)),
    TargetPanel("11", "AI总大脑中心", "11-brain.png", (831, 533, 1248, 718)),
    TargetPanel("12", "系统运维与可观测", "12-admin-ops.png", (1258, 533, 1660, 718)),
    TargetPanel("13", "权限治理中心", "13-admin-governance.png", (12, 727, 407, 931)),
    TargetPanel("14", "主数据与模板中心", "14-admin-master.png", (418, 727, 764, 931)),
    TargetPanel("15", "响应式录入体验", "15-entry-responsive.png", (775, 727, 1249, 931)),
    TargetPanel("16", "路线图与下一步", "16-review-roadmap.png", (1258, 727, 1660, 931)),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare command pages with target reference panels.")
    parser.add_argument("--module", dest="module_id", default="", help="Only compare one module id, e.g. 01.")
    parser.add_argument("--threshold", dest="threshold_percent", type=float, default=DIFF_THRESHOLD_PERCENT)
    parser.add_argument("--target", default=os.environ.get("REFERENCE_UI_TARGET_IMAGE", REFERENCE_UI_TARGET_IMAGE))
    parser.add_argument("--screenshots", default=str(Path("tmp") / "visual-audit"))
    parser.add_argument("--out", default=str(Path("tmp") / "visual-audit" / "visual-diff-report.json"))
    parser.add_argument("--enforce", action="store_true", default=os.environ.get("VISUAL_DIFF_ENFORCE") == "1")
    return parser.parse_args()


def selected_panels(module_id: str) -> Iterable[TargetPanel]:
    wanted = module_id.strip()
    return (panel for panel in TARGET_PANELS if not wanted or panel.module_id == wanted)


def crop_reference(target: Image.Image, panel: TargetPanel, crop_dir: Path) -> Image.Image:
    crop = target.crop(panel.box).convert("RGB")
    crop_dir.mkdir(parents=True, exist_ok=True)
    crop.save(crop_dir / f"{panel.module_id}-{panel.title}.png")
    return crop


def normalize_generated(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = image.convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (244, 247, 251))
    left = (size[0] - image.width) // 2
    top = (size[1] - image.height) // 2
    canvas.paste(image, (left, top))
    return canvas


def diff_percent(reference: Image.Image, generated: Image.Image) -> float:
    diff = ImageChops.difference(reference, generated)
    stat = ImageStat.Stat(diff)
    mean = sum(stat.mean) / len(stat.mean)
    return round((mean / 255.0) * 100.0, 2)


def edge_mask(image: Image.Image) -> Image.Image:
    edges = image.convert("L").filter(ImageFilter.FIND_EDGES)
    return edges.point(lambda value: 255 if value > 18 else 0, mode="L")


def edge_diff_percent(reference: Image.Image, generated: Image.Image) -> float:
    diff = ImageChops.difference(edge_mask(reference), edge_mask(generated))
    stat = ImageStat.Stat(diff)
    return round((stat.mean[0] / 255.0) * 100.0, 2)


def content_occupancy(image: Image.Image) -> float:
    background = Image.new("RGB", image.size, (244, 247, 251))
    diff = ImageChops.difference(image.convert("RGB"), background)
    gray = diff.convert("L")
    mask = gray.point(lambda value: 255 if value > 10 else 0, mode="L")
    stat = ImageStat.Stat(mask)
    return round(stat.mean[0] / 255.0, 4)


def combined_diff(reference: Image.Image, generated: Image.Image) -> dict[str, float]:
    pixel = diff_percent(reference, generated)
    edge = edge_diff_percent(reference, generated)
    reference_occupancy = content_occupancy(reference)
    generated_occupancy = content_occupancy(generated)
    occupancy_delta = round(abs(reference_occupancy - generated_occupancy) * 100.0, 2)
    combined = round(max(pixel, edge, occupancy_delta), 2)
    return {
        "pixel_diff_percent": pixel,
        "edge_diff_percent": edge,
        "reference_content_occupancy": reference_occupancy,
        "generated_content_occupancy": generated_occupancy,
        "content_occupancy_delta_percent": occupancy_delta,
        "combined_diff_percent": combined,
    }


def compare_panel(panel: TargetPanel, target: Image.Image, screenshot_dir: Path, crop_dir: Path) -> dict[str, object]:
    screenshot_path = screenshot_dir / panel.screenshot
    reference = crop_reference(target, panel, crop_dir)
    if not screenshot_path.exists():
        return {
            "module_id": panel.module_id,
            "title": panel.title,
            "screenshot": str(screenshot_path),
            "threshold_percent": DIFF_THRESHOLD_PERCENT,
            "diff_percent": 100.0,
            "status": "fail",
            "error": "missing screenshot",
        }

    generated = normalize_generated(Image.open(screenshot_path), reference.size)
    metrics = combined_diff(reference, generated)
    diff = metrics["combined_diff_percent"]
    return {
        "module_id": panel.module_id,
        "title": panel.title,
        "target_crop": str(crop_dir / f"{panel.module_id}-{panel.title}.png"),
        "screenshot": str(screenshot_path),
        "threshold_percent": DIFF_THRESHOLD_PERCENT,
        "diff_percent": diff,
        **metrics,
        "status": "pass" if diff <= DIFF_THRESHOLD_PERCENT else "fail",
        "error": "" if diff <= DIFF_THRESHOLD_PERCENT else f"diff {diff}% exceeds threshold",
    }


def main() -> int:
    args = parse_args()
    target_path = Path(args.target)
    screenshot_dir = Path(args.screenshots)
    out_path = Path(args.out)
    crop_dir = out_path.parent / "target-crops"
    threshold = float(args.threshold_percent)

    target = Image.open(target_path).convert("RGB")
    rows = []
    for panel in selected_panels(args.module_id):
        row = compare_panel(panel, target, screenshot_dir, crop_dir)
        row["threshold_percent"] = threshold
        row["status"] = "pass" if float(row["diff_percent"]) <= threshold else "fail"
        if row["status"] == "fail" and not row.get("error"):
            row["error"] = f"diff {row['diff_percent']}% exceeds threshold"
        rows.append(row)

    failed = [row for row in rows if row["status"] != "pass"]
    report = {
        "target_image": str(target_path),
        "screenshot_dir": str(screenshot_dir),
        "threshold_percent": threshold,
        "module_id": args.module_id or "all",
        "enforced": bool(args.enforce),
        "summary": {
            "total": len(rows),
            "failed": len(failed),
            "max_diff_percent": max((float(row["diff_percent"]) for row in rows), default=0.0),
        },
        "results": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report["summary"], ensure_ascii=False))
    if args.enforce and failed:
        for row in failed:
            print(f"{row['module_id']} {row['title']}: {row['error']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
