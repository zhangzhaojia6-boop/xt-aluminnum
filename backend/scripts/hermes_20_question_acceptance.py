from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
REPORTS_ROOT = REPO_ROOT / "docs" / "superpowers" / "reports"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(BACKEND_ROOT / ".env")

from app.core.redaction import redact_secret_text
from app.database import get_sessionmaker
from app.models.system import User
from app.services.external_readonly_source_registry import (
    build_external_readonly_sources,
    health_check_sources,
)
from app.services.hermes_20_question_acceptance import render_acceptance_report
from app.services.hermes_20_question_runner import (
    DingTalkDeliveryTarget,
    _ALLOWED_DELIVERY_CHANNEL_TYPES,
    run_20_question_acceptance,
)
from app.services.report.daily_fact_bundle import build_daily_fact_bundle
from scripts.check_daily_report_output_skill_alignment import (
    resolve_output_skill_root,
    temporary_output_skill_root,
    write_alignment_artifacts,
)


_DEFAULT_ALIGNMENT_ARTIFACT_DIR = "docs/superpowers/reports/daily-report-fact-closure-smoke"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run 鑫泰铝业智能大脑 20 问真实验收")
    parser.add_argument("--business-date", required=True)
    parser.add_argument("--sender-external-id", required=True)
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--real-delivery", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--output-skill-root", default=None)
    parser.add_argument("--alignment-artifact-dir", default=_DEFAULT_ALIGNMENT_ARTIFACT_DIR)
    parser.add_argument("--require-daily-report-gate", action="store_true")
    parser.add_argument(
        "--report-path",
        default="docs/superpowers/reports/2026-06-28-hermes-20-question-real-acceptance-report.md",
    )
    return parser.parse_args(argv)


def parse_delivery_targets(values: list[str]) -> tuple[DingTalkDeliveryTarget, ...]:
    targets: list[DingTalkDeliveryTarget] = []
    for value in values:
        raw_value = str(value or "").strip()
        if ":" not in raw_value:
            raise ValueError("target_must_use_channel_type_colon_key")
        channel_type, channel_key = raw_value.split(":", 1)
        channel_type = channel_type.strip()
        channel_key = channel_key.strip()
        if channel_type not in _ALLOWED_DELIVERY_CHANNEL_TYPES or not channel_key:
            raise ValueError("unsupported_delivery_target")
        targets.append(DingTalkDeliveryTarget(channel_type=channel_type, channel_key=channel_key))
    return tuple(targets)


def resolve_report_path(value: str) -> Path:
    raw_value = str(value or "").strip()
    candidate = Path(raw_value)
    if not raw_value or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("report_path_outside_reports_dir")
    if candidate.parts[: len(REPORTS_ROOT.relative_to(REPO_ROOT).parts)] != REPORTS_ROOT.relative_to(REPO_ROOT).parts:
        raise ValueError("report_path_outside_reports_dir")
    return REPO_ROOT / candidate


