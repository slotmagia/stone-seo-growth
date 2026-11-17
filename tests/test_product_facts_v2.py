"""Versioned evidence, re-verification, expiration, revocation and approval gates."""
from datetime import date, timedelta

from sqlalchemy import select
from app.models import ProductFactRevision
from app.domains.catalog.facts import effective_facts


def verify_fact(authed, product_id, field="stone_type", reference="technical report p. 12", **overrides):
    data = {"field_path": field, "evidence_reference": reference, "reviewer": "quality-manager"}
    data.update(overrides)
    return authed.post(f"/api/v1/products/{product_id}/facts/verify", json=data)


def test_fact_revision_history_and_effective_evidence(authed, product):
    pid = product["id"]
    assert verify_fact(authed, pid, evidence_sha256="a" * 64).status_code == 200
    assert verify_fact(authed, pid, reference="second sample report p. 13").status_code == 200
    result = authed.get(f"/api/v1/products/{pid}/facts")
    assert result.status_code == 200
    facts = result.json()
    assert len(facts["history"]) == 2
    assert [item["revision"] for item in facts["history"]] == [2, 1]
    assert facts["history"][0]["reviewer"] == "quality-manager"
    assert facts["history"][1]["evidence_sha256"] == "a" * 64
    assert facts["effective_facts"]["stone_type"]["source"] == "second sample report p. 13"
    assert facts["effective_facts"]["stone_type"]["revision"] == 2
    assert any(event["action"] == "facts_verified_v2" for event in authed.get('/api/v1/audit-events').json())


def test_revocation_is_append_only_and_facts_not_reused(authed, product, keyword):
    pid = product["id"]
    for field in ("title_en", "stone_type", "properties.thickness_mm"):
        assert verify_fact(authed, pid, field=field).status_code == 200
    draft = authed.post('/api/v1/contents/drafts', json={"keyword_id":keyword["id"]}).json()
    assert 'stone_type' in draft['evidence_snapshot']
    revocation = authed.post(f"/api/v1/products/{pid}/facts/revoke", json={
        "field_path": "stone_type", "reviewer": "quality-manager", "reason": "Superseded supplier document"})
    assert revocation.status_code == 200, revocation.text
    data = authed.get(f"/api/v1/products/{pid}/facts").json()
    assert data["history"][-1]["action"] == "revoked" or any(x["action"] == "revoked" for x in data["history"])
    assert "stone_type" not in data["effective_facts"]
    assert "stone_type" not in revocation.json()["verified_fields"]
    newer = authed.post('/api/v1/contents/drafts', json={"keyword_id":keyword["id"]}).json()
    assert "stone_type" not in newer['evidence_snapshot']
    qa = authed.post(f"/api/v1/contents/{draft['id']}/validate")
    assert qa.status_code == 200
    assert qa.json()["status"] == "DRAFT"
    assert any("stone_type" in note for note in qa.json()["review_notes"])
    assert authed.post(f"/api/v1/products/{pid}/facts/revoke", json={
        "field_path":"stone_type", "reviewer":"quality-manager", "reason":"Duplicate revoke"}).status_code == 409


def test_changed_evidence_requires_regenerated_draft(authed, product, keyword):
    pid = product["id"]
    for field in ("title_en", "stone_type", "properties.thickness_mm"):
        assert verify_fact(authed, pid, field=field).status_code == 200
    draft = authed.post('/api/v1/contents/drafts', json={"keyword_id":keyword["id"]}).json()
    cid = draft['id']
    assert authed.post(f'/api/v1/contents/{cid}/validate').json()['status'] == 'VALIDATED'
    assert authed.post(f'/api/v1/contents/{cid}/submit-review').status_code == 200
    assert verify_fact(authed, pid, field="stone_type", reference="new quarry assessment p. 7").status_code == 200
    rejected = authed.post(f'/api/v1/contents/{cid}/approve')
    assert rejected.status_code == 422
    assert "stale" in rejected.json()['detail']
    newer = authed.post('/api/v1/contents/drafts', json={"keyword_id":keyword["id"]}).json()
    assert newer['evidence_snapshot']['stone_type']['source'] == "new quarry assessment p. 7"


def test_facts_expire_and_expired_input_rejected(authed, client, product):
    pid = product["id"]
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    assert verify_fact(authed, pid, valid_until=yesterday).status_code == 422
    tomorrow = date.today() + timedelta(days=1)
    assert verify_fact(authed, pid, valid_until=tomorrow.isoformat()).status_code == 200
    from app.database import get_db
    # Read through the TestClient fixture's dependency override session.
    generator = client.app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        model = db.get(__import__('app.models',fromlist=['Product']).Product, pid)
        assert "stone_type" in effective_facts(db, model, today=tomorrow)
        assert "stone_type" not in effective_facts(db, model, today=tomorrow + timedelta(days=1))
    finally:
        generator.close()


