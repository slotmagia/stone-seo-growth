from datetime import datetime, date, timezone
from sqlalchemy import String, Integer, DateTime, Date, ForeignKey, Float, JSON, UniqueConstraint, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title_zh: Mapped[str] = mapped_column(String(255))
    title_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stone_type: Mapped[str] = mapped_column(String(100))
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    verified_fields: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Keyword(Base):
    __tablename__ = "keywords"
    id: Mapped[int] = mapped_column(primary_key=True)
    phrase: Mapped[str] = mapped_column(String(300), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    locale: Mapped[str] = mapped_column(String(16))
    intent: Mapped[str] = mapped_column(String(100))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    source: Mapped[str] = mapped_column(String(150))
    intent_score: Mapped[float] = mapped_column(Float)
    relevance_score: Mapped[float] = mapped_column(Float)
    opportunity_score: Mapped[float] = mapped_column(Float)
    feasibility_score: Mapped[float] = mapped_column(Float)
    priority: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("phrase", "platform", "locale", "product_id", name="uq_keyword_scope"),)

class Content(Base):
    __tablename__ = "contents"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id"))
    platform: Mapped[str] = mapped_column(String(32))
    locale: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    version: Mapped[int] = mapped_column(Integer, default=1)
    review_notes: Mapped[list] = mapped_column(JSON, default=list)
    publication_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publication_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    product: Mapped[Product] = relationship()
    keyword: Mapped[Keyword] = relationship()

class Metric(Base):
    __tablename__ = "metrics"
    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"))
    day: Mapped[str] = mapped_column(String(10))
    platform: Mapped[str] = mapped_column(String(32))
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    qualified_leads: Mapped[int] = mapped_column(Integer, default=0)
    orders: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(32))
    __table_args__ = (UniqueConstraint("content_id", "day", "platform", "source", name="uq_metric_source"),)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class GeoObservation(Base):
    __tablename__ = "geo_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[str] = mapped_column(String(100))
    locale: Mapped[str] = mapped_column(String(16))
    prompt: Mapped[str] = mapped_column(String(800))
    brand_mentioned: Mapped[bool] = mapped_column(default=False)
    company_cited: Mapped[bool] = mapped_column(default=False)
    accuracy_reviewed: Mapped[bool | None] = mapped_column(nullable=True)
    evidence_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str] = mapped_column(String(32), default="manual_sample")


class SiteAuditRun(Base):
    """Historical snapshot; this is not proof of any live crawl/index state."""
    __tablename__ = "site_audit_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_url: Mapped[str] = mapped_column(String(500))
    site_host: Mapped[str] = mapped_column(String(255), index=True)
    source: Mapped[str] = mapped_column(String(32))
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    pages_count: Mapped[int] = mapped_column(Integer)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProductFactRevision(Base):
    """Append-only field-level verification history; never edit old revisions.

    A verified fact remains usable only while its latest revision is verified,
    not expired, and still matches the current catalog field value.
    """
    __tablename__ = "product_fact_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    field_path: Mapped[str] = mapped_column(String(120), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # verified / revoked
    value_snapshot: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON, nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evidence_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer: Mapped[str] = mapped_column(String(120), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (
        UniqueConstraint("product_id", "field_path", "revision", name="uq_product_fact_revision"),
        Index("ix_product_fact_revisions_product_field", "product_id", "field_path"),
    )
