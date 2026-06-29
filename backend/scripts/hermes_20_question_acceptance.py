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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run 鑫泰铝业智能大脑 20 问真实验收")
    parser.add_argument("--business-date", required=True)
    parser.add_argument("--sender-external-id", required=True)
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--real-delivery", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--user-id", type=int, default=1)
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
        outcome = run_20_question_acceptance(
            db,
            current_user=current_user,
            sender_external_id=args.sender_external_id,
            business_date=business_date,
            source_health=source_health,
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