def test_missing_and_invalid_facts_fail_closed(authed, product):
    pid = product['id']
    assert authed.get(f'/api/v1/products/{pid+777}/facts').status_code == 404
    assert verify_fact(authed,pid,field='properties.other').status_code == 422
    assert verify_fact(authed,pid,evidence_sha256='invalid').status_code == 422
    assert verify_fact(authed,pid,reference='  a  ').status_code == 422
    assert verify_fact(authed,pid,reviewer=' ').status_code == 422
    assert authed.get(f'/api/v1/products/{pid}/facts').json()['history'] == []


def test_legacy_mirror_is_not_authority_for_unreviewed_old_data(authed, client, product, keyword):
    # Simulate a pre-v2 row carrying asserted status but no matching revision.
    from app.models import Product
    from app.database import get_db
    gen = client.app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        model = db.get(Product, product['id'])
        model.verified_fields = ['title_en','stone_type','properties.thickness_mm']
        model.evidence = {v:'old reference' for v in model.verified_fields}
        db.commit()
    finally:
        gen.close()
    draft = authed.post('/api/v1/contents/drafts', json={"keyword_id":keyword['id']}).json()
    assert draft['evidence_snapshot'] == {}
    assert authed.post(f"/api/v1/contents/{draft['id']}/validate").json()['status'] == 'DRAFT'


def test_legacy_endpoint_writes_unattributed_v2_revision(authed, product):
    pid=product['id']
    response=authed.post(f'/api/v1/products/{pid}/verify',json={"evidence":{"stone_type":"supplier specification p.5"}})
    assert response.status_code==200, response.text
    history=authed.get(f'/api/v1/products/{pid}/facts').json()['history']
    assert history[0]['source_kind']=='legacy_api'
    assert history[0]['reviewer']=='legacy_api_unattributed'


def test_same_document_reverified_invalidates_reviewed_draft(authed, product, keyword):
    pid = product['id']
    for field in ('title_en','stone_type','properties.thickness_mm'):
        assert verify_fact(authed,pid,field=field).status_code == 200
    cid = authed.post('/api/v1/contents/drafts',json={'keyword_id':keyword['id']}).json()['id']
    assert authed.post(f'/api/v1/contents/{cid}/validate').json()['status'] == 'VALIDATED'
    assert authed.post(f'/api/v1/contents/{cid}/submit-review').status_code == 200
    assert verify_fact(authed,pid,field='stone_type').status_code == 200
    assert authed.post(f'/api/v1/contents/{cid}/approve').status_code == 422


def test_revoked_after_approval_blocks_handoff(authed, product, keyword):
    pid=product['id']
    for field in ('title_en','stone_type','properties.thickness_mm'):
        assert verify_fact(authed,pid,field=field).status_code == 200
    cid=authed.post('/api/v1/contents/drafts',json={'keyword_id':keyword['id']}).json()['id']
    for action in ('validate','submit-review','approve'):
        assert authed.post(f'/api/v1/contents/{cid}/{action}').status_code==200
    assert authed.post(f'/api/v1/products/{pid}/facts/revoke',json={
        'field_path':'stone_type','reviewer':'quality-manager','reason':'Supplier retracted certification'}).status_code==200
    assert authed.post(f'/api/v1/contents/{cid}/prepare-publication').status_code==422


def test_revoked_after_handoff_blocks_confirmation(authed, product, keyword):
    pid=product['id']
    for field in ('title_en','stone_type','properties.thickness_mm'):
        assert verify_fact(authed,pid,field=field).status_code == 200
    cid=authed.post('/api/v1/contents/drafts',json={'keyword_id':keyword['id']}).json()['id']
    for action in ('validate','submit-review','approve','prepare-publication'):
        assert authed.post(f'/api/v1/contents/{cid}/{action}').status_code==200
    assert authed.post(f'/api/v1/products/{pid}/facts/revoke',json={
        'field_path':'stone_type','reviewer':'quality-manager','reason':'Supplier changed specifications'}).status_code==200
    result=authed.post(f'/api/v1/contents/{cid}/confirm-manual-publication',json={
        'url':'https://example.org/stone','external_reference':'manual-123'})
    assert result.status_code==422


def test_revocation_then_reverification_produces_new_version(authed, product):
    pid=product['id']
    assert verify_fact(authed,pid).status_code==200
    assert authed.post(f'/api/v1/products/{pid}/facts/revoke',json={
        'field_path':'stone_type','reviewer':'quality-manager','reason':'Wrong quarry listed'}).status_code==200
    assert verify_fact(authed,pid,reference='corrected quarry document v2').status_code==200
    result=authed.get(f'/api/v1/products/{pid}/facts').json()
    assert [r['action'] for r in result['history']] == ['verified','revoked','verified']
    assert [r['revision'] for r in result['history']] == [3,2,1]
    assert result['effective_facts']['stone_type']['revision']==3
