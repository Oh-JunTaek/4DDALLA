"""Database configuration for 4 DDALLA (P1-DB-02).

Connection information is read from the ``DATABASE_URL`` environment variable,
e.g.::

    DATABASE_URL=postgresql+psycopg://4ddalla:<password>@127.0.0.1:5432/4ddalla

The value is used only to construct the SQLAlchemy/psycopg connection; it is
never logged, printed, or persisted by this module.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from .errors import DatabaseConfigurationError

__all__ = ["DatabaseConfigurationError", "get_database_url"]

DATABASE_URL_ENV = "DATABASE_URL"


def get_database_url(env: Mapping[str, str] | None = None) -> str:
    """Return the configured database URL.

    Args:
        env: optional mapping source (defaults to ``os.environ``); used by
            tests to avoid mutating process-wide state.

    Raises:
        DatabaseConfigurationError: if the variable is unset or empty.
            The message names the variable only - it never contains a value.
    """
    source: Mapping[str, str] = os.environ if env is None else env
    raw = source.get(DATABASE_URL_ENV)
    if raw is None or not raw.strip():
        raise DatabaseConfigurationError(
            f"{DATABASE_URL_ENV} environment variable is not set; "
            "export it to use the database layer (the value is never printed)"
        )
    return raw.strip()
