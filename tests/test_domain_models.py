"""DB-free structural tests for the P1-DATA-01 ORM models.

These checks the mapping contract that a real database would enforce
(UUID primary keys, nullability, FK actions, check constraints, GiST index,
absent-until-policy-confirmed UNIQUE/normalization) using SQLAlchemy's
offline metadata introspection -- no connection required.
"""

from __future__ import annotations

import sqlalchemy as sa
from geoalchemy2 import Geography
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.contracts.enums import CollectionPermissionStatus, SourceIdentityStatus
from app.db import models  # noqa: F401  (registers the tables on Base.metadata)
from app.db.base import Base

EXPECTED_TABLES = {
    "brands",
    "stores",
    "store_aliases",
    "sources",
    "source_links",
    "source_evidence",
}


def _table(name: str) -> sa.Table:
    return Base.metadata.tables[name]


def _check_sqlts(table: sa.Table) -> list[str]:
    return [
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint)
    ]


def _fk_actions(table: sa.Table) -> set[str]:
    return {constraint.ondelete for constraint in table.foreign_key_constraints}


def _pk_is_uuid(table: sa.Table) -> bool:
    pk = next(column for column in table.columns if column.primary_key)
    return isinstance(pk.type, PGUUID)


def test_expected_tables_registered():
    assert set(Base.metadata.tables) >= EXPECTED_TABLES


def test_primary_keys_are_uuid():
    for name in EXPECTED_TABLES:
        assert _pk_is_uuid(_table(name)), name


def test_store_brand_is_nullable_fk():
    brand_id = _table("stores").c.brand_id
    assert brand_id.nullable is True
    assert ("brands.id", "SET NULL") in {
        (element.target_fullname, constraint.ondelete)
        for constraint in _table("stores").foreign_key_constraints
        for element in constraint.elements
    }


def test_store_aliases_valid_range_check():
    checks = _check_sqlts(_table("store_aliases"))
    assert any("valid_to > valid_from" in sql for sql in checks)


def test_sources_permission_values_match_shared_enum():
    values = {status.value for status in CollectionPermissionStatus}
    checks = _check_sqlts(_table("sources"))
    assert any(all(f"'{value}'" in sql for value in values) for sql in checks)


def test_source_links_exclusive_target_and_identity_check():
    checks = _check_sqlts(_table("source_links"))
    identity = {status.value for status in SourceIdentityStatus}
    assert any(
        "(brand_id IS NOT NULL) <> (store_id IS NOT NULL)" in sql for sql in checks
    )
    assert any(all(f"'{value}'" in sql for value in identity) for sql in checks)
    assert _table("source_links").c.brand_id.nullable is True
    assert _table("source_links").c.store_id.nullable is True


def test_source_links_and_evidence_fk_policy():
    assert _fk_actions(_table("source_links")) == {"RESTRICT"}
    assert _fk_actions(_table("source_evidence")) == {"RESTRICT"}
    assert _fk_actions(_table("store_aliases")) == {"RESTRICT"}


def test_store_location_is_nullable_geography_point_4326_with_single_gist():
    location = _table("stores").c.location
    assert location.nullable is True
    assert isinstance(location.type, Geography)
    assert location.type.srid == 4326
    assert location.type.geometry_type.upper() == "POINT"
    indexes = [
        index
        for index in _table("stores").indexes
        if set(index.columns.keys()) == {"location"}
    ]
    # exactly one spatial index on location: the named one. GeoAlchemy2's
    # implicit spatial index is not requested (spatial_index=False on the
    # column), so no duplicate GiST index can exist in the metadata.
    assert [index.name for index in indexes] == ["ix_stores_location_gist"]
    assert indexes[0].dialect_options.get("postgresql", {}).get("using") == "gist"


def test_identity_and_authority_fields_are_distinct_columns():
    """공식성(identity_status) ≠ 수집 권한(collection_permission): 별도 컬럼."""
    source_link_columns = {column.name for column in _table("source_links").columns}
    source_columns = {column.name for column in _table("sources").columns}
    assert "identity_status" in source_link_columns
    assert "collection_permission" in source_columns
    assert "identity_status" not in source_columns
    assert "collection_permission" not in source_link_columns
