"""FastAPI DB session dependency and error mapping (P1-DB-02, 2nd review).

Sessions are per-request and explicitly closed; nothing here commits
automatically - endpoints own their transaction boundaries (commit on success,
rollback on error). Connection/unavailable and configuration failures surface
as safe JSON errors and never include connection strings or credentials.
Connection-class failures raised while a request uses a session are normalized
to ``DatabaseUnavailableError`` (503); every other failure propagates
unchanged.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from fastapi import Request
from fastapi.responses import JSONResponse
from psycopg import InterfaceError as PsycopgInterfaceError
from psycopg import OperationalError as PsycopgOperationalError
from sqlalchemy.engine import Engine
from sqlalchemy.exc import (
    DisconnectionError,
)
from sqlalchemy.exc import (
    TimeoutError as SqlAlchemyTimeoutError,
)
from sqlalchemy.orm import Session, sessionmaker

from .engine import get_engine
from .errors import DatabaseConfigurationError, DatabaseUnavailableError

logger = logging.getLogger(__name__)

__all__ = [
    "DatabaseConfigurationError",
    "DatabaseUnavailableError",
    "database_configuration_handler",
    "database_unavailable_handler",
    "get_db",
]

# Connection-class failures are identified from evidence, not by class name
# alone: psycopg driver connection classes (connection exceptions and client
# interface errors) as raised directly or wrapped in a SQLAlchemy
# OperationalError's driver cause, plus SQLAlchemy engine/pool-level
# availability errors. An OperationalError without a recognized driver cause
# is deliberately NOT treated as connection loss -- server-side execution
# errors (constraints, query errors, unknowns) keep their ordinary path and
# must not be reported as a 503 outage.
_CONNECTION_FAILURE_TYPES = (
    PsycopgInterfaceError,
    PsycopgOperationalError,
    DisconnectionError,
    SqlAlchemyTimeoutError,
)


def _is_connection_failure(exc: BaseException) -> bool:
    """Classify failure as connection-class from its driver cause.

    Deliberately does not decide by SQLAlchemy exception class name alone:
    OperationalError is a broad DBAPI wrapper, so classification requires the
    wrapped psycopg driver cause (or a direct driver/engine-level failure).
    """
    if isinstance(exc, _CONNECTION_FAILURE_TYPES):
        return True
    orig = getattr(exc, "orig", None)
    return isinstance(orig, _CONNECTION_FAILURE_TYPES)

__all__ = [
    "DatabaseConfigurationError",
    "DatabaseUnavailableError",
    "database_configuration_handler",
    "database_unavailable_handler",
    "get_db",
]


def get_db() -> Iterator[Session]:
    """Yield a per-request Session bound to the cached Engine.

    The session is always closed; a failure mid-request triggers an explicit
    rollback. Connection-class failures (SQLAlchemy/psycopg reaching PostgreSQL)
    are normalized to ``DatabaseUnavailableError`` for the API layer to answer
    503; every other failure propagates unchanged.
    """
    engine: Engine = get_engine()
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    except Exception as exc:
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            # Never let a failing rollback mask the original error or route it
            # through a different class; close below still runs. Static message
            # only -- exception text may carry SQL/URL material.
            logger.debug("session rollback failed; original error preserved")
        if _is_connection_failure(exc):
            raise DatabaseUnavailableError(
                "database connection failed (details withheld; check that "
                "PostgreSQL is reachable and DATABASE_URL is correct - "
                "credentials are never printed)"
            ) from None
        raise
    finally:
        session.close()


async def database_unavailable_handler(request: Request, exc: DatabaseUnavailableError) -> JSONResponse:
    """503 with a static, credential-free body."""
    return JSONResponse(status_code=503, content={"detail": "database unavailable"})


async def database_configuration_handler(
    request: Request, exc: DatabaseConfigurationError
) -> JSONResponse:
    """500 with a static, credential-free body (server misconfiguration)."""
    return JSONResponse(status_code=500, content={"detail": "database configuration error"})
