import io
import app.services.documents.storage as storage


def test_download_sin_credenciales_devuelve_none(monkeypatch):
    monkeypatch.setattr(storage.settings, "AWS_ACCESS_KEY_ID", "")
    assert storage.download_from_storage("documents/x/y/z.pdf") is None


def test_presigned_sin_credenciales_devuelve_none(monkeypatch):
    monkeypatch.setattr(storage.settings, "AWS_ACCESS_KEY_ID", "")
    assert storage.presigned_get_url("documents/x/y/z.pdf") is None


def test_download_con_credenciales_lee_bytes(monkeypatch):
    monkeypatch.setattr(storage.settings, "AWS_ACCESS_KEY_ID", "AKIA_fake")

    class _FakeS3:
        def get_object(self, Bucket, Key):
            return {"Body": io.BytesIO(b"PDFBYTES")}

    monkeypatch.setattr(storage, "_s3_client", lambda: _FakeS3())
    assert storage.download_from_storage("documents/a/b/c.pdf") == b"PDFBYTES"


def test_presigned_con_credenciales_devuelve_url(monkeypatch):
    monkeypatch.setattr(storage.settings, "AWS_ACCESS_KEY_ID", "AKIA_fake")

    class _FakeS3:
        def generate_presigned_url(self, op, Params, ExpiresIn):
            return f"https://signed/{Params['Key']}?e={ExpiresIn}"

    monkeypatch.setattr(storage, "_s3_client", lambda: _FakeS3())
    url = storage.presigned_get_url("documents/a/b/c.pdf", expires=120)
    assert url.startswith("https://signed/documents/a/b/c.pdf")


def test_download_traga_excepcion_y_devuelve_none(monkeypatch):
    monkeypatch.setattr(storage.settings, "AWS_ACCESS_KEY_ID", "AKIA_fake")

    class _BoomS3:
        def get_object(self, Bucket, Key):
            raise RuntimeError("network down")

    monkeypatch.setattr(storage, "_s3_client", lambda: _BoomS3())
    assert storage.download_from_storage("documents/a/b/c.pdf") is None
