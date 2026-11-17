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

from collections.abc import Iterator

from fastapi import Request
from fastapi.responses import JSONResponse
from psycopg import OperationalError as PsycopgOperationalError
from sqlalchemy.engine import Engine
from sqlalchemy.exc import (
    DisconnectionError,
)
from sqlalchemy.exc import (
    OperationalError as SqlAlchemyOperationalError,
)
from sqlalchemy.exc import (
    TimeoutError as SqlAlchemyTimeoutError,
)
from sqlalchemy.orm import Session, sessionmaker

from .engine import get_engine
from .errors import DatabaseConfigurationError, DatabaseUnavailableError

__all__ = [
    "DatabaseConfigurationError",
    "DatabaseUnavailableError",
    "database_configuration_handler",
    "database_unavailable_handler",
    "get_db",
]

# Only these mean "PostgreSQL could not be reached / the connection failed".
# Constraint violations, query errors and anything else keep their ordinary
# error path -- they must not be reported as a 503 outage.
_CONNECTION_FAILURE_TYPES = (
    SqlAlchemyOperationalError,
    DisconnectionError,
    SqlAlchemyTimeoutError,
    PsycopgOperationalError,
)


def _is_connection_failure(exc: BaseException) -> bool:
    """True only for connection-class failures (SQLAlchemy/psycopg).

    The wrapped driver error (``exc.orig``) is checked as well so the mapping
    stays correct across execution paths.
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
        session.rollback()
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
