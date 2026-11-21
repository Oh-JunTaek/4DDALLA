"""SQLAlchemy 2.x ORM models for the P1-DATA-01 first domain set.

Tables (see ``Docs/P1-DATA-01-physical-draft.md`` for the design mapping and
``alembic`` revision ``002`` for the DDL): ``brands``, ``stores``,
``store_aliases``, ``sources``, ``source_links``, ``source_evidence``.

Physical decisions follow ``Docs/DATA_MODEL.md``; values the documents leave
open -- channel/category/operational taxonomies, alias duplicate policy, URL
normalization, evidence/alias value sets -- are deliberately unconstrained here
and listed as follow-ups instead of being invented. The models target the
PostgreSQL + PostGIS stack (ADR-004).
"""

from __future__ import annotations

import datetime
import uuid

import sqlalchemy as sa
from geoalchemy2 import Geography
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

__all__ = [
    "Brand",
    "Source",
    "SourceEvidence",
    "SourceLink",
    "Store",
    "StoreAlias",
]


def _uuid4() -> uuid.UUID:
    return uuid.uuid4()


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=_uuid4
    )
    canonical_name: Mapped[str] = mapped_column(sa.Text(), nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=_uuid4
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        sa.ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    operational_status: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    location: Mapped[str | None] = mapped_column(  # type: ignore[assignment]
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.Index("ix_stores_location_gist", "location", postgresql_using="gist"),
    )


class StoreAlias(Base):
    __tablename__ = "store_aliases"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=_uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        sa.ForeignKey("stores.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    alias: Mapped[str] = mapped_column(sa.Text(), nullable=False, index=True)
    valid_from: Mapped[datetime.datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    valid_to: Mapped[datetime.datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from",
            name="ck_store_aliases_valid_range",
        ),
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=_uuid4
    )
    channel_type: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    canonical_url: Mapped[str] = mapped_column(sa.Text(), nullable=False, index=True)
    collection_permission: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    permitted_method: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.CheckConstraint(
            "collection_permission IN ('ALLOWED','RESTRICTED','UNKNOWN')",
            name="ck_sources_collection_permission",
        ),
    )


class SourceLink(Base):
    __tablename__ = "source_links"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=_uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        sa.ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        sa.ForeignKey("brands.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        sa.ForeignKey("stores.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    identity_status: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.CheckConstraint(
            "(brand_id IS NOT NULL) <> (store_id IS NOT NULL)",
            name="ck_source_links_exclusive_target",
        ),
        sa.CheckConstraint(
            "identity_status IN ('VERIFIED','REVIEW_REQUIRED','REJECTED')",
            name="ck_source_links_identity_status",
        ),
    )


class SourceEvidence(Base):
    __tablename__ = "source_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=_uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        sa.ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    evidence_type: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    verified_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )
