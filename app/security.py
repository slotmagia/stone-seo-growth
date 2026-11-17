import os
from hmac import compare_digest
from fastapi import Header, HTTPException

def require_admin(x_api_key: str | None = Header(default=None)) -> None:
    configured = os.getenv("ADMIN_API_KEY", "")
    if not configured:
        raise HTTPException(status_code=503, detail="ADMIN_API_KEY is not configured")
    if not x_api_key or not compare_digest(x_api_key, configured):
        raise HTTPException(status_code=401, detail="Invalid API key")
