from __future__ import annotations

from pathlib import Path
from typing import Iterable

PROTECT_MARKERS = (
    "/manage/today",
    "/manage/live",
    "/manage/production",
    "/manage/coils",
    "/entry/*",
    "agent_communication",
    "daily_fact_bundle",
    "daily_report_history",
    "frontend/src/views/mobile/attendanceconfirm.vue",
    "frontend/src/views/mobile/coilentryworkbench.vue",
    "frontend/src/views/mobile/consumableentry.vue",
    "frontend/src/views/mobile/mobileentry.vue",
    "frontend/src/views/mobile/ocrcapture.vue",
    "frontend/src/views/mobile/reminderlist.vue",
    "frontend/src/views/mobile/shiftreportform.vue",
    "frontend/src/views/mobile/shiftreporthistory.vue",
    "frontend/src/views/mobile/unifiedentryform.vue",
    "frontend/src/views/entry/",
    "frontend/src/layout/entryshell.vue",
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

ROUTE_CANDIDATES = (
    "/manage/today",
    "/manage/live",
    "/manage/production",
    "/manage/coils",
    "/entry/*",
)

ROUTE_PROTECT_REASON = "生产核心入口路由，减法阶段必须保留。"

RUNTIME_SCAN_PATTERNS = (
    "backend/app/**/*.py",
    "backend/scripts/**/*.py",
    "backend/tests/**/*.py",
    "frontend/src/**/*.js",
    "frontend/src/**/*.vue",
    "frontend/tests/**/*.js",
)


def classify_audit_item(path: str) -> dict[str, str]:
    clean = str(path).replace("\\", "/")
    lowered = clean.lower()
    if lowered in ROUTE_CANDIDATES:
        return {
            "path": clean,
            "classification": "protect",
            "action": "keep",
            "reason": ROUTE_PROTECT_REASON,
        }
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
        "frontend/src/layout/**/*.vue",
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
    result.extend(ROUTE_CANDIDATES)

    return sorted(set(result))


def check_candidate_delete_paths(repo_root: str | Path, paths: Iterable[str]) -> dict:
    root = Path(repo_root)
    items = [_check_single_delete_candidate(root, str(path).replace("\\", "/")) for path in paths]
    return {
        "passed": all(item["status"] == "delete_allowed" for item in items),
        "items": items,
    }


def _check_single_delete_candidate(root: Path, clean_path: str) -> dict:
    lowered = clean_path.lower()
    if any(marker in lowered for marker in PROTECT_MARKERS):
        return {
            "path": clean_path,
            "status": "blocked",
            "reason": "protected_marker",
            "references": [],
        }

    full_path = root / clean_path
    if not full_path.exists():
        return {
            "path": clean_path,
            "status": "blocked",
            "reason": "candidate_missing",
            "references": [],
        }

    references = _runtime_references(root, clean_path)
    if references:
        return {
            "path": clean_path,
            "status": "blocked",
            "reason": "referenced_by_runtime_file",
            "references": references,
        }

    return {
        "path": clean_path,
        "status": "delete_allowed",
        "reason": "no_runtime_references",
        "references": [],
    }


def _runtime_references(root: Path, clean_path: str) -> list[str]:
    candidate = root / clean_path
    tokens = _reference_tokens(clean_path)
    references: list[str] = []
    for pattern in RUNTIME_SCAN_PATTERNS:
        for file_path in root.glob(pattern):
            if not file_path.is_file() or file_path == candidate:
                continue
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(token and token in text for token in tokens):
                references.append(str(file_path.relative_to(root)).replace("\\", "/"))
    return sorted(set(references))


def _reference_tokens(clean_path: str) -> tuple[str, ...]:
    path = Path(clean_path)
    stem = path.stem
    slash_path = clean_path.replace("\\", "/")
    without_ext = slash_path.rsplit(".", 1)[0]
    import_path = without_ext.replace("/", ".")
    vue_name = path.name if path.suffix == ".vue" else ""
    return tuple(token for token in (slash_path, without_ext, import_path, stem, vue_name) if token)
