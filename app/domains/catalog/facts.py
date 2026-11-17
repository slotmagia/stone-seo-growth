"""ProductFact v2: immutable verification/revocation events and effective facts.

Intentionally does not infer that a document is genuine: source references and
reviewer identities are operator assertions, not an external identity check.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditEvent, Product, ProductFactRevision
from app.domains.catalog.service import ALLOWED_ROOTS, get_value


def _revisions(db: Session, product_id: int) -> list[ProductFactRevision]:
    return list(db.scalars(select(ProductFactRevision).where(
        ProductFactRevision.product_id == product_id
    ).order_by(ProductFactRevision.field_path, ProductFactRevision.revision.desc())).all())


def latest_by_field(db: Session, product_id: int) -> dict[str, ProductFactRevision]:
    latest = {}
    for rev in _revisions(db, product_id):
        latest.setdefault(rev.field_path, rev)
    return latest


def effective_facts(db: Session, product: Product, today: date | None = None) -> dict[str, dict]:
    """Only current, unexpired, non-revoked, value-matching v2 facts count."""
    today = today or datetime.now(timezone.utc).date()
    facts = {}
    for field, rev in latest_by_field(db, product.id).items():
        if (rev.action != "verified" or
                (rev.valid_until is not None and rev.valid_until < today)):
            continue
        value = get_value(product, field)
        if value is None or value != rev.value_snapshot:
            continue
        facts[field] = {
            "value": deepcopy(value), "source": rev.evidence_reference,
            "revision_id": rev.id, "revision": rev.revision,
            "valid_until": rev.valid_until.isoformat() if rev.valid_until else None,
        }
    return facts


def _sync_legacy_view(db: Session, product: Product):
    """Compatibility-only mirrors; effective_facts is always the authority."""
    facts = effective_facts(db, product)
    product.evidence = {field: item["source"] for field, item in facts.items()}
    product.verified_fields = sorted(facts)


def _validate_field(product: Product, field: str):
    allowed = ALLOWED_ROOTS | {f"properties.{key}" for key in (product.properties or {})}
    if field not in allowed or get_value(product, field) in (None, "", [], {}):
        raise HTTPException(422, detail=f"Unknown or empty field: {field}")


def append_verifications(db: Session, product: Product, entries: list[dict], *, source_kind: str):
    if not entries:
        raise HTTPException(422, detail="At least one fact is required")
    fields = [entry["field_path"] for entry in entries]
    if len(set(fields)) != len(fields):
        raise HTTPException(422, detail="Duplicate fields in verification batch")
    today = datetime.now(timezone.utc).date()
    for entry in entries:
        _validate_field(product, entry["field_path"])
        if not (entry["evidence_reference"] or "").strip() or len(entry["evidence_reference"].strip()) < 6:
            raise HTTPException(422, detail="Evidence reference must be at least six non-space characters")
        if not (entry["reviewer"] or "").strip():
            raise HTTPException(422, detail="Reviewer is required")
        if entry.get("valid_until") and entry["valid_until"] < today:
            raise HTTPException(422, detail="Evidence has already expired")
    latest = latest_by_field(db, product.id)
    for entry in entries:
        field = entry["field_path"]
        prev = latest.get(field)
        db.add(ProductFactRevision(
            product_id=product.id, field_path=field,
            revision=(prev.revision + 1 if prev else 1), action="verified",
            value_snapshot=deepcopy(get_value(product, field)),
            evidence_reference=entry["evidence_reference"].strip(),
            evidence_sha256=entry.get("evidence_sha256"), reviewer=entry["reviewer"].strip(),
            source_kind=source_kind, valid_until=entry.get("valid_until"),
        ))
    try:
        db.flush()
        _sync_legacy_view(db, product)
        db.add(AuditEvent(entity_type="product", entity_id=product.id,
                          action="facts_verified_v2", details={"fields": sorted(fields), "source_kind": source_kind}))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail="Concurrent fact version conflict; retry after reloading")
    db.refresh(product)
    return product


def revoke_fact(db: Session, product: Product, *, field: str, reviewer: str, reason: str):
    current = latest_by_field(db, product.id).get(field)
    if not current or current.action != "verified":
        raise HTTPException(409, detail="No active fact revision to revoke")
    db.add(ProductFactRevision(
        product_id=product.id, field_path=field, revision=current.revision + 1,
        action="revoked", value_snapshot=deepcopy(current.value_snapshot),
        evidence_reference=None, evidence_sha256=None, reviewer=reviewer.strip(),
        source_kind="manual_revocation", reason=reason.strip(), valid_until=None,
    ))
    try:
        db.flush()
        _sync_legacy_view(db, product)
        db.add(AuditEvent(entity_type="product", entity_id=product.id,
                          action="fact_revoked_v2", details={"field": field, "reason": reason.strip()}))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail="Concurrent fact version conflict; retry after reloading")
    db.refresh(product)
    return product


def current_draft_blockers(db: Session, content) -> list[str]:
    """Block approval if an assertion in the draft is no longer effective."""
    now = effective_facts(db, content.product)
    blockers = []
    for field, original in (content.evidence_snapshot or {}).items():
        current = now.get(field)
        if (not current or current["value"] != original.get("value") or
                current["source"] != original.get("source") or
                current["revision_id"] != original.get("revision_id")):
            blockers.append(f"Evidence changed, expired or revoked: {field}; regenerate draft")
    return blockers
