"""Append-only ProductFact v2 versioned evidence revisions.

Revision ID: 0002_product_facts
Revises: 0001_baseline
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_product_facts"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if sa.inspect(bind).has_table("product_fact_revisions"):
        # SQLite local-MVP create_all may have precreated this matching table.
        actual = {c["name"] for c in sa.inspect(bind).get_columns("product_fact_revisions")}
        expected = {"id", "product_id", "field_path", "revision", "action", "value_snapshot",
                    "evidence_reference", "evidence_sha256", "reviewer", "source_kind",
                    "valid_until", "reason", "created_at"}
        if actual != expected:
            raise RuntimeError("Existing fact table has incompatible columns; backup and migrate manually")
        uniques = {tuple(sorted(u.get("column_names") or []))
                   for u in sa.inspect(bind).get_unique_constraints("product_fact_revisions")}
        if tuple(sorted(("product_id", "field_path", "revision"))) not in uniques:
            raise RuntimeError("Existing fact table lacks the version uniqueness constraint")
        if "ix_product_fact_revisions_product_field" not in {
                idx["name"] for idx in sa.inspect(bind).get_indexes("product_fact_revisions")}:
            op.create_index("ix_product_fact_revisions_product_field", "product_fact_revisions", ["product_id", "field_path"])
        return
    op.create_table("product_fact_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("field_path", sa.String(120), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("value_snapshot", sa.JSON(), nullable=True),
        sa.Column("evidence_reference", sa.String(500), nullable=True),
        sa.Column("evidence_sha256", sa.String(64), nullable=True),
        sa.Column("reviewer", sa.String(120), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("product_id", "field_path", "revision", name="uq_product_fact_revision"),
    )
    op.create_index("ix_product_fact_revisions_product_field", "product_fact_revisions", ["product_id", "field_path"])


def downgrade():
    # A downgrade that destroys verification history is not an acceptable rollback.
    connection = op.get_bind()
    count = connection.execute(sa.text("SELECT COUNT(*) FROM product_fact_revisions")).scalar_one()
    if count:
        raise RuntimeError("Product facts exist: downgrade would delete evidence history. Back up and plan an explicit data migration.")
    op.drop_index("ix_product_fact_revisions_product_field", table_name="product_fact_revisions")
    op.drop_table("product_fact_revisions")
