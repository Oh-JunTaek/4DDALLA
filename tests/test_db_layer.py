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
  dropped at runtime and verified in phases against the released chain (001 ->
  head -> 001 -> head). The configured DATABASE_URL is the server ANCHOR (any
  database of the local development loopback endpoint, dev DB ``4ddalla``
  included); every destructive statement (create/upgrade/downgrade/drop) targets
  only the runtime UUID scratch, which is re-verified from the URL in force
  immediately before execution. The server identity (PostgreSQL version,
  loopback-or-local-socket peer), CREATE/DROP privilege are pre-checked, the target is cross-checked
  so identification uncertainty starts nothing, an unusable configuration in
  verification mode FAILS instead of silently skipping, and cleanup runs even on
  failure. Because the chain's DDL uses a ``geography`` column, the scratch
  database has to have the PostGIS extension enabled before the chain runs (a
  fresh database does not inherit it); a failure to enable it aborts the
  round-trip without privilege escalation, and cleanup still runs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
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
from app.db import (
    dependencies,
    models,  # noqa: F401  -- register the domain tables on Base.metadata
)
from app.db.base import Base
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
# the local dev DB name from docker/.env (POSTGRES_DB); the name is an anchor
# candidate, NEVER a migration target -- plan_isolated_target() generates the
# scratch name itself and _isolated_roundtrip() rejects any scheme in which
# create/upgrade/downgrade/drop could reach it, the maintenance DB "postgres",
# or a second pre-existing scratch.
_ISOLATION_ENV = "DDALLA_TEST_ISOLATED_MIGRATION_DB"
_PROTECTED_DBNAMES = frozenset({"4ddalla"})
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "::1"})
_ALLOWED_PORT = 5432
_ALLOWED_DRIVERNAME = "postgresql+psycopg"
_MAINTENANCE_DB = "postgres"
_SCRATCH_PREFIX = "p1db02_iso_"
# Expected P1-DATA-01 domain set (alembic revision 002) and the 001-era probe
# table that 002 drops (its downgrade restores the schema, not rows)
_DOMAIN_TABLES = frozenset(
    {"brands", "stores", "store_aliases", "sources", "source_links", "source_evidence"}
)
_PROBE_TABLE = "p1db02_migration_probe"
_DEV_LIKE_URL = "postgresql+psycopg://4ddalla:fake-pw@127.0.0.1:5432/4ddalla"

# Docker-side identification for the conditional bridge-peer allowance (§2
# of the final verification ticket). Identified from read-only Docker
# metadata at every verification run -- nothing network-side is trusted from
# constants, and nothing here is a general service-connection policy: the
# allowance is scoped to this isolated verification harness ("4ddalla" dev
# container), never to map/place sources or other projects.
_EXPECTED_CONTAINER = "4ddalla-db"
_EXPECTED_IMAGE = "postgis/postgis:17-3.7"
_EXPECTED_COMPOSE_PROJECT = "docker"
_EXPECTED_COMPOSE_SERVICE = "db"
_EXPECTED_PUBLISHED = ("5432/tcp", "127.0.0.1", "5432")


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

    ``database_url`` is the *server anchor* -- any database of the expected local
    development loopback endpoint (the dev DB ``4ddalla`` included); the
    round-trip never migrates or destroys the anchor. Parsed-URL checks cover
    dialect/host/port and a present database name; the scratch name is generated
    here (never taken from configuration) and must not collide with the anchor,
    the maintenance DB ``postgres``, or protected names. No connection is opened
    and no target is modified here -- the live server/privilege pre-flight runs
    in ``_isolated_roundtrip`` right before anything is created.
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
        raise IsolatedTargetError(f"target must use the {_ALLOWED_DRIVERNAME} dialect")
    if url.host not in _ALLOWED_HOSTS or url.port != _ALLOWED_PORT:
        raise IsolatedTargetError(
            "target must be the local development loopback endpoint"
        )
    if not url.database:
        raise IsolatedTargetError("target URL has no database name")
    scratch = f"{_SCRATCH_PREFIX}{uuid.uuid4()}"
    if scratch in {_MAINTENANCE_DB, *_PROTECTED_DBNAMES, url.database}:
        raise IsolatedTargetError(
            "generated scratch name collides with a real database"
        )
    return url, scratch


