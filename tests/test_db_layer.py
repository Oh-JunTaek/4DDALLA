"""DB-layer tests for P1-DB-02, hardened in P1-DB-HARDEN-01.

Three tiers, kept deliberately separable so the default run stays DB-free:

- Always-run (no database, no env): configuration handling, error
  normalization against a closed local port, secret-hygiene of error text/logs,
  session lifecycle without a live server, FastAPI handler registration, the
  endpoint error-mapping boundary, and the isolated-migration policy guard
  (unit-level refusals -- no connection, no migration).
- DB-required against the dev database addressed by ``DATABASE_URL`` (skipped
  when unset, e.g. CI without a DB): connectivity, scratch-table commit/rollback,
  connection return to the pool, and real FastAPI endpoint behavior for
  connection failure (503), rollback-on-error, and SQL-constraint violation
  (500, not blanket-503).
- Isolation-verification (separate opt-in, ``DDALLA_TEST_ISOLATED_MIGRATION_DB``
  in {"1", "true", "yes", "on"}): the Alembic upgrade -> downgrade -> re-upgrade
  round-trip executed ONLY on a uniquely named scratch database, created and
  dropped at runtime. ``downgrade base`` must never run against a general
  database: the target is verified from parsed URL components (dialect, loopback
  host, port, non-protected database), an unusable configuration in verification
  mode FAILS instead of silently skipping, and cleanup runs even on failure.
  """

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from collections.abc import Iterator, Mapping
from pathlib import Path

import psycopg
import pytest
from alembic.config import Config
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import URL, inspect, text
from sqlalchemy.exc import (
    DisconnectionError,
    IntegrityError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.exc import (
    OperationalError as SqlAlchemyOperationalError,
)
from sqlalchemy.exc import (
    TimeoutError as SqlAlchemyTimeoutError,
)
from sqlalchemy.orm import Session

from alembic import command
from app.db.config import get_database_url
from app.db.dependencies import (
    _is_connection_failure,
    database_configuration_handler,
    database_unavailable_handler,
    get_db,
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

# Isolation-policy constants (P1-DB-HARDEN-01). ``_PROTECTED_DBNAMES`` mirrors
# the local dev DB name from docker/.env (POSTGRES_DB); safety never rests on a
# variable name or a database name ALONE -- plan_isolated_target() verifies the
# parsed dialect/host/port and generates the scratch name itself.
_ISOLATION_ENV = "DDALLA_TEST_ISOLATED_MIGRATION_DB"
_PROTECTED_DBNAMES = frozenset({"4ddalla"})
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "::1"})
_ALLOWED_PORT = 5432
_ALLOWED_DRIVERNAME = "postgresql+psycopg"
_MAINTENANCE_DB = "postgres"
_SCRATCH_PREFIX = "p1db02_iso_"
_DEV_LIKE_URL = "postgresql+psycopg://4ddalla:fake-pw@127.0.0.1:5432/4ddalla"


class IsolatedTargetError(RuntimeError):
    """Isolated-migration target refused; static, credential-free text only."""


def isolation_mode_enabled(env: Mapping[str, str] | None = None) -> bool | None:
    """Tri-state opt-in read: True / False (explicitly off) / None (unset).

    A set-but-unrecognized value raises ``IsolatedTargetError`` so a typo in
    verification mode surfaces instead of being silently ignored.
    """
    source: Mapping[str, str] = os.environ if env is None else env
    raw = source.get(_ISOLATION_ENV)
    if raw is None or not raw.strip():
        return None
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise IsolatedTargetError(
        f"{_ISOLATION_ENV} has unrecognized value; use 1/true/yes/on or 0/false/no/off"
    )


def _skip_isolated_migration(env: Mapping[str, str] | None = None) -> bool:
    """Skip condition for the isolated-migration tests (resolved eagerly).

    pytest evaluates ``skipif`` conditions with ``bool()``; a lambda condition
    would be truthy no matter what the opt-in says, skipping the verification
    even when enabled (and silently ignoring an unrecognized value). Invalid
    values still raise ``IsolatedTargetError`` -- an explicit collection failure.
    """
    return isolation_mode_enabled(env) is not True


