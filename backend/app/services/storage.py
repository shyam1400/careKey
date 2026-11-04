from urllib.parse import quote

import httpx
from fastapi import HTTPException

from app.core.config import get_settings


def _request(method: str, endpoint: str, *, json: dict | None = None) -> dict:
    settings = get_settings()
    base_url = (settings.supabase_url or "").rstrip("/")
    key = (settings.supabase_service_role_key or "").strip()
    if not base_url or not key:
        raise HTTPException(status_code=503, detail="Private document storage is not configured on the backend")
    try:
        response = httpx.request(
            method,
            f"{base_url}/storage/v1{endpoint}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            json=json,
            timeout=20,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Document storage is temporarily unavailable") from None
    if not response.is_success:
        raise HTTPException(status_code=502, detail="Document storage rejected the request")
    if not response.content:
        return {}
    return response.json()


def _object_path(path: str) -> str:
    return quote(path, safe="/")


def create_upload_token(path: str) -> str:
    settings = get_settings()
    bucket = quote(settings.supabase_storage_bucket, safe="")
    result = _request("POST", f"/object/upload/sign/{bucket}/{_object_path(path)}", json={"upsert": False})
    token = result.get("token")
    if not isinstance(token, str) or not token:
        raise HTTPException(status_code=502, detail="Storage did not return an upload token")
    return token


def create_download_url(path: str, expires_in: int = 60) -> str:
    settings = get_settings()
    bucket = quote(settings.supabase_storage_bucket, safe="")
    result = _request(
        "POST",
        f"/object/sign/{bucket}/{_object_path(path)}",
        json={"expiresIn": expires_in},
    )
    signed_url = result.get("signedURL") or result.get("signedUrl")
    if not isinstance(signed_url, str) or not signed_url:
        raise HTTPException(status_code=502, detail="Storage did not return a download link")
    if signed_url.startswith("http://") or signed_url.startswith("https://"):
        return signed_url
    return f"{(settings.supabase_url or '').rstrip('/')}/storage/v1{signed_url}"


def download_object(path: str, max_bytes: int = 10 * 1024 * 1024) -> bytes:
    """Download a private object server-side for extraction; never expose its bytes or service key."""
    settings = get_settings()
    base_url = (settings.supabase_url or "").rstrip("/")
    key = (settings.supabase_service_role_key or "").strip()
    if not base_url or not key:
        raise HTTPException(status_code=503, detail="Private document storage is not configured on the backend")
    bucket = quote(settings.supabase_storage_bucket, safe="")
    try:
        with httpx.stream(
            "GET", f"{base_url}/storage/v1/object/{bucket}/{_object_path(path)}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=30,
        ) as response:
            if not response.is_success:
                raise HTTPException(status_code=502, detail="Document storage could not read the report")
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(status_code=413, detail="Report exceeds the extraction size limit")
                chunks.append(chunk)
            return b"".join(chunks)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Document storage is temporarily unavailable") from None


def delete_object(path: str) -> None:
    settings = get_settings()
    bucket = quote(settings.supabase_storage_bucket, safe="")
    _request("DELETE", f"/object/{bucket}", json={"prefixes": [path]})