def _docker_inspect_json(container: str) -> object:
    """Read-only ``docker inspect`` payload for one named container.

    Raises ``RuntimeError`` (static, credential-free text) when the CLI/engine
    is unavailable, the container is missing, the call times out, or the
    payload cannot be parsed: identification uncertainty aborts the isolated
    round-trip before any DDL is attempted.
    """
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{json .}}", container],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError:
        raise RuntimeError(
            "docker CLI is not available; cannot identify the target container"
        ) from None
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "docker inspect timed out; container identification is uncertain"
        ) from None
    if result.returncode != 0:
        raise RuntimeError(
            "docker inspect failed; container identification is uncertain"
        ) from None
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        raise RuntimeError("docker inspect payload could not be parsed") from None
    if not isinstance(payload, dict):
        raise TypeError("docker inspect payload must be an object")
    return payload


def _docker_container_context(
    container: str = _EXPECTED_CONTAINER,
) -> dict[str, object]:
    """Identify the expected local container from Docker metadata (read-only)."""
    return _container_from_payload(_docker_inspect_json(container), container)


def _container_from_payload(payload: object, container: str) -> dict[str, object]:
    """Validate a parsed ``docker inspect`` payload (seam for DB-free tests).

    Confirms: a running container with the expected name; the expected image and
    Compose project/service; the published binding ``127.0.0.1:5432 ->
    container 5432``; and extracts the container's network gateway address(es)
    -- the value(s) the server-observed client peer is compared against.
    Raises ``RuntimeError`` on any missing/mismatched metadata: identification
    failure; not a boundary to widen.
    """
    if not isinstance(payload, dict):
        raise TypeError("docker inspect payload must be an object")
    if str(payload.get("Name", "")).lstrip("/") != container:
        raise RuntimeError("docker container identity does not match expectation")
    state = payload.get("State")
    if not isinstance(state, dict) or state.get("Running") is not True:
        raise RuntimeError("docker container is not running")
    config = payload.get("Config")
    config = config if isinstance(config, dict) else {}
    image = str(config.get("Image", ""))
    image_ref = image.split("@", 1)[0]
    if image_ref != _EXPECTED_IMAGE:
        raise RuntimeError(
            "docker container image does not match the compose definition"
        )
    labels = config.get("Labels")
    if not isinstance(labels, dict):
        raise TypeError("docker Compose metadata must be a mapping")
    if labels.get("com.docker.compose.project") != _EXPECTED_COMPOSE_PROJECT:
        raise RuntimeError("docker Compose project does not match the expected project")
    if labels.get("com.docker.compose.service") != _EXPECTED_COMPOSE_SERVICE:
        raise RuntimeError("docker Compose service does not match the expected service")
    container_id = str(payload.get("Id", ""))
    if not container_id:
        raise RuntimeError("docker container identifier is unavailable")
    network_settings = payload.get("NetworkSettings")
    network_settings = network_settings if isinstance(network_settings, dict) else {}
    ports = network_settings.get("Ports")
    ports = ports if isinstance(ports, dict) else {}
    published = ports.get(_EXPECTED_PUBLISHED[0])
    published = published if isinstance(published, list) else []
    bindings = [p for p in published if isinstance(p, dict)]
    if (
        len(bindings) != 1
        or bindings[0].get("HostIp") != _EXPECTED_PUBLISHED[1]
        or bindings[0].get("HostPort") != _EXPECTED_PUBLISHED[2]
    ):
        raise RuntimeError(
            "docker published port does not match the expected 127.0.0.1:5432 binding"
        )
    networks = network_settings.get("Networks")
    networks = networks if isinstance(networks, dict) else {}
    gateways: set[str] = set()
    for network in networks.values():
        if not isinstance(network, dict):
            continue
        gateway = network.get("Gateway")
        if isinstance(gateway, str) and gateway.strip():
            gateways.add(gateway.strip())
        ipam = network.get("IPAMConfig")
        if isinstance(ipam, list):
            for entry in ipam:
                if isinstance(entry, dict):
                    gateway = entry.get("Gateway")
                    if isinstance(gateway, str) and gateway.strip():
                        gateways.add(gateway.strip())
    return {
        "container": container,
        "id": container_id,
        "image": image,
        "project": _EXPECTED_COMPOSE_PROJECT,
        "service": _EXPECTED_COMPOSE_SERVICE,
        "published": _EXPECTED_PUBLISHED,
        "gateways": frozenset(gateways),
        "running": True,
    }


