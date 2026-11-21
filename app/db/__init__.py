"""Application-side database layer for 4 DDALLA (P1-DB-02).

Scope (ticket): connection configuration module, SQLAlchemy 2.x Engine/Session
management, FastAPI DB session dependency, explicit connection-error handling,
ORM ``Base``, and Alembic wiring. P1-DATA-01 (2026-11-21) added the first
domain models in ``app.db.models`` -- brands, stores, store_aliases,
sources, source_links, source_evidence; other domain tables follow in later
approved tickets.

Design notes:
- All configuration comes from environment variables; the module never reads
  dotenv files and never logs connection strings or credentials.
- The default access pattern is synchronous (psycopg 3 via SQLAlchemy's
  ``postgresql+psycopg`` dialect); async drivers are not introduced here.
- Engines are cached per process; tests can ``reset_engine_cache()`` between
  cases that mutate ``DATABASE_URL``.
"""

from __future__ import annotations

from .base import Base
from .config import DatabaseConfigurationError, get_database_url
from .engine import create_db_engine, get_engine, reset_engine_cache
from .errors import DatabaseError, DatabaseUnavailableError

__all__ = [
    "Base",
    "DatabaseConfigurationError",
    "DatabaseError",
    "DatabaseUnavailableError",
    "create_db_engine",
    "get_database_url",
    "get_engine",
    "reset_engine_cache",
]
