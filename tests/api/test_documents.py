"""Flask route tests for app/api/documents.py: upload validation boundary
(unsupported extension -> 400, oversize -> 413) and the happy path. Real DB,
real app; only the Celery dispatch is stubbed so the route test doesn't also
have to run the full pipeline (pipeline stages have their own tests).
"""
import io

import pytest

pytestmark = pytest.mark.api


@pytest.fixture(autouse=True)
def stub_celery_dispatch(monkeypatch):
    from app.tasks.processing import process_document_task

    calls = []
    monkeypatch.setattr(process_document_task, "delay", lambda doc_id: calls.append(doc_id))
    return calls


def test_upload_rejects_unsupported_extension(client, tmp_uploads):
    data = {"file": (io.BytesIO(b"not a real file"), "malware.exe")}
    resp = client.post("/api/documents/upload", data=data, content_type="multipart/form-data")

    assert resp.status_code == 400
    assert "Unsupported file type" in resp.get_json()["error"]


def test_upload_rejects_oversize_pdf(client, tmp_uploads, monkeypatch):
    import app.api.documents as documents_api

    monkeypatch.setitem(documents_api.MAX_UPLOAD_BY_TYPE, "pdf", 10)

    oversize_content = b"%PDF-1.4\n" + b"0" * 1000
    data = {"file": (io.BytesIO(oversize_content), "big.pdf")}
    resp = client.post("/api/documents/upload", data=data, content_type="multipart/form-data")

    assert resp.status_code == 413
    assert "too large" in resp.get_json()["error"].lower()


def test_upload_accepts_valid_pdf_and_enqueues_processing(client, tmp_uploads, stub_celery_dispatch):
    data = {"file": (io.BytesIO(b"%PDF-1.4\nminimal pdf content"), "report.pdf")}
    resp = client.post("/api/documents/upload", data=data, content_type="multipart/form-data")

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["file_type"] == "pdf"
    assert body["status"] == "pending"
    assert len(stub_celery_dispatch) == 1


def test_upload_requires_file_or_youtube_url(client, tmp_uploads):
    resp = client.post("/api/documents/upload", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