def _context_gateways(container_context: object) -> frozenset[str]:
    """Extract the confirmed gateway set from a container context (empty if absent)."""
    if not isinstance(container_context, dict):
        return frozenset()
    gateways = container_context.get("gateways")
    if not isinstance(gateways, (set, frozenset)):
        return frozenset()
    return frozenset(
        item for item in gateways if isinstance(item, str) and item.strip()
    )


def _check_live_server(connection, *, container_context: object = None) -> None:
    """Pre-flight a maintenance connection before any DDL is attempted.

    Verifies the live PostgreSQL identity, the connection peer, and the current
    role's CREATE/DROP capability, and that a supplied container context (from
    ``_docker_container_context``) matches the deployment being verified;
    insufficient identification or privilege stops the round-trip before
    anything is created or dropped. Query results are inspected, never echoed.

    Peer policy: NULL (local socket) and loopback peers are always accepted;
    otherwise the peer must match a network gateway confirmed from Docker
    metadata for the expected project container (``container_context``).
    Without a usable context, only loopback/NULL is accepted. An address is
    never trusted from constants, a private-range blanket rule, or a database
    name -- Docker metadata and/or a direct loopback connection must identify
    the path, and uncertainty refuses. This allowance is scoped to the isolated
    verification harness and does not modify the service connection policy.
    """
    version = connection.execute(text("SHOW server_version")).scalar()
    if not isinstance(version, str) or not version.strip():
        raise RuntimeError("could not verify the PostgreSQL server identity")
    user = connection.execute(text("SELECT current_user")).scalar()
    if not isinstance(user, str) or not user.strip():
        raise RuntimeError("could not verify the PostgreSQL role identity")
    peer = connection.execute(text("SELECT inet_client_addr()")).scalar()
    if peer is not None:
        # psycopg3/SQLAlchemy may surface inet as an ipaddress object; compare
        # the normalized textual address against the same exact allowlist.
        peer_text = peer if isinstance(peer, str) else str(peer)
        if peer_text not in _ALLOWED_HOSTS and peer_text not in _context_gateways(
            container_context
        ):
            raise RuntimeError(
                "connection peer is not the expected local loopback address or a "
                "metadata-confirmed gateway for the expected container; an "
                "unidentifiable network path stops the round-trip"
            )
    can_create = connection.execute(
        text("SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    if can_create is not True:
        raise RuntimeError(
            "current role cannot create databases; refuse the isolated round-trip"
        )


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
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": scratch},
            ).fetchone()
        if row is not None:
            raise RuntimeError("scratch database still present after drop")
    finally:
        maintenance_engine.dispose()


def _isolated_schema_state(
    database_url: str,
) -> tuple[bool, frozenset[str], str | None]:
    """Read (probe present, domain tables present, alembic revision) from target.

    Read-only introspection of one database; the caller decides which state is
    acceptable at each phase of the isolated round-trip.
    """
    engine = create_db_engine(database_url)
    try:
        names = set(inspect(engine).get_table_names())
        revision: str | None
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
    except SQLAlchemyError:
        raise RuntimeError("isolated database schema state could not be read") from None
    finally:
        engine.dispose()
    domain = frozenset(name for name in _DOMAIN_TABLES if name in names)
    return _PROBE_TABLE in names, domain, revision


def _enable_postgis(engine) -> None:
    """Enable the PostGIS extension in a fresh scratch database.

    A geography column cannot exist without the extension, and a newly created
    database does not inherit it; a failure (missing package or insufficient
    privilege) aborts the round-trip -- nothing here escalates privileges.
    """
    try:
        with engine.connect() as connection:
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            row = connection.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'postgis'")
            ).fetchone()
    except Exception:  # noqa: BLE001 - driver/permission errors vary; static text only
        raise RuntimeError(
            "PostGIS extension could not be enabled on the isolated scratch "
            "database; aborting"
        ) from None
    if row is None or not row[0]:
        raise RuntimeError(
            "PostGIS is not available on the isolated scratch database; aborting"
        )


def _assert_connection_database(database_url: object, expected_database: str) -> None:
    """Read the database the live connection actually landed on.

    The configured target and the server-observed ``current_database()`` must
    agree: this is what ties a run to the intended database rather than a
    same-server default. Read-only; no URL material appears in failures.
    """
    engine = create_db_engine(database_url)
    try:
        with engine.connect() as connection:
            current = connection.execute(text("SELECT current_database()")).scalar()
    finally:
        engine.dispose()
    assert current == expected_database, (
        "the live connection did not land on the intended database; "
        "nothing further is attempted"
    )