def resolve_artifact_dir(value: str | None) -> Path | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    candidate = Path(raw_value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("alignment_artifact_dir_outside_reports_dir")
    reports_root_resolved = REPORTS_ROOT.resolve()
    resolved = (REPO_ROOT / candidate).resolve()
    try:
        resolved.relative_to(reports_root_resolved)
    except ValueError as exc:
        raise ValueError("alignment_artifact_dir_outside_reports_dir") from exc
    return resolved


def build_daily_report_gate_payload(
    db,
    *,
    business_date: date,
    output_skill_root: str | None,
    alignment_artifact_dir: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_key": "daily_report_gate",
        "domain": "factory_overview",
        "readonly": False,
        "business_date": business_date.isoformat(),
        "output_skill_alignment": {},
        "fact_closure": {},
        "gap_plan": {},
    }
    artifact_dir = resolve_artifact_dir(alignment_artifact_dir)
    output_root = resolve_output_skill_root(output_skill_root)
    row: dict[str, object]
    if output_root is None:
        payload["status"] = "error"
        payload["failure_reason"] = "output_skill_root_missing"
        row = _daily_report_gate_artifact_row(payload, error="output_skill_root_missing")
    elif not output_root.exists():
        payload["status"] = "error"
        payload["failure_reason"] = "output_skill_root_not_found"
        payload["output_skill_root"] = str(output_root)
        row = _daily_report_gate_artifact_row(payload, error=f"output skill root does not exist: {output_root}")
    else:
        payload["output_skill_root"] = str(output_root)
        try:
            with temporary_output_skill_root(output_root):
                bundle = build_daily_fact_bundle(db, business_date=business_date, persist_run=False)
        except Exception as exc:  # noqa: BLE001
            payload["status"] = "error"
            payload["failure_reason"] = "daily_report_gate_build_failed"
            row = _daily_report_gate_artifact_row(
                payload,
                error=redact_secret_text(f"{type(exc).__name__}: {exc}"),
            )
        else:
            alignment = dict(bundle.get("output_skill_alignment") or {})
            fact_closure = dict(bundle.get("fact_closure") or {})
            gap_plan = dict(bundle.get("gap_plan") or {})
            payload["output_skill_alignment"] = alignment
            payload["fact_closure"] = fact_closure
            payload["gap_plan"] = gap_plan
            payload["missing_fields"] = list(bundle.get("missing_fields") or bundle.get("missing") or [])
            payload["status"] = (
                "passed"
                if alignment.get("status") == "passed" and fact_closure.get("status") == "pass"
                else "blocked"
            )
            row = _daily_report_gate_artifact_row(payload)
    if artifact_dir is not None:
        payload["artifacts"] = write_alignment_artifacts([row], artifact_dir)
    return payload


def _daily_report_gate_artifact_row(
    payload: dict[str, object],
    *,
    error: str | None = None,
) -> dict[str, object]:
    alignment = payload.get("output_skill_alignment")
    alignment_map = alignment if isinstance(alignment, dict) else {}
    fact_closure = payload.get("fact_closure")
    fact_closure_map = fact_closure if isinstance(fact_closure, dict) else {}
    gap_plan = payload.get("gap_plan")
    gap_plan_map = gap_plan if isinstance(gap_plan, dict) else {}
    differences = list(alignment_map.get("differences") or [])
    return {
        "business_date": payload.get("business_date"),
        "status": payload.get("status"),
        "bundle_status": fact_closure_map.get("status"),
        "file_name": alignment_map.get("file_name"),
        "field_match_rate": alignment_map.get("field_match_rate"),
        "matched_fields": alignment_map.get("matched_fields"),
        "expected_fields": alignment_map.get("expected_fields"),
        "difference_count": alignment_map.get("difference_count"),
        "differences": differences[:20],
        "char_match_rate": alignment_map.get("char_match_rate"),
        "exact_match": bool(alignment_map.get("exact_match")),
        "threshold": alignment_map.get("threshold"),
        "missing_fields_count": len(payload.get("missing_fields") or []),
        "gap_plan": gap_plan_map,
        "error": error,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.real_delivery:
        print("refusing_real_acceptance_without_real_delivery_flag")
        return 2
    if not args.target:
        print("target_required")
        return 2
    try:
        delivery_targets = parse_delivery_targets(args.target)
        business_date = date.fromisoformat(args.business_date)
        report_path = resolve_report_path(args.report_path)
        resolve_artifact_dir(args.alignment_artifact_dir)
    except ValueError as exc:
        print(str(exc))
        return 2

    session_factory = get_sessionmaker()
    with session_factory() as db:
        current_user = db.get(User, int(args.user_id))
        if current_user is None:
            print("user_not_found")
            return 2
        source_health = health_check_sources(
            build_external_readonly_sources(),
            probe=lambda source: None,
        )
        required_source_health: tuple[str, ...] = ()
        if args.require_daily_report_gate:
            source_health["daily_report_gate"] = build_daily_report_gate_payload(
                db,
                business_date=business_date,
                output_skill_root=args.output_skill_root,
                alignment_artifact_dir=args.alignment_artifact_dir,
            )
            required_source_health = ("daily_report_gate",)
        outcome = run_20_question_acceptance(
            db,
            current_user=current_user,
            sender_external_id=args.sender_external_id,
            business_date=business_date,
            source_health=source_health,
            required_source_health=required_source_health,
            delivery_targets=delivery_targets,
            limit=args.limit,
        )

    report = render_acceptance_report(outcome.summary)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(report)
    return 0 if outcome.summary.core_passed and outcome.summary.delivery_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
