"""Offline, operator-provided SEO page inventory baseline; never fetch URLs."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException

from app.schemas import SiteSnapshotIn


def normalize_url(value: str) -> str:
    parts = urlsplit(value)
    path = parts.path.rstrip("/") or "/"
    # A content-equivalent trailing slash is normalized; query remains significant.
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def generate_baseline(snapshot: SiteSnapshotIn) -> dict:
    """Static analysis only. URL/sitemap/status fields are operator assertions."""
    site_host = (urlsplit(str(snapshot.site_url)).hostname or "").lower().removeprefix("www.")
    if not site_host:
        raise HTTPException(422, "Site host is required")
    urls: set[str] = set()
    duplicate_titles: dict[str, list[str]] = defaultdict(list)
    for page in snapshot.pages:
        hostname = (urlsplit(str(page.url)).hostname or "").lower()
        if hostname != site_host and hostname != "www." + site_host and not hostname.endswith("." + site_host):
            raise HTTPException(422, f"Page is outside declared site: {page.url}")
        normalized = normalize_url(str(page.url))
        if normalized in urls:
            raise HTTPException(422, f"Duplicate page URL: {page.url}")
        urls.add(normalized)
        if page.title and page.title.strip():
            duplicate_titles[page.title.strip().casefold()].append(str(page.url))

    issues: list[dict] = []
    def add(page, severity: str, code: str, message: str):
        issues.append({"url": str(page.url), "severity": severity, "code": code, "message": message})

    for page in snapshot.pages:
        if page.http_status >= 400:
            add(page, "error", "http_error", f"HTTP {page.http_status}: investigate broken page")
        elif not 200 <= page.http_status < 300:
            add(page, "warning", "non_2xx", f"HTTP {page.http_status}: inspect redirect or response")
        if page.noindex is True:
            add(page, "warning", "noindex", "Noindex asserted by snapshot; verify indexing intent")
        elif page.noindex is None:
            add(page, "info", "robots_unknown", "Noindex status not supplied; cannot assess")
        if not page.title or not page.title.strip():
            add(page, "error", "missing_title", "Page title is missing")
        else:
            if len(page.title) > 70:
                add(page, "info", "long_title", "Title exceeds local 70-character editorial heuristic")
            if len(duplicate_titles[page.title.strip().casefold()]) > 1:
                add(page, "warning", "duplicate_title", "Title repeats within this supplied sample")
        if not page.meta_description or not page.meta_description.strip():
            add(page, "warning", "missing_description", "Meta description is missing")
        elif len(page.meta_description) > 160:
            add(page, "info", "long_description", "Description exceeds local 160-character heuristic")
        if page.h1_count != 1:
            add(page, "warning", "h1_count", f"Snapshot has {page.h1_count} H1 headings (editorial heuristic: one)")
        if page.in_sitemap is False:
            add(page, "warning", "not_in_sitemap", "Snapshot indicates page is absent from sitemap")
        elif page.in_sitemap is None:
            add(page, "info", "sitemap_unknown", "Sitemap membership not supplied; cannot assess")
        if page.canonical is None:
            add(page, "info", "canonical_unknown", "Canonical not supplied in snapshot; cannot assess")
        elif normalize_url(str(page.canonical)) != normalize_url(str(page.url)):
            add(page, "info", "canonical_differs", "Canonical points to a different URL; review intent")

    issues.sort(key=lambda i: ({"error": 0, "warning": 1, "info": 2}[i["severity"]], i["url"], i["code"]))
    counts = Counter(issue["severity"] for issue in issues)
    payload = snapshot.model_dump(mode="json")
    fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "site_url": str(snapshot.site_url), "site_host": site_host,
        "source": snapshot.source, "snapshot_sha256": fingerprint,
        "pages_count": len(snapshot.pages),
        "summary": {"errors": counts["error"], "warnings": counts["warning"], "info": counts["info"]},
        "issues": issues,
        "note": "Operator-supplied static snapshot only: no live crawl, sitemap fetch, indexing status, or rankings were verified.",
    }