def _assert_single_location_gist_index(database_url: str) -> None:
    """The domain schema must carry exactly one GiST index on stores.location."""
    engine = create_db_engine(database_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename = 'stores' AND indexdef ILIKE '%gist%'"
                )
            ).fetchall()
    finally:
        engine.dispose()
    assert [row[0] for row in rows] == ["ix_stores_location_gist"], (
        "expected exactly one GiST index named ix_stores_location_gist on "
        f"stores.location, found {len(rows)}"
    )


def _assert_constraints_enforced(database_url: str) -> None:
    """FK/CHECK violations must fail on the live schema (scratch DB only)."""
    engine = create_db_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO brands (id, canonical_name) VALUES "
                    "('00000000-0000-0000-0000-0000000000b0', 'probe-brand')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO stores (id) VALUES ('00000000-0000-0000-0000-0000000000b1')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO sources (channel_type, canonical_url, collection_permission) "
                    "VALUES ('probe', 'https://example.invalid/probe', 'ALLOWED')"
                )
            )
        violations = (
            (
                "source_links FK (dangling source)",
                (
                    "INSERT INTO source_links (id, source_id, identity_status) VALUES "
                    "('00000000-0000-0000-0000-0000000000c1', "
                    "'00000000-0000-0000-0000-0000000000ff', 'VERIFIED')"
                ),
            ),
            (
                "source_links CHECK (brand xor store target)",
                (
                    "INSERT INTO source_links (id, source_id, brand_id, store_id, identity_status) VALUES "
                    "('00000000-0000-0000-0000-0000000000c2', "
                    "'00000000-0000-0000-0000-0000000000b2', "
                    "'00000000-0000-0000-0000-0000000000b0', "
                    "'00000000-0000-0000-0000-0000000000b1', 'VERIFIED')"
                ),
            ),
            (
                "source_links CHECK (identity_status value)",
                (
                    "INSERT INTO source_links (id, source_id, identity_status) VALUES "
                    "('00000000-0000-0000-0000-0000000000c3', "
                    "'00000000-0000-0000-0000-0000000000b3', 'NOT_A_STATUS')"
                ),
            ),
        )
        for _label, statement in violations:
            with engine.begin() as connection, pytest.raises(IntegrityError):
                connection.execute(text(statement))
    finally:
        engine.dispose()


def _assert_geography_roundtrip(database_url: str) -> None:
    """A geography point stores and answers a ST_DWithin query (scratch DB)."""
    engine = create_db_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO stores (id, location) VALUES "
                    "('00000000-0000-0000-0000-0000000000b4', "
                    "ST_SetSRID(ST_Point(1, 2), 4326)::geography), "
                    "('00000000-0000-0000-0000-0000000000b5', "
                    "ST_SetSRID(ST_Point(3, 3), 4326)::geography)"
                )
            )
        with engine.connect() as connection:
            srid = connection.execute(
                text("SELECT ST_SRID(location) FROM stores LIMIT 1")
            ).scalar()
            near = connection.execute(
                text(
                    "SELECT count(*) FROM stores WHERE ST_DWithin("
                    "location, ST_GeographyFromText('SRID=4326;POINT(1 2)'), 100)"
                )
            ).scalar_one()
    finally:
        engine.dispose()
    assert srid == 4326
    assert near == 1


def _assert_orm_schema_matches(database_url: str) -> None:
    """ORM metadata for the domain tables is a subset of the live schema."""
    engine = create_db_engine(database_url)
    try:
        inspector = inspect(engine)
        assert _DOMAIN_TABLES <= set(inspector.get_table_names())
        for name in _DOMAIN_TABLES:
            model = Base.metadata.tables[name]
            live_columns = {column["name"] for column in inspector.get_columns(name)}
            assert set(model.columns.keys()) <= live_columns, name
            live_pk = set(inspector.get_pk_constraint(name)["constrained_columns"])
            assert set(model.primary_key.columns.keys()) <= live_pk, name
    finally:
        engine.dispose()


