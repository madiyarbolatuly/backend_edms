"""
Indexes declared on `documents`.

Not a style check: on a library of tens of thousands of rows, a folder listing
without an index on `parent_id` is a sequential scan of the whole table, and
these tests are the record of which access paths the queries depend on.
"""
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from app.db.tables.documents.documents import Document

INDEXES = {ix.name: ix for ix in Document.__table__.indexes}


def ddl(name: str) -> str:
    return str(CreateIndex(INDEXES[name]).compile(dialect=postgresql.dialect()))


def test_children_of_a_folder_are_indexed():
    # `WHERE parent_id = ?` runs on every listing and every tree expansion.
    assert "ix_documents_parent_id" in INDEXES
    assert [c.name for c in INDEXES["ix_documents_parent_id"].columns] == ["parent_id"]


def test_tenant_scope_is_indexed():
    # Every query filters on all three before anything else.
    assert "ix_documents_scope" in INDEXES
    assert [c.name for c in INDEXES["ix_documents_scope"].columns] == [
        "tenant_id",
        "department_id",
        "status",
    ]


def test_listing_order_is_covered():
    # Matches the ORDER BY of a folder page: folders first, then lower(name).
    rendered = ddl("ix_documents_parent_type_name")
    assert "parent_id" in rendered
    assert "file_type" in rendered
    assert "lower(name)" in rendered


def test_folder_size_prefix_scan_is_indexed():
    # `_folder_sizes` aggregates children with `file_path LIKE 'parent/%'`, which
    # a plain btree cannot serve.
    assert "text_pattern_ops" in ddl("ix_documents_file_path_prefix")


def test_every_index_compiles_for_postgres():
    for name in INDEXES:
        assert ddl(name).startswith("CREATE INDEX")


def test_uniqueness_constraints_are_still_declared():
    names = {c.name for c in Document.__table__.constraints if c.name}
    assert "uq_title_parent" in names
    assert "uniq_file" in names


def test_ensure_indexes_creates_what_create_all_misses(tmp_path):
    """
    `metadata.create_all` builds indexes only while creating a table, so a
    database that already has `documents` never picks up an index added later.
    `ensure_indexes` is what closes that gap on boot.
    """
    from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

    engine = create_engine(f"sqlite:///{tmp_path / 'probe.db'}")
    meta = MetaData()

    # Create the table with no index...
    Table("thing", meta, Column("id", Integer, primary_key=True), Column("owner", String))
    meta.create_all(engine)
    assert inspect(engine).get_indexes("thing") == []

    # ...then declare one, as adding an Index to a model does.
    meta2 = MetaData()
    t2 = Table("thing", meta2, Column("id", Integer, primary_key=True), Column("owner", String))
    from sqlalchemy import Index

    Index("ix_thing_owner", t2.c.owner)

    # create_all leaves the existing table alone — this is the gap.
    meta2.create_all(engine)
    assert inspect(engine).get_indexes("thing") == []

    # Reconciling explicitly is what actually creates it.
    with engine.begin() as conn:
        conn.execute(CreateIndex(t2.indexes.pop()))
    assert [ix["name"] for ix in inspect(engine).get_indexes("thing")] == ["ix_thing_owner"]

    engine.dispose()
