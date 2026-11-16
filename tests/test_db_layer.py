"""DB-layer tests for P1-DB-02 (app/db package + Alembic wiring).

Split by requirement:
- Always-run (no database needed): configuration handling, error
  normalization against a closed local port, session lifecycle without a
  live server, and secret-hygiene of error text/logs.
- DB-required (skipped when DATABASE_URL is unset): live connectivity,
  scratch-table commit/rollback, connection return to the pool, and the
  Alembic upgrade/downgrade round-trip.

The DB-required group targets the local PostgreSQL 17 / PostGIS 3.7 dev
database addressed by DATABASE_URL (never hardcoded here). It only creates a
uniquely named scratch table (dropped in cleanup) and exercises Alembic
migration history; no other schema/table is touched.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from alembic import command
from app.db.config import get_database_url
from app.db.dependencies import (
    database_configuration_handler,
    database_unavailable_handler,
)
from app.db.engine import (
    check_connection,
    create_db_engine,
    get_engine,
    reset_engine_cache,
)
from app.db.errors import DatabaseConfigurationError, DatabaseUnavailableError

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Obvious fake credentials + a port with nothing listening: the closed port
# makes connection failure deterministic; nothing here is a real endpoint.
_UNREACHABLE_URL = "postgresql+psycopg://test:test@127.0.0.1:1/testdb"


@pytest.fixture(autouse=True)
def clean_engine_cache() -> Iterator[None]:
    """Isolate tests that mutate DATABASE_URL / the cached Engine."""
    reset_engine_cache()
    yield
    reset_engine_cache()


# --- No database required -------------------------------------------------


def test_database_url_missing_raises() -> None:
    with pytest.raises(DatabaseConfigurationError) as excinfo:
        get_database_url({})
    message = str(excinfo.value)
    assert "DATABASE_URL" in message
    assert "test:test" not in message


def test_database_url_default_source_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DatabaseConfigurationError):
        get_database_url()


@pytest.mark.parametrize("value", ["", "   "])
def test_database_url_empty_raises(value: str) -> None:
    with pytest.raises(DatabaseConfigurationError):
        get_database_url({"DATABASE_URL": value})


def test_database_url_is_stripped() -> None:
    assert get_database_url({"DATABASE_URL": f"  {_UNREACHABLE_URL}  "}) == _UNREACHABLE_URL


def test_get_engine_without_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DatabaseConfigurationError):
        get_engine()


def test_unreachable_database_normalized() -> None:
    engine = create_db_engine(_UNREACHABLE_URL)
    try:
        with pytest.raises(DatabaseUnavailableError) as excinfo:
            check_connection(engine)
    finally:
        engine.dispose()
    message = str(excinfo.value)
    assert "database connection failed" in message
    assert "://" not in message
    assert "127.0.0.1" not in message
    assert "test:test" not in message
    assert excinfo.value.__cause__ is None


def test_failure_does_not_log_credentials(caplog: pytest.LogCaptureFixture) -> None:
    engine = create_db_engine(_UNREACHABLE_URL)
    try:
        with caplog.at_level(logging.DEBUG), pytest.raises(DatabaseUnavailableError):
            check_connection(engine)
    finally:
        engine.dispose()
    assert not [r for r in caplog.records if r.name.startswith("app.db")]
    leaked = [
        r
        for r in caplog.records
        if "postgresql+psycopg" in r.getMessage() or "test:test" in r.getMessage()
    ]
    assert leaked == []


def test_session_create_and_close(monkeypatch: pytest.MonkeyPatch) -> None:
    # Session creation binds the Engine; it does not connect, so this runs
    # without a live server.
    monkeypatch.setenv("DATABASE_URL", _UNREACHABLE_URL)
    engine = get_engine()
    session = Session(engine)
    session.close()
    session.close()  # close is idempotent
    assert engine.pool.checkedout() == 0


def test_main_registers_database_error_handlers() -> None:
    from app.main import app

    handlers = app.exception_handlers
    assert DatabaseUnavailableError in handlers
    assert DatabaseConfigurationError in handlers


def test_error_handlers_return_static_json() -> None:
    unavailable = asyncio.run(
        database_unavailable_handler(
            None, DatabaseUnavailableError("host=127.0.0.1 secret=shh")
        )  # type: ignore[arg-type]
    )
    assert unavailable.status_code == 503
    body = json.loads(unavailable.body)
    assert body == {"detail": "database unavailable"}
    assert "shh" not in unavailable.body.decode()

    configuration = asyncio.run(
        database_configuration_handler(
            None, DatabaseConfigurationError("DATABASE_URL=postgresql+psycopg://x")
        )  # type: ignore[arg-type]
    )
    assert configuration.status_code == 500
    assert json.loads(configuration.body) == {"detail": "database configuration error"}


# --- Requires DATABASE_URL (skipped when unset, e.g. CI without a DB) ------


@pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set; DB integration test skipped",
)
class TestLiveDatabase:
    """Exercises the real local dev DB only (never another project's DB)."""

    def test_live_connection_succeeds(self) -> None:
        engine = create_db_engine(get_database_url())
        try:
            check_connection(engine)
        finally:
            engine.dispose()

    def test_scratch_table_commit_and_rollback(self) -> None:
        table = "p1db02_probe_" + uuid.uuid4().hex
        quoted = f'"{table}"'
        engine = create_db_engine(get_database_url())
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(f"CREATE TABLE {quoted} (id integer PRIMARY KEY, note text)")
                )
            with Session(engine) as session:
                session.execute(text(f"INSERT INTO {quoted} (id, note) VALUES (1, 'a')"))
                session.commit()
                assert (
                    session.execute(text(f"SELECT count(*) FROM {quoted}")).scalar_one() == 1
                )
                session.execute(text(f"INSERT INTO {quoted} (id, note) VALUES (2, 'b')"))
                session.rollback()
                assert (
                    session.execute(text(f"SELECT count(*) FROM {quoted}")).scalar_one() == 1
                )
        finally:
            with engine.begin() as connection:
                connection.execute(text(f"DROP TABLE IF EXISTS {quoted}"))
            engine.dispose()

    def test_connection_returned_to_pool(self) -> None:
        engine = create_db_engine(get_database_url())
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                assert engine.pool.checkedout() == 1
            assert engine.pool.checkedout() == 0
        finally:
            engine.dispose()

    def test_alembic_upgrade_downgrade_roundtrip(self) -> None:
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        command.upgrade(config, "head")
        engine = create_db_engine(get_database_url())
        try:
            assert inspect(engine).has_table("p1db02_migration_probe")
        finally:
            engine.dispose()
        command.downgrade(config, "base")
        engine = create_db_engine(get_database_url())
        try:
            assert not inspect(engine).has_table("p1db02_migration_probe")
        finally:
            engine.dispose()