def _isolated_roundtrip(database_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """Run the released chain in phases: 001 -> head -> 001 -> head.

    Scratch schema state is asserted at each phase: 001 must show the
    verification probe; head must show it dropped with the six domain tables;
    the 001 downgrade must remove the domain tables and restore the probe shape
    (schema only -- rows are not recovered); the final head must be the released
    state again. The configured database is used only as the loopback server
    anchor; the anchor and scratch connections are each verified to have landed
    on the intended database. A live pre-flight verifies the server identity,
    the loopback-or-metadata-confirmed peer, and the CREATE/DROP privilege of
    the connecting role (container identified from Docker metadata); the scratch
    database has PostGIS enabled as a DDL prerequisite, schema state is asserted
    at every phase, and constraint/geography/index/metadata checks run against
    the final head state. The scratch is dropped and verified gone afterwards --
    including on failure. If the target cannot be identified with certainty,
    nothing is created, migrated, or dropped.
    """
    server_url, scratch = plan_isolated_target(database_url, enabled=True)
    container_context = _docker_container_context()
    maintenance_engine = create_db_engine(server_url.set(database=_MAINTENANCE_DB))
    created = False
    try:
        _assert_connection_database(server_url, server_url.database)
        with maintenance_engine.connect() as connection:
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
            _check_live_server(connection, container_context=container_context)
            connection.execute(text(f'CREATE DATABASE "{scratch}"'))
            created = True
        scratch_engine = create_db_engine(server_url.set(database=scratch))
        try:
            _enable_postgis(scratch_engine)
        finally:
            scratch_engine.dispose()
        target_url = server_url.set(database=scratch)
        _assert_connection_database(target_url, scratch)
        monkeypatch.setenv(
            "DATABASE_URL", target_url.render_as_string(hide_password=False)
        )
        # the URL actually in force must be the scratch database -- the
        # configured general database is only used as the server anchor
        # credentials are passed via the internal environment variable only;
        # they are never printed, logged, or written anywhere by this test
        assert get_database_url().endswith(f"/{scratch}")
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        # phased verification against the released chain: 001 creates the
        # verification probe; 002 drops it and creates the domain tables; the
        # 001 downgrade restores the probe shape (schema only, no row recovery)
        command.upgrade(config, "001")
        assert _isolated_schema_state(target_url) == (True, frozenset(), "001")
        command.upgrade(config, "head")
        assert _isolated_schema_state(target_url) == (False, _DOMAIN_TABLES, "002")
        command.downgrade(config, "001")
        assert _isolated_schema_state(target_url) == (True, frozenset(), "001")
        command.upgrade(config, "head")
        assert _isolated_schema_state(target_url) == (False, _DOMAIN_TABLES, "002")
        _assert_constraints_enforced(target_url)
        _assert_geography_roundtrip(target_url)
        _assert_single_location_gist_index(target_url)
        _assert_orm_schema_matches(target_url)
    finally:
        if created:
            _drop_scratch(maintenance_engine, scratch)
        else:
            maintenance_engine.dispose()
    return scratch


def _make_probe_app(*, table: str | None = None) -> FastAPI:
    """Tiny app reusing the app's DB error handlers and ``get_db`` dependency.

    ``Depends`` in a default marks a FastAPI dependency-injection position
    (B008 suppressed deliberately; FastAPI evaluates it, it is not called here).
    """
    app = FastAPI()
    app.add_exception_handler(DatabaseUnavailableError, database_unavailable_handler)
    app.add_exception_handler(
        DatabaseConfigurationError, database_configuration_handler
    )

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
            db.execute(text(f"INSERT INTO {quoted} (id) VALUES (1)"))
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
    assert (
        get_database_url({"DATABASE_URL": f"  {_UNREACHABLE_URL}  "})
        == _UNREACHABLE_URL
    )


def test_url_rendering_default_masks_password() -> None:
    """``str(URL)`` masks the password; the explicit full form is opt-in.

    The isolated round-trip hands the URL to the environment for subprocess
    style use, so the full form is used internally there (never logged); the
    default rendering must stay masked. Values are synthetic, never real.
    """
    from sqlalchemy.engine import URL

    synthetic = "synthetic-pw"
    url = URL.create(
        "postgresql+psycopg", "synthetic-user", synthetic, "127.0.0.1", 5432, "4ddalla"
    )
    assert synthetic not in str(url)
    assert synthetic not in str(url.set(database="p1db02_iso_x"))
    assert synthetic in url.render_as_string(hide_password=False)


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
        DisconnectionError("connection invalidated"),
        SqlAlchemyTimeoutError("pool timed out"),
        psycopg.OperationalError("connection refused"),
        psycopg.InterfaceError("cannot use connection"),
        SqlAlchemyOperationalError(
            "SELECT 1", {}, psycopg.OperationalError("bootstrap")
        ),
        SqlAlchemyOperationalError("SELECT 1", {}, psycopg.InterfaceError("bootstrap")),
    ],
)
def test_connection_failures_are_recognized(exc: Exception) -> None:
    """Connection-class failures normalize, from driver cause or engine level."""
    assert _is_connection_failure(exc) is True


