"""Base ORM class for the DB layer.

The first domain models were added with P1-DATA-01 (``app.db.models``:
brands, stores, store_aliases, sources, source_links, source_evidence; Alembic
revision ``002``); further domain sets follow in later tickets, each with its
own migration history entries (see ``Docs/DATA_MODEL.md`` and
``Docs/ENGINE_SPEC.md``).
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase

__all__ = ["Base"]


class Base(DeclarativeBase):
    """Declarative base for all 4 DDALLA domain models."""
