import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import Base, engine, get_db
from app.models import Product, Keyword, Content, Metric, AuditEvent, GeoObservation, SiteAuditRun, ProductFactRevision
from app.schemas import ProductCreate, ProductRead, VerifyFields, KeywordCreate, KeywordRead, DraftCreate, ContentRead, ManualPublication, MetricIn, GeoSampleIn, SiteSnapshotIn, ProductFactVerifyIn, ProductFactRevokeIn, ProductFactRevisionRead
from app.security import require_admin
from app.domains.catalog.service import verify
from app.domains.catalog.facts import append_verifications, revoke_fact, effective_facts, current_draft_blockers
from app.domains.catalog.importer import prepare_csv_import, MAX_CSV_BYTES
from app.domains.keywords.service import priority_score
from app.domains.content.service import generate, qa_blockers
from app.domains.publishing.service import publication_package, CAPABILITIES
from app.domains.analytics.service import dashboard
from app.domains.site_audit.service import generate_baseline

@asynccontextmanager
async def lifespan(app:FastAPI):
    # Compatibility for local SQLite demos and TestClient only.
    # PostgreSQL must be migrated with `alembic upgrade head` before startup.
    if engine.dialect.name == "sqlite" and os.getenv("MVP_SQLITE_AUTO_CREATE", "1") == "1":
        Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="Stone SEO/GEO Growth Platform", version="0.1.2", lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
def home():
    return Path(__file__).with_name("web").joinpath("index.html").read_text(encoding="utf-8")

@app.get("/health")
def health():
    return {"status":"ok", "service":"stone-seo-growth", "environment":"mvp"}

from fastapi import APIRouter
api = APIRouter(dependencies=[Depends(require_admin)])

def must_find(db, model, id):
    found = db.get(model, id)
    if not found:
        raise HTTPException(404, detail=f"{model.__name__} {id} not found")
    return found

@api.post("/products", response_model=ProductRead, status_code=201)
def create_product(payload:ProductCreate, db:Session=Depends(get_db)):
    product=Product(**payload.model_dump(),evidence={},verified_fields=[])
    db.add(product)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, detail="SKU already exists")
    db.refresh(product)
    return product