def plan_isolated_target(database_url: str, *, enabled: bool) -> tuple[URL, str]:
    """Verify a round-trip target and return (server URL, unique scratch name).

    The server family must be the local development loopback endpoint on the
    expected dialect/port and the configured database must not be a protected
    general database. The scratch database name is generated here (never taken
    from configuration), so it cannot collide with a real database. No
    connection is opened and no target is modified.
    """
    if not enabled:
        raise IsolatedTargetError("isolated-migration mode is not enabled")
    try:
        engine = create_db_engine(database_url)
    except Exception:  # noqa: BLE001
        raise IsolatedTargetError("target URL could not be parsed") from None
    try:
        url = engine.url
    finally:
        engine.dispose()
    if url.drivername != _ALLOWED_DRIVERNAME:
        raise IsolatedTargetError(
            f"target must use the {_ALLOWED_DRIVERNAME} dialect"
        )
    if url.host not in _ALLOWED_HOSTS or url.port != _ALLOWED_PORT:
        raise IsolatedTargetError(
            "target must be the local development loopback endpoint"
        )
    if not url.database:
        raise IsolatedTargetError("target URL has no database name")
    if url.database in _PROTECTED_DBNAMES:
        raise IsolatedTargetError(
            "refusing isolated migrations against a protected general database"
        )
    return url, f"{_SCRATCH_PREFIX}{uuid.uuid4().hex}"


def _drop_scratch(maintenance_engine, scratch: str) -> None:
    """Drop the scratch database and verify it is gone; loudly on failure."""
    try:
        with maintenance_engine.connect() as connection:
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
            connection.execute(
                text(f'DROP DATABASE IF EXISTS "{scratch}" WITH (FORCE)')
            )
        with maintenance_engine.connect() as connection:
            row = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": scratch}
            ).fetchone()
        if row is not None:
            raise RuntimeError("scratch database still present after drop")
    finally:
        maintenance_engine.dispose()


def _isolated_roundtrip(database_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """Run upgrade -> downgrade -> re-upgrade on a fresh scratch database.

    The configured database is used only as the loopback server anchor; every
    migration statement executes on the uniquely named scratch database, which
    is dropped (and verified gone) afterwards -- including on failure.
    """
    server_url, scratch = plan_isolated_target(database_url, enabled=True)
    maintenance_engine = create_db_engine(server_url.set(database=_MAINTENANCE_DB))
    try:
        with maintenance_engine.connect() as connection:
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
            connection.execute(text(f'CREATE DATABASE "{scratch}"'))
        target_url = server_url.set(database=scratch)
        monkeypatch.setenv("DATABASE_URL", str(target_url))
        # the URL actually in force must be the scratch database -- the
        # configured general database is only used as the server anchor
        assert get_database_url().endswith(f"/{scratch}")
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        command.upgrade(config, "head")
        inspector_engine = create_db_engine(target_url)
        try:
            assert inspector_engine.url.database == scratch
            assert inspect(inspector_engine).has_table("p1db02_migration_probe")
        finally:
            inspector_engine.dispose()
        command.downgrade(config, "base")
        command.upgrade(config, "head")
    finally:
        _drop_scratch(maintenance_engine, scratch)
    return scratch


def _make_probe_app(*, table: str | None = None) -> FastAPI:
    """Tiny app reusing the app's DB error handlers and ``get_db`` dependency.

    ``Depends`` in a default marks a FastAPI dependency-injection position
    (B008 suppressed deliberately; FastAPI evaluates it, it is not called here).
    """
    app = FastAPI()
    app.add_exception_handler(DatabaseUnavailableError, database_unavailable_handler)
    app.add_exception_handler(DatabaseConfigurationError, database_configuration_handler)

    @app.get("/db_probe")
    def db_probe(db: Session = Depends(get_db)) -> dict[str, str]:  # noqa: B008
        value = db.execute(text("SELECT 1")).scalar_one()
        return {"value": str(value)}

    @app.get("/db_probe_synthetic")
    def db_probe_synthetic() -> dict[str, str]:
        # No database needed: proves the mapping boundary for SQLAlchemyError
        # subclasses that are NOT connection failures.
        raise IntegrityError("synthetic statement", {}, Exception("synthetic failure"))

    if table is not None:
        quoted = f'"{table}"'

        @app.get("/db_probe_rollback")
        def db_probe_rollback(db: Session = Depends(get_db)) -> dict[str, str]:  # noqa: B008
            db.execute(text(f"INSERT INTO {quoted} (id) VALUES (99)"))
            raise RuntimeError("probe failure")

        @app.get("/db_probe_violation")
        def db_probe_violation(db: Session = Depends(get_db)) -> dict[str, str]:  # noqa: B008
            db.execute(text(f"INSERT INTO {quoted} (id) VALUES (1)"))
            db.commit()
            db.execute(text(f'INSERT INTO {quoted} (id) VALUES (1)'))
            db.commit()
            return {"ok": "true"}

    return app


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


# --- Connection-failure classification (P1-DB-HARDEN-01 2nd review) ------------


@pytest.mark.parametrize(
    "exc",
    [
        SqlAlchemyOperationalError("SELECT 1", {}, Exception("connection refused")),
        DisconnectionError("connection invalidated"),
        SqlAlchemyTimeoutError("pool timed out"),
        psycopg.OperationalError("connection refused"),
    ],
)
def test_connection_failures_are_recognized(exc: Exception) -> None:
    """Only connection-class failures normalize to DatabaseUnavailableError."""
    assert _is_connection_failure(exc) is True


@pytest.mark.parametrize(
    "exc",
    [
        IntegrityError("INSERT", {}, Exception("duplicate key")),
        ProgrammingError("SELECT", {}, Exception("syntax error")),
        SQLAlchemyError("generic database error"),
    ],
)
def test_non_connection_errors_are_not_unavailable(exc: Exception) -> None:
    """Constraints / query errors / unknowns must not be reported as outage (503)."""
    assert _is_connection_failure(exc) is False


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


# --- Isolated-migration policy (P1-DB-HARDEN-01, no DB required) ------------


def test_isolation_mode_unset_and_explicitly_off() -> None:
    assert isolation_mode_enabled({}) is None
    assert isolation_mode_enabled({"DDALLA_TEST_ISOLATED_MIGRATION_DB": ""}) is None
    assert isolation_mode_enabled({"DDALLA_TEST_ISOLATED_MIGRATION_DB": "0"}) is False


def test_isolation_mode_unknown_value_rejected() -> None:
    with pytest.raises(IsolatedTargetError):
        isolation_mode_enabled({"DDALLA_TEST_ISOLATED_MIGRATION_DB": "maybe"})


def test_isolation_mode_enabled_values() -> None:
    for value in ("1", "true", "YES", " on "):
        assert isolation_mode_enabled({"DDALLA_TEST_ISOLATED_MIGRATION_DB": value}) is True


def test_guard_refuses_without_mode() -> None:
    with pytest.raises(IsolatedTargetError):
        plan_isolated_target(_DEV_LIKE_URL, enabled=False)


def test_guard_refuses_protected_general_database() -> None:
    with pytest.raises(IsolatedTargetError):
        plan_isolated_target(_DEV_LIKE_URL, enabled=True)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://u:p@db.example.com:5432/other",
        "postgresql+psycopg://u:p@127.0.0.1:5433/other",
        "postgresql://u:p@127.0.0.1:5432/other",
        "not-a-sqlalchemy-url",
    ],
)
def test_guard_refuses_non_local_or_unparseable_targets(url: str) -> None:
    with pytest.raises(IsolatedTargetError):
        plan_isolated_target(url, enabled=True)


