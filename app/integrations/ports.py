"""Contracts for authorized external integrations. No scraping or bypass fallbacks."""
from dataclasses import dataclass
from typing import Protocol, Literal

@dataclass(frozen=True)
class PublishRequest:
    channel: str
    content_id: int
    version: int
    idempotency_key: str

@dataclass(frozen=True)
class PublishResult:
    status: Literal["published","pending_review","manual_handoff","failed"]
    external_id: str | None = None
    url: str | None = None
    error_code: str | None = None

class Publisher(Protocol):
    async def publish(self, request: PublishRequest) -> PublishResult: ...

class SearchMetricsReader(Protocol):
    async def fetch_metrics(self, start_day: str, end_day: str) -> list[dict]: ...
