"""Database error types shared by the DB layer (P1-DB-02).

Messages are static strings by design: connection failures must never carry
connection strings, hosts, or credentials into logs, reports, or test output.
"""

from __future__ import annotations

__all__ = ["DatabaseConfigurationError", "DatabaseError", "DatabaseUnavailableError"]


class DatabaseError(RuntimeError):
    """Base class for database-layer errors."""


class DatabaseConfigurationError(DatabaseError):
    """Connection configuration is missing or unusable."""


class DatabaseUnavailableError(DatabaseError):
    """PostgreSQL could not be reached or the connection failed."""