@pytest.mark.parametrize(
    "exc",
    [
        IntegrityError("INSERT", {}, Exception("duplicate key")),
        ProgrammingError("SELECT", {}, Exception("syntax error")),
        SQLAlchemyError("generic database error"),
        # OperationalError is not connection loss on class name alone:
        SqlAlchemyOperationalError("SELECT 1", {}, Exception("server-side failure")),
        SqlAlchemyOperationalError("SELECT 1", {}, None),
    ],
)
def test_non_connection_errors_are_not_unavailable(exc: Exception) -> None:
    """Constraints / query errors / unknowns must not be reported as outage (503)."""
    assert _is_connection_failure(exc) is False


class _RecordingSession:
    """Session double whose rollback fails, for cleanup-order checks."""

    def __init__(self) -> None:
        self.closed = False
        self.rollback_calls = 0

    def rollback(self) -> None:
        self.rollback_calls += 1
        raise RuntimeError("rollback failed on purpose")

    def close(self) -> None:
        self.closed = True


def _recording_session_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> list[_RecordingSession]:
    created: list[_RecordingSession] = []

    def sessionmaker(**_kwargs: object) -> object:
        def make() -> _RecordingSession:
            session = _RecordingSession()
            created.append(session)
            return session

        return make

    monkeypatch.setattr(dependencies, "sessionmaker", sessionmaker)
    monkeypatch.setattr(dependencies, "get_engine", lambda: object())
    return created


