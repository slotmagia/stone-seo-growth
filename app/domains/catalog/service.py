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

def verify(product: Product, evidence: dict[str,str], db: Session):
    allowed = ALLOWED_ROOTS | {f"properties.{key}" for key in (product.properties or {})}
    for field, reference in evidence.items():
        if field not in allowed or get_value(product,field) in (None,"",[],{}):
            raise HTTPException(422, detail=f"Unknown or empty field: {field}")
        if not reference or len(reference.strip()) < 6:
            raise HTTPException(422, detail=f"Evidence reference too short: {field}")
    product.evidence = {**(product.evidence or {}), **evidence}
    product.verified_fields = sorted(set(product.verified_fields or []).union(evidence))
    db.add(AuditEvent(entity_type="product", entity_id=product.id, action="fields_verified",details={"fields": sorted(evidence)}))
    db.commit(); db.refresh(product)
    return product
