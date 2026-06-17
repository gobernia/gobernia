import boto3
import app.services.documents.storage as storage


def test_s3_client_pasa_endpoint_cuando_esta_definido(monkeypatch):
    captured = {}
    monkeypatch.setattr(boto3, "client", lambda *a, **k: captured.update(k) or "CLIENT")
    monkeypatch.setattr(storage.settings, "AWS_ACCESS_KEY_ID", "k")
    monkeypatch.setattr(storage.settings, "S3_ENDPOINT_URL", "https://proj.supabase.co/storage/v1/s3")
    storage._s3_client()
    assert captured["endpoint_url"] == "https://proj.supabase.co/storage/v1/s3"


def test_s3_client_sin_endpoint_no_pasa_endpoint_url(monkeypatch):
    captured = {}
    monkeypatch.setattr(boto3, "client", lambda *a, **k: captured.update(k) or "CLIENT")
    monkeypatch.setattr(storage.settings, "AWS_ACCESS_KEY_ID", "k")
    monkeypatch.setattr(storage.settings, "S3_ENDPOINT_URL", "")
    storage._s3_client()
    assert "endpoint_url" not in captured