@api.post("/products/import-csv")
async def import_products_csv(request: Request, dry_run: bool = Query(False), db: Session = Depends(get_db)):
    """POST text/csv with raw CSV bytes. Entire batch is transactional."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in ("text/csv", "application/csv"):
        raise HTTPException(415, "Use Content-Type: text/csv and send raw UTF-8 CSV bytes")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_CSV_BYTES:
            raise HTTPException(413, "CSV exceeds 1 MiB limit")
        body.extend(chunk)
    prepared = prepare_csv_import(bytes(body), db)
    if dry_run:
        return {**prepared.report, "dry_run": True}
    if prepared.report["errors"]:
        raise HTTPException(422, detail=prepared.report)
    if not prepared.products:
        raise HTTPException(422, detail="CSV contains no importable products")
    for item in prepared.products:
        db.add(Product(**item.model_dump(), evidence={}, verified_fields=[]))
    try:
        db.flush()
        db.add(AuditEvent(entity_type="catalog_import", entity_id=0,
                          action="csv_products_imported",
                          details={"sha256": prepared.report["sha256"], "count": len(prepared.products)}))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "SKU conflict during commit; the batch was rolled back")
    return {**prepared.report, "imported": len(prepared.products), "dry_run": False}

def _product_view(db: Session, product: Product):
    """Never display expired or legacy-only mirrors as currently verified."""
    result = ProductRead.model_validate(product).model_dump()
    effective = effective_facts(db, product)
    result["evidence"] = {field: fact["source"] for field, fact in effective.items()}
    result["verified_fields"] = sorted(effective)
    return result

@api.get("/products", response_model=list[ProductRead])
def list_products(db:Session=Depends(get_db)):
    return [_product_view(db, product) for product in db.scalars(
        select(Product).order_by(Product.id.desc()).limit(100)).all()]

@api.post("/products/{product_id}/verify", response_model=ProductRead)
def verify_product(product_id:int, payload:VerifyFields, db:Session=Depends(get_db)):
    product = verify(must_find(db,Product,product_id),payload.evidence,db)
    return _product_view(db, product)

@api.post("/products/{product_id}/facts/verify", response_model=ProductRead)
def verify_product_fact(product_id: int, payload: ProductFactVerifyIn, db: Session = Depends(get_db)):
    product = must_find(db, Product, product_id)
    verified = append_verifications(db, product, [payload.model_dump()], source_kind="manual_document")
    return _product_view(db, verified)

@api.post("/products/{product_id}/facts/revoke", response_model=ProductRead)
def revoke_product_fact(product_id: int, payload: ProductFactRevokeIn, db: Session = Depends(get_db)):
    product = must_find(db, Product, product_id)
    revoked = revoke_fact(db, product, field=payload.field_path, reviewer=payload.reviewer, reason=payload.reason)
    return _product_view(db, revoked)

@api.get("/products/{product_id}/facts")
def get_product_facts(product_id: int, db: Session = Depends(get_db)):
    product = must_find(db, Product, product_id)
    revisions = db.scalars(select(ProductFactRevision).where(
        ProductFactRevision.product_id == product_id
    ).order_by(ProductFactRevision.field_path, ProductFactRevision.revision.desc()).limit(1000)).all()
    effective = effective_facts(db, product)
    return {
        "product_id": product_id,
        "effective_facts": effective,
        "history": [ProductFactRevisionRead.model_validate(item) for item in revisions],
        "history_truncated": len(revisions) == 1000,
        "note": "Operator-supplied evidence; source authenticity/reviewer identity are not independently verified. Legacy facts must be reverified.",
    }

@api.post("/keywords",response_model=KeywordRead,status_code=201)
def create_keyword(payload:KeywordCreate,db:Session=Depends(get_db)):
    must_find(db,Product,payload.product_id)
    fields=payload.model_dump()
    fields["priority"]=priority_score(payload.intent_score,payload.relevance_score,payload.opportunity_score,payload.feasibility_score)
    keyword=Keyword(**fields)
    db.add(keyword)
    try: db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,detail="Keyword exists for the same product/channel/locale")
    db.refresh(keyword)
    return keyword

@api.get("/keywords",response_model=list[KeywordRead])
def list_keywords(db:Session=Depends(get_db)):
    return db.scalars(select(Keyword).order_by(Keyword.priority.desc()).limit(100)).all()

@api.post("/contents/drafts",response_model=ContentRead,status_code=201)
def create_draft(payload:DraftCreate,db:Session=Depends(get_db)):
    keyword=must_find(db,Keyword,payload.keyword_id)
    product=must_find(db,Product,keyword.product_id)
    drafted=generate(product,keyword,effective_facts(db,product))
    content=Content(product_id=product.id,keyword_id=keyword.id,platform=keyword.platform,locale=keyword.locale,**drafted)
    db.add(content);db.flush()
    db.add(AuditEvent(entity_type="content",entity_id=content.id,action="draft_created",details={"engine":"evidence_template_v1"}))
    db.commit();db.refresh(content)
    return content

@api.get("/contents",response_model=list[ContentRead])
def list_contents(db:Session=Depends(get_db)):
    return db.scalars(select(Content).order_by(Content.id.desc()).limit(100)).all()

@api.post("/contents/{content_id}/validate",response_model=ContentRead)
def validate_content(content_id:int,db:Session=Depends(get_db)):
    item=must_find(db,Content,content_id)
    if item.status != "DRAFT": raise HTTPException(409,detail="Can only validate a DRAFT")
    blockers=qa_blockers(item) + current_draft_blockers(db,item)
    item.review_notes=blockers
    if not blockers: item.status="VALIDATED"
    db.add(AuditEvent(entity_type="content",entity_id=item.id,action="qa_run",details={"blockers":blockers}))
    db.commit();db.refresh(item)
    return item

@api.post("/contents/{content_id}/submit-review",response_model=ContentRead)
def submit_review(content_id:int,db:Session=Depends(get_db)):
    item=must_find(db,Content,content_id)
    if item.status != "VALIDATED": raise HTTPException(409,detail="QA validation required")
    item.status="REVIEW_REQUIRED"
    db.add(AuditEvent(entity_type="content",entity_id=item.id,action="review_requested"))
    db.commit();db.refresh(item)
    return item

@api.post("/contents/{content_id}/approve",response_model=ContentRead)
def approve(content_id:int,db:Session=Depends(get_db)):
    item=must_find(db,Content,content_id)
    if item.status != "REVIEW_REQUIRED": raise HTTPException(409,detail="Review submission required")
    if qa_blockers(item) or current_draft_blockers(db,item):
        raise HTTPException(422,detail="Evidence requirements not satisfied or draft is stale")
    item.status="APPROVED"
    db.add(AuditEvent(entity_type="content",entity_id=item.id,action="manually_approved"))
    db.commit();db.refresh(item)
    return item

@api.post("/contents/{content_id}/prepare-publication")
def prepare_publication(content_id:int,db:Session=Depends(get_db)):
    item=must_find(db,Content,content_id)
    if item.status not in ("APPROVED","HANDOFF_READY"):
        raise HTTPException(409,detail="Approval required before handoff")
    if current_draft_blockers(db,item):
        raise HTTPException(422,detail="Evidence changed or expired; regenerate draft")
    item.status="HANDOFF_READY"
    db.add(AuditEvent(entity_type="content",entity_id=item.id,action="manual_publication_package_prepared"))
    db.commit()
    return publication_package(item)

@api.post("/contents/{content_id}/confirm-manual-publication",response_model=ContentRead)
def confirm_manual_publication(content_id:int,payload:ManualPublication,db:Session=Depends(get_db)):
    item=must_find(db,Content,content_id)
    if item.status != "HANDOFF_READY": raise HTTPException(409,detail="Prepare publication handoff first")
    if current_draft_blockers(db,item):
        raise HTTPException(422,detail="Evidence changed or expired; do not confirm publication")
    item.status="PUBLISHED"
    item.publication_url=str(payload.url)
    item.publication_method="manual_operator_confirmation"  # not independently verified
    db.add(AuditEvent(entity_type="content",entity_id=item.id,action="operator_confirmed_publication",details={"url":str(payload.url),"reference":payload.external_reference}))
    db.commit();db.refresh(item)
    return item

@api.get("/channels")
def channels():
    return {"capabilities":CAPABILITIES,"note":"No third-party API tokens or authorizations are configured; no external publication is attempted."}

@api.post("/metrics",status_code=201)
def import_metric(payload:MetricIn,db:Session=Depends(get_db)):
    item=must_find(db,Content,payload.content_id)
    if payload.platform != item.platform: raise HTTPException(422,detail="Platform mismatch with content")
    if payload.clicks>payload.impressions:raise HTTPException(422,detail="Clicks cannot exceed impressions in this MVP data model")
    metric=Metric(**{**payload.model_dump(),"day":payload.day.isoformat()})
    db.add(metric)
    try: db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,detail="Metric row already exists for content/date/platform/source")
    db.refresh(metric)
    return {"id":metric.id,"recorded":True,"source":metric.source}

@api.get("/dashboard")
def get_dashboard(db:Session=Depends(get_db)):
    return dashboard(db)

@api.get("/audit-events")
def list_audit_events(db:Session=Depends(get_db)):
    rows=db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(100)).all()
    return [{"id":r.id,"entity_type":r.entity_type,"entity_id":r.entity_id,"action":r.action,"details":r.details,"created_at":r.created_at} for r in rows]


@api.get("/contents/{content_id}/seo-audit")
def seo_audit(content_id:int,db:Session=Depends(get_db)):
    item=must_find(db,Content,content_id)
    checks=[]
    def check(code,valid,reason):
        checks.append({"code":code,"pass":valid,"note":reason})
    check("title_present",bool(item.title),"Page title must be present")
    check("title_length",len(item.title)<=70,"70 characters is a local editorial heuristic, not a search-engine limit")
    check("description_present",bool(item.description),"Meta description should be populated")
    check("description_length",len(item.description)<=160,"160 characters is a local editorial heuristic, not a search-engine limit")
    check("h1_present",item.body.startswith("# "),"Content should have a primary heading")
    check("product_facts_verified",not (qa_blockers(item) or current_draft_blockers(db,item)),"Product facts must pass evidence quality gate and remain current")
    check("keyword_in_title",item.keyword.phrase.lower() in item.title.lower(),"Target topic should be apparent in title")
    return {"content_id":item.id,"checks":checks,"pass_count":sum(x['pass'] for x in checks),"total":len(checks),"note":"Local editorial checks only; no ranking, crawl or index status is inferred."}

@api.post("/geo/observations",status_code=201)
def add_geo_observation(payload:GeoSampleIn,db:Session=Depends(get_db)):
    data=payload.model_dump()
    if data['evidence_url'] is not None:data['evidence_url']=str(data['evidence_url'])
    sample=GeoObservation(**data,source='manual_sample')
    db.add(sample);db.flush()
    db.add(AuditEvent(entity_type="geo_sample",entity_id=sample.id,action="manual_geo_observation_recorded",details={"provider":sample.provider,"model_version":sample.model_version}))
    db.commit();db.refresh(sample)
    return {"id":sample.id,"source":sample.source}

@api.get("/geo/report")
def geo_report(db:Session=Depends(get_db)):
    samples=db.scalars(select(GeoObservation).order_by(GeoObservation.id.desc()).limit(1000)).all()
    count=len(samples)
    cited=sum(s.company_cited for s in samples)
    mentioned=sum(s.brand_mentioned for s in samples)
    reviewed=[s.accuracy_reviewed for s in samples if s.accuracy_reviewed is not None]
    return {"sample_count":count,"mention_rate":round(mentioned/count,4) if count else None,
            "citation_rate":round(cited/count,4) if count else None,
            "reviewed_accuracy_rate":round(sum(reviewed)/len(reviewed),4) if reviewed else None,
            "accuracy_reviewed_count":len(reviewed),
            "note":"Manual observations only, maximum latest 1000. Not official search rankings or population estimates."}


@api.post("/sites/audits", status_code=201)
def create_site_audit(payload: SiteSnapshotIn, db: Session = Depends(get_db)):
    baseline = generate_baseline(payload)
    record = SiteAuditRun(**{key: baseline[key] for key in (
        "site_url", "site_host", "source", "snapshot_sha256", "pages_count", "summary", "issues")})
    db.add(record)
    db.flush()
    db.add(AuditEvent(entity_type="site_audit", entity_id=record.id,
                      action="static_site_baseline_recorded",
                      details={"source": baseline["source"], "snapshot_sha256": baseline["snapshot_sha256"],
                               "pages_count": baseline["pages_count"]}))
    db.commit()
    db.refresh(record)
    return {"id": record.id, **baseline}

@api.get("/sites/audits")
def list_site_audits(db: Session = Depends(get_db)):
    runs = db.scalars(select(SiteAuditRun).order_by(SiteAuditRun.id.desc()).limit(100)).all()
    return [{"id": item.id, "site_url": item.site_url, "pages_count": item.pages_count,
             "source": item.source, "summary": item.summary, "created_at": item.created_at}
            for item in runs]

@api.get("/sites/audits/{audit_id}")
def get_site_audit(audit_id: int, db: Session = Depends(get_db)):
    item = must_find(db, SiteAuditRun, audit_id)
    return {"id": item.id, "site_url": item.site_url, "site_host": item.site_host,
            "source": item.source, "snapshot_sha256": item.snapshot_sha256,
            "pages_count": item.pages_count, "summary": item.summary, "issues": item.issues,
            "created_at": item.created_at,
            "note": "Static operator-provided snapshot only; no live crawl or ranking verification."}

app.include_router(api,prefix="/api/v1")
