from types import SimpleNamespace

from app.services import storage


class _Response:
    is_success = True
    content = b'{"token":"signed-token"}'

    def json(self):
        return {"token": "signed-token"}


def test_upload_token_uses_private_service_key_and_encoded_path(monkeypatch):
    captured = {}
    monkeypatch.setattr(storage, "get_settings", lambda: SimpleNamespace(
        supabase_url="https://example.supabase.co/",
        supabase_service_role_key="server-secret",
        supabase_storage_bucket="medical-documents",
    ))

    def fake_request(method, url, **kwargs):
        captured.update(method=method, url=url, **kwargs)
        return _Response()

    monkeypatch.setattr(storage.httpx, "request", fake_request)

    token = storage.create_upload_token("firebase-uid/folder/file name.pdf")

    assert token == "signed-token"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://example.supabase.co/storage/v1/object/upload/sign/medical-documents/firebase-uid/folder/file%20name.pdf"
    assert captured["headers"]["Authorization"] == "Bearer server-secret"
    assert captured["json"] == {"upsert": False}
