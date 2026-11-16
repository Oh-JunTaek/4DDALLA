"""ORM base class for 4 DDALLA (P1-DB-02).

Domain models are not defined yet - later tickets add models and the Alembic
migration history follows the documented contract/versioning policy.
Deliberately no models are invented here.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase

__all__ = ["Base"]


class Base(DeclarativeBase):
    """Declarative base for all future 4 DDALLA ORM models."""
