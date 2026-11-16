"""P1-DB-02 migration foundation: single minimal verification table.

Creates ``p1db02_migration_probe`` - a deliberately non-domain table used to
prove Alembic upgrade/downgrade round-trips against the local PostgreSQL 17 /
PostGIS 3.7 development database. 4 DDALLA domain tables are NOT designed here
(DATA_MODEL.md governs them, later tickets define them).

The table name carries the ticket id so it cannot be mistaken for a domain
entity. It is created in migration history only; whether a deployed database
keeps it can be decided later (e.g. drop once real models/migrations exist).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p1db02_migration_probe",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("p1db02_migration_probe")
