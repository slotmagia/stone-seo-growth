"""P0: approved manual inventory only; no third-party HTTP requests."""

import io

KEY = {"X-API-Key": "test-only-api-key", "Content-Type": "text/csv"}


def csv_post(client, text, *, dry_run=False, authorized=True):
    headers = KEY if authorized else {"Content-Type": "text/csv"}
    return client.post(
        "/api/v1/products/import-csv" + ("?dry_run=true" if dry_run else ""),
        content=text.encode("utf-8") if isinstance(text, str) else text,
        headers=headers,
    )


def test_csv_preview_bom_properties_and_no_side_effects(client, authed):
    raw = ('\ufeffsku,title_zh,title_en,stone_type,property.thickness_mm\n'
           '  g-01 , 花岗岩示例 ,Example Granite,granite,"[20,30]"\n')
    preview = csv_post(client, raw, dry_run=True)
    assert preview.status_code == 200, preview.text
    assert preview.json()["would_import"] == 1
    assert preview.json()["imported"] == 0
    assert len(preview.json()["sha256"]) == 64
    assert authed.get("/api/v1/products").json() == []
    saved = csv_post(client, raw)
    assert saved.status_code == 200, saved.text
    assert saved.json()["imported"] == 1
    rows = authed.get("/api/v1/products").json()
    assert rows[0]["sku"] == "G-01"
    assert rows[0]["properties"]["thickness_mm"] == [20, 30]
    assert rows[0]["verified_fields"] == []
    assert rows[0]["evidence"] == {}
    assert any(e["action"] == "csv_products_imported" for e in authed.get("/api/v1/audit-events").json())


def test_csv_validation_is_all_or_nothing(client, authed):
    raw = "sku,title_zh,stone_type\nA-01,合法示例,granite\nA-02,,marble\n"
    resp = csv_post(client, raw)
    assert resp.status_code == 422
    assert resp.json()["detail"]["errors"][0]["row"] == 3
    assert authed.get("/api/v1/products").json() == []
    assert not authed.get("/api/v1/audit-events").json()


def test_csv_duplicate_in_file_casefold_rejected(client, authed):
    resp = csv_post(client, "sku,title_zh,stone_type\nAA-2,示例,granite\naa-2,重复,marble\n")
    assert resp.status_code == 422
    assert resp.json()["detail"]["errors"][0]["code"] == "duplicate_in_file"
    assert authed.get("/api/v1/products").json() == []


def test_csv_duplicate_against_db_and_no_overwrite(client, authed):
    assert authed.post("/api/v1/products", json={"sku": "p-11", "title_zh": "原始", "stone_type": "granite"}).status_code == 201
    resp = csv_post(client, "sku,title_zh,stone_type\nP-11,修改,marble\nN-02,新建,granite\n", dry_run=True)
    assert resp.status_code == 200
    assert resp.json()["would_import"] == 0
    assert resp.json()["errors"][0]["code"] == "already_exists"
    assert csv_post(client, "sku,title_zh,stone_type\nP-11,修改,marble\nN-02,新建,granite\n").status_code == 422
    products = authed.get("/api/v1/products").json()
    assert len(products) == 1 and products[0]["title_zh"] == "原始"


def test_csv_rejects_bad_header_encoding_property_and_column_count(client):
    bad = [
        (b"sku,stone_type\nB1,granite\n", "invalid_file"),
        (b"sku,title_zh,stone_type\nB1,\xff,granite\n", "invalid_file"),
        (b"sku,title_zh,stone_type\nB1,good,granite,extra\n", "column_count"),
        (b"sku,title_zh,stone_type,property.thickness_mm\nB1,good,granite,[bad\n", "property_json"),
        (b"sku,sku,title_zh,stone_type\nB1,B1,good,granite\n", "invalid_file"),
    ]
    for content, code in bad:
        resp = csv_post(client, content)
        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"]["errors"][0]["code"] == code


def test_csv_auth_content_type_and_payload_limit(client, authed):
    assert csv_post(client, "sku,title_zh,stone_type\nAA,示例,granite\n", authorized=False).status_code == 401
    resp = client.post("/api/v1/products/import-csv", content=b"hello", headers={"X-API-Key": KEY["X-API-Key"]})
    assert resp.status_code == 415
    too_large = b"sku,title_zh,stone_type\n" + b"A" * (1024 * 1024)
    assert csv_post(client, too_large).status_code == 413


def snapshot():
    return {
        "site_url": "https://stones.example.org",
        "pages": [
            {"url": "https://stones.example.org/zh/stone-a", "http_status": 200,
             "title": "示例石材", "meta_description": "示例", "h1_count": 1,
             "in_sitemap": True, "noindex": False,
             "canonical": "https://stones.example.org/zh/stone-a"},
            {"url": "https://stones.example.org/zh/stone-b", "http_status": 404,
             "title": "示例石材", "meta_description": "", "h1_count": 0,
             "in_sitemap": False, "noindex": True,
             "canonical": "https://stones.example.org/zh/stone-a"},
        ],
    }


def test_site_audit_persists_static_baseline_and_reports(authed):
    resp = authed.post("/api/v1/sites/audits", json=snapshot())
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["pages_count"] == 2
    assert data["summary"]["errors"] >= 1
    codes = {x["code"] for x in data["issues"]}
    assert {"http_error", "duplicate_title", "noindex", "not_in_sitemap", "h1_count", "canonical_differs"}.issubset(codes)
    assert "no live crawl" in data["note"]
    audit_id = data["id"]
    assert authed.get(f"/api/v1/sites/audits/{audit_id}").json()["snapshot_sha256"] == data["snapshot_sha256"]
    assert authed.get("/api/v1/sites/audits").json()[0]["id"] == audit_id
    assert any(e["action"] == "static_site_baseline_recorded" for e in authed.get("/api/v1/audit-events").json())


def test_site_audit_rejects_external_domain_and_duplicate_url(authed):
    payload = snapshot()
    payload["pages"][0]["url"] = "https://different-domain.example.com/steal"
    assert authed.post("/api/v1/sites/audits", json=payload).status_code == 422
    dup = snapshot()
    dup["pages"][1]["url"] = "https://stones.example.org/zh/stone-a/"
    assert authed.post("/api/v1/sites/audits", json=dup).status_code == 422
    assert authed.get("/api/v1/sites/audits").json() == []


def test_site_audit_unknown_indicators_do_not_assert_false(authed):
    minimal = {"site_url": "https://stones.example.org", "pages": [
        {"url": "https://stones.example.org/", "http_status": 200, "title": "Home",
         "meta_description": "Intro", "h1_count": 1}
    ]}
    resp = authed.post("/api/v1/sites/audits", json=minimal)
    assert resp.status_code == 201
    codes = {v["code"] for v in resp.json()["issues"]}
    assert "not_in_sitemap" not in codes and "noindex" not in codes
    assert "robots_unknown" in codes and "sitemap_unknown" in codes


def test_site_audit_schema_requires_pages_and_valid_urls(authed):
    assert authed.post("/api/v1/sites/audits", json={"site_url": "http://x.example", "pages": []}).status_code == 422
    data = snapshot()
    data["pages"][0]["url"] = "file:///etc/passwd"
    assert authed.post("/api/v1/sites/audits", json=data).status_code == 422
    assert authed.get("/api/v1/sites/audits/999").status_code == 404