def test_guard_generates_unique_scratch_name() -> None:
    server_url, scratch = plan_isolated_target(_DEV_LIKE_URL.replace("/4ddalla", "/other"), enabled=True)
    assert server_url.host in _ALLOWED_HOSTS
    assert scratch.startswith(_SCRATCH_PREFIX)
    _other_url, other_scratch = plan_isolated_target(
        _DEV_LIKE_URL.replace("/4ddalla", "/other"), enabled=True
    )
    assert scratch != other_scratch


@pytest.mark.parametrize(
    "env,expected",
    [
        ({}, True),
        ({_ISOLATION_ENV: ""}, True),
        ({_ISOLATION_ENV: "0"}, True),
        ({_ISOLATION_ENV: "false"}, True),
        ({_ISOLATION_ENV: "1"}, False),
        ({_ISOLATION_ENV: "yes"}, False),
        ({_ISOLATION_ENV: " on "}, False),
    ],
)
def test_skip_condition_follows_opt_in(env: Mapping[str, str], expected: bool) -> None:
    """Enabled -> runnable condition (False); unset/explicitly off -> skip (True)."""
    assert _skip_isolated_migration(env) is expected


def test_skip_condition_rejects_unrecognized_value() -> None:
    """A typo in the verification switch fails loudly, never silently skips."""
    with pytest.raises(IsolatedTargetError):
        _skip_isolated_migration({_ISOLATION_ENV: "maybe"})


def test_endpoint_non_connection_sqlaerror_is_not_503() -> None:
    client = TestClient(_make_probe_app(), raise_server_exceptions=False)
    response = client.get("/db_probe_synthetic")
    assert response.status_code == 500
    assert response.status_code != 503
    assert "synthetic failure" not in response.text
    assert "database unavailable" not in response.text


