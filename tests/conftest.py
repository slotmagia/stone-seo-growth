import os
os.environ["ADMIN_API_KEY"] = "test-only-api-key"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db

@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread":False}, poolclass=StaticPool)
    @event.listens_for(engine,"connect")
    def fk_on(connection,record):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(bind=engine)
    session=sessionmaker(bind=engine)
    def override_db():
        with session() as db:yield db
    app.dependency_overrides[get_db]=override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear();engine.dispose()

@pytest.fixture
def authed(client):
    class Client:
        def get(self,url):return client.get(url,headers={"X-API-Key":"test-only-api-key"})
        def post(self,url,json=None):return client.post(url,json=json,headers={"X-API-Key":"test-only-api-key"})
    return Client()

@pytest.fixture
def product(authed):
    data={"sku":"STONE-1","title_zh":"芝麻黑花岗岩","title_en":"Black Granite","stone_type":"granite","properties":{"thickness_mm":[20,30],"finishes":["flamed"]}}
    result=authed.post("/api/v1/products",json=data)
    assert result.status_code==201,result.text
    return result.json()

@pytest.fixture
def keyword(authed,product):
    r=authed.post("/api/v1/keywords",json={"phrase":"granite paving slabs supplier","platform":"google","locale":"en-US","intent":"B2B enquiry","product_id":product["id"],"source":"manual_research","intent_score":85,"relevance_score":90,"opportunity_score":70,"feasibility_score":95})
    assert r.status_code==201,r.text
    return r.json()