def test_get_db_rollback_failure_keeps_connection_error_static_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rollback failing must not mask the original error or its classification."""
    created = _recording_session_factory(monkeypatch)
    gen = dependencies.get_db()
    next(gen)
    with pytest.raises(DatabaseUnavailableError) as excinfo:
        gen.throw(psycopg.OperationalError("connect failed"))
    assert "database connection failed" in str(excinfo.value)
    assert created[0].rollback_calls == 1
    assert created[0].closed is True  # cleanup still attempted


def test_get_db_rollback_failure_does_not_mask_other_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _recording_session_factory(monkeypatch)
    gen = dependencies.get_db()
    next(gen)
    boom = ValueError("application failure")
    with pytest.raises(ValueError) as excinfo:
        gen.throw(boom)
    assert excinfo.value is boom
    assert created[0].closed is True  # cleanup still attempted


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
        assert (
            isolation_mode_enabled({"DDALLA_TEST_ISOLATED_MIGRATION_DB": value}) is True
        )


def test_guard_refuses_without_mode() -> None:
    with pytest.raises(IsolatedTargetError):
        plan_isolated_target(_DEV_LIKE_URL, enabled=False)


def test_guard_allows_local_general_database_as_anchor() -> None:
    """The dev DB is a valid *anchor*; the scratch is the only target."""
    server_url, scratch = plan_isolated_target(_DEV_LIKE_URL, enabled=True)
    assert server_url.database == "4ddalla"
    assert scratch not in _PROTECTED_DBNAMES | {_MAINTENANCE_DB, "4ddalla"}


def test_guard_never_returns_a_real_name_as_scratch() -> None:
    for url in (_DEV_LIKE_URL, _DEV_LIKE_URL.replace("/4ddalla", "/other")):
        _server_url, scratch = plan_isolated_target(url, enabled=True)
        assert scratch.startswith(_SCRATCH_PREFIX) and "-" in scratch
        assert scratch not in _PROTECTED_DBNAMES and scratch != _MAINTENANCE_DB


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
    server_url, scratch = plan_isolated_target(
        _DEV_LIKE_URL.replace("/4ddalla", "/other"), enabled=True
    )
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


class _FakeResult:
    """Minimal execute()-result double (only ``scalar()`` is used)."""

    def __init__(self, value: object) -> None:
        self._value = value

    def scalar(self) -> object:
        return self._value


class _FakeConnection:
    """Duck-typed connection for ``_check_live_server`` pre-flight checks."""

    def __init__(
        self,
        *,
        server_version: str = "17.12",
        peer: str | None = "127.0.0.1",
        can_create: bool = True,
        user: object = "4ddalla",
    ) -> None:
        self._server_version = server_version
        self._peer = peer
        self._can_create = can_create
        self._user = user

    def execute(self, statement: object) -> _FakeResult:
        text_ = str(statement)
        if "SHOW server_version" in text_:
            return _FakeResult(self._server_version)
        if "inet_client_addr" in text_:
            return _FakeResult(self._peer)
        if "rolcreatedb" in text_:
            return _FakeResult(self._can_create)
        if "current_user" in text_:
            return _FakeResult(self._user)
        raise AssertionError(f"unexpected statement: {text_}")


@pytest.mark.parametrize("peer", ["127.0.0.1", "::1", None])
def test_check_live_server_accepts_loopback_peer(peer: str | None) -> None:
    _check_live_server(_FakeConnection(peer=peer))


@pytest.mark.parametrize("peer", ["172.17.0.1", "10.0.0.5"])
def test_check_live_server_refuses_non_loopback_peer(peer: str) -> None:
    """Bridge/private peers cannot be attributed to the expected project."""
    with pytest.raises(RuntimeError, match="loopback") as excinfo:
        _check_live_server(_FakeConnection(peer=peer))
    assert peer not in str(excinfo.value)


def test_check_live_server_allows_context_confirmed_gateway() -> None:
    """A gateway confirmed from Docker metadata is positive identification."""
    _check_live_server(
        _FakeConnection(peer="172.18.0.1"),
        container_context={"gateways": {"172.18.0.1"}},
    )


def test_check_live_server_refuses_unconfirmed_bridge_peer() -> None:
    """A bridge peer not confirmed by metadata is not attributed to the project."""
    with pytest.raises(RuntimeError, match="loopback") as excinfo:
        _check_live_server(
            _FakeConnection(peer="172.18.0.5"),
            container_context={"gateways": {"172.18.0.1"}},
        )
    assert "172.18.0.5" not in str(excinfo.value)


def test_check_live_server_without_context_stays_strict() -> None:
    """The allowance is context-scoped: no metadata -> loopback/NULL only."""
    with pytest.raises(RuntimeError, match="loopback"):
        _check_live_server(_FakeConnection(peer="172.18.0.1"))


def test_context_gateways_malformed_context_is_empty() -> None:
    assert _context_gateways(None) == frozenset()
    assert _context_gateways({"gateways": "172.18.0.1"}) == frozenset()
    assert _context_gateways({"gateways": {"172.18.0.1"}}) == frozenset({"172.18.0.1"})


def _container_payload(**overrides: object) -> dict[str, object]:
    """Synthetic `docker inspect` payload (test fixture, not policy)."""
    payload: dict[str, object] = {
        "Name": "/4ddalla-db",
        "Id": "0123456789abcdef0123456789abcdef01234567",
        "State": {"Running": True},
        "Config": {
            "Image": "postgis/postgis:17-3.7",
            "Labels": {
                "com.docker.compose.project": "docker",
                "com.docker.compose.service": "db",
            },
        },
        "NetworkSettings": {
            "Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "5432"}]},
            "Networks": {"docker": {"Gateway": "172.18.0.1"}},
        },
    }
    payload.update(overrides)
    return payload


def test_docker_context_identifies_expected_container() -> None:
    """Synthetic payload -> expected identification (no patching needed)."""
    context = _container_from_payload(_container_payload(), "4ddalla-db")
    assert context["container"] == "4ddalla-db"
    assert str(context["id"])
    assert context["project"] == "docker"
    assert context["service"] == "db"
    assert context["published"] == ("5432/tcp", "127.0.0.1", "5432")
    assert context["gateways"] == frozenset({"172.18.0.1"})


@pytest.mark.parametrize(
    "payload",
    [
        "not-a-dict",
        {"Id": "x", "State": {"Running": True}, "Config": {}, "NetworkSettings": {}},
        _container_payload(Name="/other"),
        _container_payload(State={"Running": False}),
        _container_payload(
            Config={
                "Image": "nginx",
                "Labels": {
                    "com.docker.compose.project": "docker",
                    "com.docker.compose.service": "db",
                },
            }
        ),
        _container_payload(Config={"Image": "postgis/postgis:17-3.7"}),
        _container_payload(
            Config={
                "Image": "postgis/postgis:17-3.7",
                "Labels": {
                    "com.docker.compose.project": "other",
                    "com.docker.compose.service": "db",
                },
            }
        ),
        _container_payload(
            Config={
                "Image": "postgis/postgis:17-3.7",
                "Labels": {
                    "com.docker.compose.project": "docker",
                    "com.docker.compose.service": "other",
                },
            }
        ),
        _container_payload(
            NetworkSettings={
                "Ports": {"5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "5432"}]}
            }
        ),
        _container_payload(NetworkSettings={"Ports": {}}),
        _container_payload(Id=""),
    ],
)
def test_docker_context_refuses_uncertain_metadata(payload: object) -> None:
    with pytest.raises((RuntimeError, TypeError)):
        _container_from_payload(payload, "4ddalla-db")


def test_docker_context_without_gateway_still_identifies() -> None:
    """No gateway visible -> context valid, bridge allowance empty (strict)."""
    context = _container_from_payload(
        _container_payload(
            NetworkSettings={
                "Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "5432"}]},
                "Networks": {},
            }
        ),
        "4ddalla-db",
    )
    assert context["gateways"] == frozenset()


@pytest.mark.parametrize(
    "side_effect",
    [
        OSError("docker CLI missing"),
        subprocess.TimeoutExpired("docker", 30),
    ],
)
def test_docker_context_refuses_unusable_inspect(
    monkeypatch: pytest.MonkeyPatch, side_effect: BaseException
) -> None:
    """A failed/timed-out inspect aborts identification; nothing is widened."""
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **k: (_ for _ in ()).throw(side_effect)
    )
    with pytest.raises(RuntimeError):
        _docker_container_context()


def test_check_live_server_refuses_missing_identity_or_privilege() -> None:
    with pytest.raises(RuntimeError, match="server identity"):
        _check_live_server(_FakeConnection(server_version=""))
    with pytest.raises(RuntimeError, match="create databases"):
        _check_live_server(_FakeConnection(can_create=False))


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
            if "test:test" in record.getMessage()
            or "postgresql+psycopg" in record.getMessage()
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
                session.execute(
                    text(f"INSERT INTO {quoted} (id, note) VALUES (1, 'a')")
                )
                session.commit()
                assert (
                    session.execute(text(f"SELECT count(*) FROM {quoted}")).scalar_one()
                    == 1
                )
                session.execute(
                    text(f"INSERT INTO {quoted} (id, note) VALUES (2, 'b')")
                )
                session.rollback()
                assert (
                    session.execute(text(f"SELECT count(*) FROM {quoted}")).scalar_one()
                    == 1
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
            client = TestClient(
                _make_probe_app(table=table), raise_server_exceptions=False
            )
            response = client.get("/db_probe_rollback")
            assert response.status_code == 500
            assert "probe failure" not in response.text
            with Session(engine) as session:
                assert (
                    session.execute(text(f"SELECT count(*) FROM {quoted}")).scalar_one()
                    == 0
                )
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
            client = TestClient(
                _make_probe_app(table=table), raise_server_exceptions=False
            )
            response = client.get("/db_probe_violation")
            assert response.status_code == 500
            assert response.status_code != 503
            with Session(engine) as session:
                assert (
                    session.execute(text(f"SELECT count(*) FROM {quoted}")).scalar_one()
                    == 1
                )
            assert engine.pool.checkedout() == 0
        finally:
            with engine.begin() as connection:
                connection.execute(text(f"DROP TABLE IF EXISTS {quoted}"))
            engine.dispose()


# --- Isolated-migration verification (opt-in; unmet prerequisites FAIL) --------
#
# Kept deliberately OUTSIDE TestLiveDatabase: that class carries its own
# `skipif(not DATABASE_URL)`, which would suppress these tests even when the
# verification was explicitly requested. Without opt-in they skip as before;
# with opt-in they run and a missing configuration/connection is a failure,
# never a silent skip.


@pytest.mark.skipif(
    _skip_isolated_migration(),
    reason=(
        "isolated-migration verification not enabled "
        "(DDALLA_TEST_ISOLATED_MIGRATION_DB=1; default run stays DB-free)"
    ),
)
def test_alembic_roundtrip_on_isolated_scratch_db(
    monkeypatch: pytest.MonkeyPatch,
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(command, "upgrade", boom)
    with pytest.raises(RuntimeError, match="simulated migration failure"):
        _isolated_roundtrip(get_database_url(), monkeypatch)
