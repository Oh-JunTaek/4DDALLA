"""P1-DATA-01: first domain schema and removal of the 001 verification table.

Upgrade drops the verification-only ``p1db02_migration_probe`` (P1-DB-02 gain:
real domain tables now exist) and creates the first domain tables with the
constraints/indexes designed per ``Docs/DATA_MODEL.md`` and
``Docs/P1-DATA-01-physical-draft.md``. Because the schema uses a ``geography``
column, the target database must have the PostGIS extension available (enabled
before migrating; a fresh scratch database does not inherit it).

Downgrade reverses the order and restores the probe shape. It is **schema
restoration only**: rows dropped by ``p1db02_migration_probe`` or by any domain
table are NOT restored by a downgrade, and no backup/retention policy is
replaced here. Before this migration is applied to a development database with
real data, the existence/data of the probe table is checked and the schema
compared against the expected 001 state; unexpected state stops the application.

Revision 001 is intentionally not modified.
"""

from __future__ import annotations

import sqlalchemy as sa
from geoalchemy2 import Geography
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

_UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.drop_table("p1db02_migration_probe")

    op.create_table(
        "brands",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("created_at", _UTC, nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            _UTC,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_brands_canonical_name", "brands", ["canonical_name"])

    op.create_table(
        "stores",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "brand_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("operational_status", sa.Text(), nullable=True),
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column("created_at", _UTC, nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            _UTC,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_stores_brand_id", "stores", ["brand_id"])
    op.create_index(
        "ix_stores_location_gist", "stores", ["location"], postgresql_using="gist"
    )

    op.create_table(
        "store_aliases",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("valid_from", _UTC, nullable=True),
        sa.Column("valid_to", _UTC, nullable=True),
        sa.Column("created_at", _UTC, nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            _UTC,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from",
            name="ck_store_aliases_valid_range",
        ),
    )
    op.create_index("ix_store_aliases_store_id", "store_aliases", ["store_id"])
    op.create_index("ix_store_aliases_alias", "store_aliases", ["alias"])

    op.create_table(
        "sources",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("channel_type", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("collection_permission", sa.Text(), nullable=False),
        sa.Column("permitted_method", sa.Text(), nullable=True),
        sa.Column("created_at", _UTC, nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            _UTC,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.CheckConstraint(
            "collection_permission IN ('ALLOWED','RESTRICTED','UNKNOWN')",
            name="ck_sources_collection_permission",
        ),
    )
    op.create_index("ix_sources_canonical_url", "sources", ["canonical_url"])

    op.create_table(
        "source_links",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "store_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("identity_status", sa.Text(), nullable=False),
        sa.Column("created_at", _UTC, nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            _UTC,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.CheckConstraint(
            "(brand_id IS NOT NULL) <> (store_id IS NOT NULL)",
            name="ck_source_links_exclusive_target",
        ),
        sa.CheckConstraint(
            "identity_status IN ('VERIFIED','REVIEW_REQUIRED','REJECTED')",
            name="ck_source_links_identity_status",
        ),
    )
    op.create_index("ix_source_links_source_id", "source_links", ["source_id"])
    op.create_index("ix_source_links_brand_id", "source_links", ["brand_id"])
    op.create_index("ix_source_links_store_id", "source_links", ["store_id"])

    op.create_table(
        "source_evidence",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("evidence_type", sa.Text(), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("verified_at", _UTC, nullable=False),
        sa.Column("created_at", _UTC, nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            _UTC,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_source_evidence_source_id", "source_evidence", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_source_evidence_source_id", table_name="source_evidence")
    op.drop_table("source_evidence")

    op.drop_index("ix_source_links_store_id", table_name="source_links")
    op.drop_index("ix_source_links_brand_id", table_name="source_links")
    op.drop_index("ix_source_links_source_id", table_name="source_links")
    op.drop_table("source_links")

    op.drop_index("ix_sources_canonical_url", table_name="sources")
    op.drop_table("sources")

    op.drop_index("ix_store_aliases_alias", table_name="store_aliases")
    op.drop_index("ix_store_aliases_store_id", table_name="store_aliases")
    op.drop_table("store_aliases")

    op.drop_index(
        "ix_stores_location_gist", table_name="stores", postgresql_using="gist"
    )
    op.drop_index("ix_stores_brand_id", table_name="stores")
    op.drop_table("stores")

    op.drop_index("ix_brands_canonical_name", table_name="brands")
    op.drop_table("brands")

    # Restore the 001-era probe shape (schema only; no rows are restored).
    op.create_table(
        "p1db02_migration_probe",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", _UTC, nullable=True),
    )
