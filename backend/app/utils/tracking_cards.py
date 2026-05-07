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


def tracking_card_sql_lookup_key(column):
    expression = func.upper(func.trim(column))
    for source, replacement in TRACKING_CARD_SQL_REPLACEMENTS:
        expression = func.replace(expression, source, replacement)
    return expression
