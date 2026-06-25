from __future__ import annotations

from pathlib import Path

from app.config import settings


def load_default_soul_text() -> str:
    configured = Path(str(settings.HERMES_SOUL_PATH or 'app/hermes/Soul.md'))
    if configured.is_absolute():
        path = configured
    elif configured.parts and configured.parts[0] == 'app':
        path = Path(__file__).resolve().parents[1] / configured.relative_to('app')
    else:
        path = Path(__file__).resolve().parents[1] / configured
    return path.read_text(encoding='utf-8')
