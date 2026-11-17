"""Adopt the existing v0.1 SQLite/PostgreSQL tables without deleting user data.

Revision ID: 0001_baseline
Revises:

Existing v0.1 deployments use SQLAlchemy create_all. This baseline creates
missing tables and respects already existing ones. It deliberately refuses to
drop the pre-existing business schema on downgrade; restore a backup instead.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    def exists(name):
        return sa.inspect(bind).has_table(name)

    if not exists("products"):
        op.create_table("products",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("sku", sa.String(100), nullable=False),
            sa.Column("title_zh", sa.String(255), nullable=False),
            sa.Column("title_en", sa.String(255), nullable=True),
            sa.Column("stone_type", sa.String(100), nullable=False),
            sa.Column("properties", sa.JSON(), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("verified_fields", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_products_sku", "products", ["sku"], unique=True)

    if not exists("keywords"):
        op.create_table("keywords",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("phrase", sa.String(300), nullable=False),
            sa.Column("platform", sa.String(32), nullable=False),
            sa.Column("locale", sa.String(16), nullable=False),
            sa.Column("intent", sa.String(100), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("source", sa.String(150), nullable=False),
            sa.Column("intent_score", sa.Float(), nullable=False),
            sa.Column("relevance_score", sa.Float(), nullable=False),
            sa.Column("opportunity_score", sa.Float(), nullable=False),
            sa.Column("feasibility_score", sa.Float(), nullable=False),
            sa.Column("priority", sa.Float(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("phrase", "platform", "locale", "product_id", name="uq_keyword_scope"),
        )
        op.create_index("ix_keywords_phrase", "keywords", ["phrase"])

    if not exists("contents"):
        op.create_table("contents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("keyword_id", sa.Integer(), sa.ForeignKey("keywords.id"), nullable=False),
            sa.Column("platform", sa.String(32), nullable=False),
            sa.Column("locale", sa.String(16), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("description", sa.String(500), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("review_notes", sa.JSON(), nullable=False),
            sa.Column("publication_url", sa.String(500), nullable=True),
            sa.Column("publication_method", sa.String(50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not exists("metrics"):
        op.create_table("metrics",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("content_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False),
            sa.Column("day", sa.String(10), nullable=False),
            sa.Column("platform", sa.String(32), nullable=False),
            sa.Column("impressions", sa.Integer(), nullable=False),
            sa.Column("clicks", sa.Integer(), nullable=False),
            sa.Column("qualified_leads", sa.Integer(), nullable=False),
            sa.Column("orders", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(32), nullable=False),
            sa.UniqueConstraint("content_id", "day", "platform", "source", name="uq_metric_source"),
        )

    if not exists("audit_events"):
        op.create_table("audit_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("entity_type", sa.String(32), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("details", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not exists("geo_observations"):
        op.create_table("geo_observations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("provider", sa.String(100), nullable=False),
            sa.Column("model_version", sa.String(100), nullable=False),
            sa.Column("locale", sa.String(16), nullable=False),
            sa.Column("prompt", sa.String(800), nullable=False),
            sa.Column("brand_mentioned", sa.Boolean(), nullable=False),
            sa.Column("company_cited", sa.Boolean(), nullable=False),
            sa.Column("accuracy_reviewed", sa.Boolean(), nullable=True),
            sa.Column("evidence_url", sa.String(500), nullable=True),
            sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("source", sa.String(32), nullable=False),
        )

    if not exists("site_audit_runs"):
        op.create_table("site_audit_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("site_url", sa.String(500), nullable=False),
            sa.Column("site_host", sa.String(255), nullable=False),
            sa.Column("source", sa.String(32), nullable=False),
            sa.Column("snapshot_sha256", sa.String(64), nullable=False),
            sa.Column("pages_count", sa.Integer(), nullable=False),
            sa.Column("summary", sa.JSON(), nullable=False),
            sa.Column("issues", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_site_audit_runs_site_host", "site_audit_runs", ["site_host"])


def downgrade():
    raise RuntimeError("Refusing to drop the adopted business schema. Restore from a verified backup.")
