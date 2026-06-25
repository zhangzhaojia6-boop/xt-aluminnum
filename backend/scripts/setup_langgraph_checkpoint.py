from __future__ import annotations

from langgraph.checkpoint.postgres import PostgresSaver

from app.config import settings


def main() -> None:
    db_uri = _postgres_checkpoint_uri(str(settings.DATABASE_URL))
    with PostgresSaver.from_conn_string(db_uri) as checkpointer:
        checkpointer.setup()
    print('langgraph checkpoint schema ready')


def _postgres_checkpoint_uri(db_uri: str) -> str:
    if db_uri.startswith('postgresql+psycopg2://') or db_uri.startswith('postgresql+psycopg://'):
        return 'postgresql://' + db_uri.split('://', 1)[1]
    if db_uri.startswith('postgresql://'):
        return db_uri
    raise RuntimeError('LangGraph checkpoint setup requires a PostgreSQL DATABASE_URL')


if __name__ == '__main__':
    main()
