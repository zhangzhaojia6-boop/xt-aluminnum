import os
import sys
from logging.config import fileConfig

from alembic import context
import sqlalchemy as sa
from sqlalchemy import engine_from_config, pool

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import settings  # noqa: E402
from app.models import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option('sqlalchemy.url', settings.DATABASE_URL)

target_metadata = Base.metadata


def _should_bootstrap_sqlite_at_head(connection) -> bool:
    if connection.dialect.name != 'sqlite':
        return False

    try:
        revision_argument = context.get_revision_argument()
    except KeyError:
        return False
    revision_arguments = (
        set(revision_argument)
        if isinstance(revision_argument, (list, tuple, set))
        else {revision_argument}
    )
    if not revision_arguments.intersection({'head', 'heads', context.get_head_revision()}):
        return False

    inspector = sa.inspect(connection)
    user_tables = [
        table_name
        for table_name in inspector.get_table_names()
        if table_name != 'alembic_version'
    ]
    return not user_tables


def _bootstrap_sqlite_schema_at_head(connection) -> None:
    target_metadata.create_all(bind=connection)
    connection.execute(sa.text('CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(64) NOT NULL)'))
    connection.execute(sa.text('DELETE FROM alembic_version'))
    connection.execute(
        sa.text('INSERT INTO alembic_version (version_num) VALUES (:revision)'),
        {'revision': context.get_head_revision()},
    )


def run_migrations_offline() -> None:
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        if _should_bootstrap_sqlite_at_head(connection):
            _bootstrap_sqlite_schema_at_head(connection)
            connection.commit()
            return

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == 'sqlite',
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
