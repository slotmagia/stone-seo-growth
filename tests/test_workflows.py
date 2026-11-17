def test_public_health_and_protected_api(client):
    assert client.get('/health').status_code==200
    assert client.get('/').status_code==200
    assert client.get('/api/v1/products').status_code==401
    assert client.get('/api/v1/products',headers={'X-API-Key':'bad'}).status_code==401

def test_keyword_priority_and_uniqueness(authed,keyword):
    assert keyword['priority']==round(.35*85+.25*90+.2*70+.2*95,2)
    assert len(authed.get('/api/v1/keywords').json())==1

def test_evidence_gate_blocks_unverified_content(authed, keyword):
    r=authed.post('/api/v1/contents/drafts',json={'keyword_id':keyword['id']})
    assert r.status_code==201
    content=r.json()
    assert 'thickness_mm' not in content['body']
    qa=authed.post(f"/api/v1/contents/{content['id']}/validate").json()
    assert qa['status']=='DRAFT'
    assert 'Missing verified product identity: title_en' in qa['review_notes']
    assert authed.post(f"/api/v1/contents/{content['id']}/approve").status_code==409
    assert authed.post(f"/api/v1/contents/{content['id']}/prepare-publication").status_code==409

def test_verified_fact_content_manual_handoff_and_metrics(authed, product, keyword):
    p=authed.post(f"/api/v1/products/{product['id']}/verify",json={'evidence':{
        'title_en':'supplier catalog: p2',
        'stone_type':'supplier specification: p1',
        'properties.thickness_mm':'technical sheet: p5'}})
    assert p.status_code==200,p.text
    item=authed.post('/api/v1/contents/drafts',json={'keyword_id':keyword['id']}).json()
    assert '20、30' in item['body']
    assert 'technical sheet: p5'==item['evidence_snapshot']['properties.thickness_mm']['source']
    cid=item['id']
    assert authed.post(f'/api/v1/contents/{cid}/validate').json()['status']=='VALIDATED'
    assert authed.post(f'/api/v1/contents/{cid}/approve').status_code==409
    assert authed.post(f'/api/v1/contents/{cid}/submit-review').json()['status']=='REVIEW_REQUIRED'
    assert authed.post(f'/api/v1/contents/{cid}/approve').json()['status']=='APPROVED'
    handoff=authed.post(f'/api/v1/contents/{cid}/prepare-publication')
    assert handoff.status_code==200
    assert handoff.json()['requires_external_action'] is True
    assert handoff.json()['mode']=='READ_ONLY_ANALYTICS'
    assert authed.get('/api/v1/dashboard').json()['published_confirmed']==0
    published=authed.post(f'/api/v1/contents/{cid}/confirm-manual-publication',json={'url':'https://example.org/products/black-granite','external_reference':'manual-check-123'})
    assert published.json()['status']=='PUBLISHED'
    assert published.json()['publication_method']=='manual_operator_confirmation'
    r=authed.post('/api/v1/metrics',json={'content_id':cid,'platform':'google','day':'2026-11-17','impressions':100,'clicks':12,'qualified_leads':2,'orders':1})
    assert r.status_code==201,r.text
    assert authed.post('/api/v1/metrics',json={'content_id':cid,'platform':'google','day':'2026-11-17','impressions':100,'clicks':12,'qualified_leads':2,'orders':1}).status_code==409
    dash=authed.get('/api/v1/dashboard').json()
    assert dash['clicks']==12 and dash['qualified_leads']==2 and dash['orders']==1
    events=authed.get('/api/v1/audit-events').json()
    assert any(x['action']=='operator_confirmed_publication' for x in events)

def test_invalid_verification_and_platform_metric_rejected(authed,product,keyword):
    assert authed.post(f"/api/v1/products/{product['id']}/verify",json={'evidence':{'properties.nonexistent':'some real-looking ref'}}).status_code==422
    item=authed.post('/api/v1/contents/drafts',json={'keyword_id':keyword['id']}).json()
    assert authed.post('/api/v1/metrics',json={'content_id':item['id'],'platform':'douyin','day':'2026-11-17','impressions':100,'clicks':12,'qualified_leads':0,'orders':0}).status_code==422
    assert authed.post('/api/v1/metrics',json={'content_id':item['id'],'platform':'google','day':'2026-11-17','impressions':10,'clicks':12,'qualified_leads':0,'orders':0}).status_code==422

def test_repeated_keyword_conflicts(authed,keyword):
    payload={k:keyword[k] for k in ['phrase','platform','locale','intent','product_id','source','intent_score','relevance_score','opportunity_score','feasibility_score']}
    assert authed.post('/api/v1/keywords',json=payload).status_code==409

def test_non_http_publication_url_rejected(authed, product, keyword):
    authed.post(f"/api/v1/products/{product['id']}/verify",json={'evidence':{'title_en':'catalog p2','stone_type':'supplier p1','properties.thickness_mm':'techsheet p9'}})
    cid=authed.post('/api/v1/contents/drafts',json={'keyword_id':keyword['id']}).json()['id']
    for route in ['validate','submit-review','approve','prepare-publication']:
        assert authed.post(f'/api/v1/contents/{cid}/{route}').status_code==200
    assert authed.post(f'/api/v1/contents/{cid}/confirm-manual-publication',json={'url':'file:///etc/passwd','external_reference':'manual-check-123'}).status_code==422

def test_seo_audit_reports_unverified_truth(authed,keyword):
    item=authed.post('/api/v1/contents/drafts',json={'keyword_id':keyword['id']}).json()
    audit=authed.get(f"/api/v1/contents/{item['id']}/seo-audit")
    assert audit.status_code==200
    checks={v['code']:v['pass'] for v in audit.json()['checks']}
    assert checks['product_facts_verified'] is False
    assert checks['keyword_in_title'] is True

def test_geo_observation_is_only_a_sample_not_rank(authed):
    empty=authed.get('/api/v1/geo/report').json()
    assert empty['sample_count']==0
    assert empty['mention_rate'] is None
    a=authed.post('/api/v1/geo/observations',json={
        'provider':'example evaluation', 'model_version':'example-v1', 'locale':'en-US',
        'prompt':'Which granite paving supplier can help?', 'brand_mentioned':True,
        'company_cited':False,'accuracy_reviewed':True})
    assert a.status_code==201,a.text
    report=authed.get('/api/v1/geo/report').json()
    assert report['sample_count']==1 and report['mention_rate']==1.0 and report['citation_rate']==0.0
