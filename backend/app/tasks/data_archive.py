from __future__ import annotations

from datetime import date, timedelta


def archive_old_data(days_before: int = 90) -> dict[str, str]:
    cutoff = date.today() - timedelta(days=days_before)
    return {'status': 'skipped', 'cutoff': cutoff.isoformat()}
