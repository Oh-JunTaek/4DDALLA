"""FastAPI DB session dependency and error mapping (P1-DB-02).

Sessions are per-request and explicitly closed; nothing here commits
automatically - endpoints own their transaction boundaries (commit on success,
rollback on error). Connection failures surface as ``DatabaseUnavailableError``
and configuration problems as ``DatabaseConfigurationError``; both are handled
in ``app.main`` without leaking connection strings or credentials.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine
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


def get_db() -> Iterator[Session]:
    """Yield a per-request Session bound to the cached Engine.

    The session is always closed; a failure mid-request triggers an explicit
    rollback so aborted transactions never leak into the connection pool.
    """
    engine: Engine = get_engine()
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    except Exception:
        session.rollback()
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
