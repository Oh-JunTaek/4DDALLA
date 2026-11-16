"""Alembic environment for 4 DDALLA (P1-DB-02).

Connection setup mirrors the application DB layer: ``DATABASE_URL`` from the
environment, synchronous ``postgresql+psycopg`` Engine, no credentials in
output. A missing DATABASE_URL fails the command with a clear message; a
failed connection is normalized to ``DatabaseUnavailableError`` whose text
withholds the connection string.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from alembic import context

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.base import Base
from app.db.config import get_database_url
from app.db.engine import create_db_engine
from app.db.errors import DatabaseUnavailableError

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    engine: Engine | None = None
    try:
        engine = create_db_engine(get_database_url())
        with engine.begin() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    except SQLAlchemyError:
        raise DatabaseUnavailableError(
            "database connection failed while running migrations "
            "(details withheld; check PostgreSQL availability and DATABASE_URL)"
        ) from None
    finally:
        if engine is not None:
            engine.dispose()


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live connection (URL still required)."""
    try:
        context.configure(
            url=get_database_url(),
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
    except SQLAlchemyError:
        raise DatabaseUnavailableError(
            "could not configure the migration database URL (details withheld)"
        ) from None
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
