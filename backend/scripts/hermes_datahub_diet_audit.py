from __future__ import annotations

from pathlib import Path

from app.services.hermes_datahub_diet_audit_service import candidate_paths, render_diet_audit_report


REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "docs" / "superpowers" / "reports" / "datahub-diet-audit-2026-06-25.md"


def main() -> None:
    report = render_diet_audit_report(candidate_paths(REPO_ROOT))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(report, encoding="utf-8")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
