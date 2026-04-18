import re

from tests.path_helpers import BACKEND_ROOT

VERSIONS_DIR = BACKEND_ROOT / 'alembic' / 'versions'


def test_long_revision_ids_are_supported_by_widening_alembic_version_column() -> None:
    revisions: list[str] = []
    for path in VERSIONS_DIR.glob('*.py'):
        text = path.read_text(encoding='utf-8')
        match = re.search(r"^revision\s*=\s*'([^']+)'", text, re.MULTILINE)
        if match:
            revisions.append(match.group(1))

    assert revisions
    assert max(len(revision) for revision in revisions) <= 64

    migration_text = (VERSIONS_DIR / '0011_work_orders_core.py').read_text(encoding='utf-8')
    assert 'alembic_version' in migration_text
    assert 'VARCHAR(64)' in migration_text or 'String(length=64)' in migration_text
