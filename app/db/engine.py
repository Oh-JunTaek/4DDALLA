"""SQLAlchemy 2.x Engine/Session management (P1-DB-02).

Synchronous access only (psycopg 3 through the ``postgresql+psycopg`` dialect):
async pool/session complexity is deliberately not introduced at this stage.

The Engine is cached per process; ``reset_engine_cache()`` exists so tests can
point the layer at a different ``DATABASE_URL`` without leaking state between
cases. No function here logs connection strings or credentials.
"""

from __future__ import annotations

import threading

from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError

from .config import get_database_url
from .errors import DatabaseUnavailableError

__all__ = [
    "check_connection",
    "create_db_engine",
    "get_engine",
    "reset_engine_cache",
]

# Short connect timeout so a stopped database fails fast instead of hanging a
# request/worker indefinitely. Seconds.
_CONNECT_TIMEOUT_SECONDS = 10

_ENGINE_LOCK = threading.Lock()
_cached_engine: Engine | None = None


def create_db_engine(database_url: str | object) -> Engine:
    """Create a SQLAlchemy sync Engine for the given URL/URL-object.

    ``pool_pre_ping`` retires stale connections; ``pool_recycle`` bounds the
    connection age. No URL material appears in engine echo/logging output.
    """
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
        connect_args={"connect_timeout": _CONNECT_TIMEOUT_SECONDS},
    )


def get_engine() -> Engine:
    """Return the process-wide Engine, creating it on first use.

    Raises:
        DatabaseConfigurationError: if ``DATABASE_URL`` is not configured.
    """
    global _cached_engine
    if _cached_engine is not None:
        return _cached_engine
    with _ENGINE_LOCK:
        if _cached_engine is None:
            _cached_engine = create_db_engine(get_database_url())
        return _cached_engine


def reset_engine_cache() -> None:
    """Dispose and forget the cached Engine (used by tests; safe to call anytime)."""
    global _cached_engine
    with _ENGINE_LOCK:
        if _cached_engine is not None:
            _cached_engine.dispose()
            _cached_engine = None


def check_connection(engine: Engine) -> None:
    """Open a connection to verify reachability.

    Any SQLAlchemy failure is normalized to ``DatabaseUnavailableError`` whose
    message is static by design - connection strings and credentials never
    appear in it (or in chained output: the original error is suppressed).
    """
    try:
        with engine.connect():
            pass
    except SQLAlchemyError:
        raise DatabaseUnavailableError(
            "database connection failed (details withheld; check that PostgreSQL "
            "is reachable and DATABASE_URL is correct - credentials are never printed)"
        ) from None