def test_endpoint_connection_failure_is_static_503(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Real FastAPI request against an unreachable endpoint -> static 503.

    No live DB needed: proves the request path normalizes connection failures to
    DatabaseUnavailableError (never a raw SQLAlchemy/psycopg exception), keeps
    the response and application logs free of URL/credential material, and
    returns the pooled connection.
    """
    monkeypatch.setenv("DATABASE_URL", _UNREACHABLE_URL)
    engine = get_engine()
    try:
        client = TestClient(_make_probe_app(), raise_server_exceptions=False)
        with caplog.at_level(logging.DEBUG):
            response = client.get("/db_probe")
        assert response.status_code == 503  # not 500: known failure class
        assert response.json() == {"detail": "database unavailable"}
        assert "test:test" not in response.text
        assert "postgresql+psycopg" not in response.text
        assert "127.0.0.1" not in response.text
        leaked = [
            record
            for record in caplog.records
            if "test:test" in record.getMessage() or "postgresql+psycopg" in record.getMessage()
        ]
        assert leaked == []
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()


# --- Requires DATABASE_URL (skipped when unset, e.g. CI without a DB) --------


@pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set; DB integration test skipped",
)
class TestLiveDatabase:
    """Exercises the configured local dev DB only (never another project's DB)."""

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

    def test_endpoint_connection_failure_is_static_503(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        marker = "endpoint-marker-pw"
        monkeypatch.setenv(
            "DATABASE_URL", f"postgresql+psycopg://u:{marker}@127.0.0.1:1/db"
        )
        engine = get_engine()
        try:
            client = TestClient(_make_probe_app(), raise_server_exceptions=False)
            with caplog.at_level(logging.DEBUG):
                response = client.get("/db_probe")
            assert response.status_code == 503
            assert response.json() == {"detail": "database unavailable"}
            assert marker not in response.text
            assert "postgresql+psycopg" not in response.text
            leaked = [
                record
                for record in caplog.records
                if marker in record.getMessage()
                or "postgresql+psycopg" in record.getMessage()
            ]
            assert leaked == []
            assert engine.pool.checkedout() == 0
        finally:
            engine.dispose()

    def test_endpoint_error_rolls_back_and_closes(self) -> None:
        table = "p1db02_probe_" + uuid.uuid4().hex
        quoted = f'"{table}"'
        engine = create_db_engine(get_database_url())
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(f"CREATE TABLE {quoted} (id integer PRIMARY KEY, note text)")
                )
            client = TestClient(_make_probe_app(table=table), raise_server_exceptions=False)
            response = client.get("/db_probe_rollback")
            assert response.status_code == 500
            assert "probe failure" not in response.text
            with Session(engine) as session:
                assert session.execute(text(f"SELECT count(*) FROM {quoted}")).scalar_one() == 0
            assert engine.pool.checkedout() == 0
        finally:
            with engine.begin() as connection:
                connection.execute(text(f"DROP TABLE IF EXISTS {quoted}"))
            engine.dispose()

    def test_endpoint_sql_violation_is_not_503(self) -> None:
        table = "p1db02_probe_" + uuid.uuid4().hex
        quoted = f'"{table}"'
        engine = create_db_engine(get_database_url())
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(f"CREATE TABLE {quoted} (id integer PRIMARY KEY, note text)")
                )
            client = TestClient(_make_probe_app(table=table), raise_server_exceptions=False)
            response = client.get("/db_probe_violation")
            assert response.status_code == 500
            assert response.status_code != 503
            with Session(engine) as session:
                assert session.execute(text(f"SELECT count(*) FROM {quoted}")).scalar_one() == 1
            assert engine.pool.checkedout() == 0
        finally:
            with engine.begin() as connection:
                connection.execute(text(f"DROP TABLE IF EXISTS {quoted}"))
            engine.dispose()

    @pytest.mark.skipif(
        _skip_isolated_migration(),
        reason=(
            "isolated-migration verification not enabled "
            "(DDALLA_TEST_ISOLATED_MIGRATION_DB=1; default run stays DB-free)"
        ),
    )
    def test_alembic_roundtrip_on_isolated_scratch_db(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scratch = _isolated_roundtrip(get_database_url(), monkeypatch)
        assert scratch.startswith(_SCRATCH_PREFIX)

    @pytest.mark.skipif(
        _skip_isolated_migration(),
        reason=(
            "isolated-migration verification not enabled "
            "(DDALLA_TEST_ISOLATED_MIGRATION_DB=1; default run stays DB-free)"
        ),
    )
    def test_isolated_roundtrip_cleans_up_on_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("simulated migration failure")

        monkeypatch.setattr(command, "upgrade", boom)
        with pytest.raises(RuntimeError, match="simulated migration failure"):
            _isolated_roundtrip(get_database_url(), monkeypatch)
