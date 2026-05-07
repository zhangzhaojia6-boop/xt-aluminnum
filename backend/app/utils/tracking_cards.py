from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func


TRACKING_CARD_SEPARATOR_TRANSLATION = str.maketrans(
    {
        '一': '-',
        '－': '-',
        '—': '-',
        '–': '-',
        '﹣': '-',
        '_': '-',
    }
)

TRACKING_CARD_SQL_REPLACEMENTS = (
    ('一', '-'),
    ('－', '-'),
    ('—', '-'),
    ('–', '-'),
    ('﹣', '-'),
    ('_', '-'),
    (' ', ''),
    ('\t', ''),
    ('\r', ''),
    ('\n', ''),
)


def tracking_card_lookup_key(value: Any) -> str:
    text = str(value or '').strip().upper().translate(TRACKING_CARD_SEPARATOR_TRANSLATION)
    text = re.sub(r'\s+', '', text)
    return re.sub(r'-{2,}', '-', text)


def tracking_card_lookup_candidates(value: Any) -> set[str]:
    key = tracking_card_lookup_key(value)
    if not key:
        return set()

    candidates: set[str] = set()

    def add_variants(candidate: str) -> None:
        normalized = tracking_card_lookup_key(candidate)
        if not normalized:
            return
        candidates.add(normalized)
        if normalized.startswith('26-') and len(normalized) > 3:
            candidates.add(normalized[3:])
            return
        if re.match(r'^[A-Z]+-\d', normalized):
            candidates.add(f'26-{normalized}')

    add_variants(key)
    for part in re.split(r'[:|,;]+', key):
        add_variants(part)

    return candidates


def tracking_card_sql_lookup_key(column):
    expression = func.upper(func.trim(column))
    for source, replacement in TRACKING_CARD_SQL_REPLACEMENTS:
        expression = func.replace(expression, source, replacement)
    return expression
