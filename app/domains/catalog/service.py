from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import Product, AuditEvent

ALLOWED_ROOTS = {"title_zh", "title_en", "stone_type"}

def get_value(product: Product, field: str):
    if field in ALLOWED_ROOTS:
        return getattr(product, field)
    if field.startswith("properties."):
        key = field.removeprefix("properties.")
        if not key or "." in key:  # flat properties only in first MVP
            return None
        return (product.properties or {}).get(key)
    return None

def verify(product: Product, evidence: dict[str, str], db: Session):
    """v1-compatible endpoint; revisions identify reviewer as legacy API, not a person."""
    from app.domains.catalog.facts import append_verifications
    return append_verifications(db, product, [
        {"field_path": field, "evidence_reference": reference,
         "reviewer": "legacy_api_unattributed"}
        for field, reference in evidence.items()
    ], source_kind="legacy_api")
