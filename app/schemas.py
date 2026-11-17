from typing import Any, Literal
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

Platform = Literal["website", "baidu", "google", "douyin", "domestic_shop", "alibaba_icbu", "geo"]
Locale = Literal["zh-CN", "en-US"]

class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    title_zh: str = Field(min_length=1, max_length=255)
    title_en: str | None = Field(default=None, max_length=255)
    stone_type: str = Field(min_length=1, max_length=100)
    properties: dict[str, Any] = Field(default_factory=dict)

class ProductRead(ProductCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    evidence: dict[str, str]
    verified_fields: list[str]

class VerifyFields(BaseModel):
    # Reference must point to a real record, document or signed manual verification.
    evidence: dict[str, str] = Field(min_length=1)

class ProductFactVerifyIn(BaseModel):
    field_path: str = Field(min_length=1, max_length=120)
    evidence_reference: str = Field(min_length=6, max_length=500)
    reviewer: str = Field(min_length=2, max_length=120)
    evidence_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    valid_until: date | None = None

class ProductFactRevokeIn(BaseModel):
    field_path: str = Field(min_length=1, max_length=120)
    reviewer: str = Field(min_length=2, max_length=120)
    reason: str = Field(min_length=6, max_length=500)

class ProductFactRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    field_path: str
    revision: int
    action: str
    value_snapshot: Any
    evidence_reference: str | None
    evidence_sha256: str | None
    reviewer: str
    source_kind: str
    valid_until: date | None
    reason: str | None
    created_at: Any

class KeywordCreate(BaseModel):
    phrase: str = Field(min_length=2, max_length=300)
    platform: Platform
    locale: Locale
    intent: str = Field(min_length=2, max_length=100)
    product_id: int
    source: str = Field(min_length=2, max_length=150)
    intent_score: float = Field(ge=0, le=100)
    relevance_score: float = Field(ge=0, le=100)
    opportunity_score: float = Field(ge=0, le=100)
    feasibility_score: float = Field(ge=0, le=100)

class KeywordRead(KeywordCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    priority: float

class DraftCreate(BaseModel):
    keyword_id: int

class ContentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    keyword_id: int
    title: str
    description: str
    body: str
    platform: str
    locale: str
    status: str
    version: int
    review_notes: list[str]
    publication_url: str | None
    publication_method: str | None
    evidence_snapshot: dict[str, Any]

class ManualPublication(BaseModel):
    url: HttpUrl
    external_reference: str = Field(min_length=2, max_length=200)

class MetricIn(BaseModel):
    content_id: int
    day: date
    platform: Platform
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    qualified_leads: int = Field(ge=0)
    orders: int = Field(ge=0)
    source: Literal["manual_import", "authorized_api"] = "manual_import"

class GeoSampleIn(BaseModel):
    provider: str = Field(min_length=2, max_length=100)
    model_version: str = Field(min_length=1, max_length=100)
    locale: Locale
    prompt: str = Field(min_length=5, max_length=800)
    brand_mentioned: bool
    company_cited: bool
    accuracy_reviewed: bool | None = None
    evidence_url: HttpUrl | None = None


class SitePageSnapshot(BaseModel):
    url: HttpUrl
    http_status: int = Field(ge=100, le=599)
    title: str | None = Field(default=None, max_length=500)
    meta_description: str | None = Field(default=None, max_length=1000)
    canonical: HttpUrl | None = None
    h1_count: int = Field(ge=0, le=100)
    noindex: bool | None = None
    in_sitemap: bool | None = None

class SiteSnapshotIn(BaseModel):
    site_url: HttpUrl
    source: Literal["manual_import"] = "manual_import"
    pages: list[SitePageSnapshot] = Field(min_length=1, max_length=200)
