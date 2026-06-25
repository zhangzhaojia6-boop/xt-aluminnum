from __future__ import annotations

from pathlib import Path
from typing import Iterable

PROTECT_MARKERS = (
    "agent_communication",
    "daily_fact_bundle",
    "daily_report_history",
    "frontend/src/views/mobile/attendanceconfirm.vue",
    "frontend/src/views/mobile/coilentryworkbench.vue",
    "frontend/src/views/mobile/consumableentry.vue",
    "frontend/src/views/mobile/mobileentry.vue",
    "frontend/src/views/mobile/ocrcapture.vue",
    "frontend/src/views/mobile/shiftreportform.vue",
    "frontend/src/views/mobile/shiftreporthistory.vue",
    "frontend/src/views/mobile/unifiedentryform.vue",
    "frontend/src/views/entry/",
    "frontend/src/views/manage/coils/",
    "frontend/src/views/manage/live/",
    "frontend/src/views/manage/production/",
    "frontend/src/views/manage/today/",
    "operation_period",
    "mes_sync",
    "mes_",
    "backend/app/routers/mes.py",
    "backend/app/models/mes.py",
    "docs/mes-page-table-mapping.md",
    "docs/mes-xtmijd-alignment-matrix.md",
    "artifacts/gstack-mes-audit-20260617/mes-sqlserver/wms_stock.sample.json",
    "rag",
    "hermes",
    "audit",
    "dingtalk",
)

FREEZE_MARKERS = (
    "reference-command",
    "ui-reference",
    "/review/",
    "/mobile/",
    "legacy",
)

MERGE_MARKERS = (
    "daily_overview_builder",
    "dashboard_builder",
    "template_daily_report",
)


def classify_audit_item(path: str) -> dict[str, str]:
    clean = str(path).replace("\\", "/")
    lowered = clean.lower()
    if any(marker in lowered for marker in PROTECT_MARKERS):
        return {
            "path": clean,
            "classification": "protect",
            "action": "keep",
            "reason": "涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。",
        }
    if any(marker in lowered for marker in MERGE_MARKERS):
        return {
            "path": clean,
            "classification": "merge",
            "action": "merge_after_source_map",
            "reason": "属于报表加工层，可在 DailyFactBundle 稳定后逐步合并。",
        }
    if any(marker in lowered for marker in FREEZE_MARKERS):
        return {
            "path": clean,
            "classification": "freeze",
            "action": "freeze_and_observe",
            "reason": "疑似旧入口或参考资产，先冻结观察，不直接删除。",
        }
    return {
        "path": clean,
        "classification": "review",
        "action": "manual_review",
        "reason": "需要结合引用、路由、测试和生产访问再判断。",
    }


def render_diet_audit_report(paths: Iterable[str]) -> str:
    items = [classify_audit_item(path) for path in paths]
    lines = [
        "# 数据中枢减法瘦身审计报告",
        "",
        "日期：2026-06-25",
        "",
        "本报告只做分类和建议，不删除任何文件、表或生产数据。",
        "",
        "| 分类 | 动作 | 路径 | 原因 |",
        "|---|---|---|---|",
    ]
    for item in items:
        lines.append(f"| {item['classification']} | {item['action']} | `{item['path']}` | {item['reason']} |")
    lines.append("")
    lines.append("硬规则：本阶段没有直接删除动作。所有删除必须另开计划，并提供回滚办法。")
    return "\n".join(lines)


def _find_artifact_path(repo_root: Path, expected_relative_path: Path) -> str | None:
    exact_candidate = repo_root / expected_relative_path
    if exact_candidate.exists():
        return str(expected_relative_path).replace("\\", "/")

    parent = repo_root / expected_relative_path.parent
    if parent.exists():
        expected_name = expected_relative_path.name.casefold()
        for candidate in parent.iterdir():
            if candidate.is_file() and candidate.name.casefold() == expected_name:
                return str(expected_relative_path.parent / candidate.name).replace("\\", "/")

    for candidate in repo_root.glob("artifacts/**/*.json"):
        if candidate.is_file() and candidate.name.casefold() == expected_relative_path.name.casefold():
            return str(candidate.relative_to(repo_root)).replace("\\", "/")
    return None


def candidate_paths(repo_root: str | Path) -> list[str]:
    root = Path(repo_root)
    patterns = [
        "backend/app/models/**/*.py",
        "backend/app/services/**/*.py",
        "backend/app/adapters/**/*.py",
        "backend/app/tasks/*.py",
        "backend/app/routers/*.py",
        "frontend/src/views/**/*.vue",
        "frontend/src/reference-command/**/*",
        "docs/**/*.md",
    ]
    required_paths = [
        "backend/app/services/report/daily_fact_bundle.py",
        "backend/app/tasks/mes_sync.py",
        "backend/app/adapters/sqlserver_mes_adapter.py",
    ]
    result: list[str] = []
    for pattern in patterns:
        result.extend(str(path.relative_to(root)).replace("\\", "/") for path in root.glob(pattern) if path.is_file())

    artifact_path = _find_artifact_path(
        root,
        Path("artifacts/gstack-mes-audit-20260617/mes-sqlserver/WMS_Stock.sample.json"),
    )
    if artifact_path is not None:
        result.append(artifact_path)

    for relative_path in required_paths:
        if (root / relative_path).exists():
            result.append(relative_path)

    return sorted(set(result))
