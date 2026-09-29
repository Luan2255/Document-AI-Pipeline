"""Exercise document API endpoints with OCR and LLM services isolated."""

from datetime import date

from fastapi.testclient import TestClient

from app.schemas.document import ExtractedDocumentData
from app.services import processing


def stub_pipeline_services(monkeypatch) -> None:
    """Replace external OCR and model calls with deterministic test values."""

    def fake_ocr(file_path, file_kind, languages, max_pdf_pages):
        """Return text after asserting that the temporary upload exists."""

        assert file_path.exists()
        assert file_kind == "jpg"
        return "Name: Maria Silva"

    def fake_extraction(text, settings):
        """Return a schema-valid extraction without a network call."""

        assert text == "Name: Maria Silva"
        return ExtractedDocumentData(name="Maria Silva", birth_date=date(1990, 5, 10))

    monkeypatch.setattr(processing, "extract_text", fake_ocr)
    monkeypatch.setattr(processing, "extract_structured_data", fake_extraction)


def test_document_lifecycle(client: TestClient, monkeypatch) -> None:
    """Create, list, retrieve, and delete one extracted document."""

    stub_pipeline_services(monkeypatch)
    response = client.post(
        "/documents",
        files={"file": ("identity.jpg", b"\xff\xd8\xffpayload", "image/jpeg")},
    )

    assert response.status_code == 201
    created = response.json()
    assert created["extracted_data"]["name"] == "Maria Silva"
    assert created["extracted_data"]["birth_date"] == "1990-05-10"

    listing = client.get("/documents?limit=5&offset=0")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["id"] == created["id"]

    detail = client.get(f"/documents/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "completed"

    deleted = client.delete(f"/documents/{created['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/documents/{created['id']}").status_code == 404


def test_rejects_unsupported_file_type(client: TestClient) -> None:
    """Reject unsupported extensions before attempting OCR or model calls."""

    response = client.post(
        "/documents", files={"file": ("notes.txt", b"plain text", "text/plain")}
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_rejects_mismatched_file_signature(client: TestClient) -> None:
    """Reject an image extension when its payload is not a valid image signature."""

    response = client.post(
        "/documents", files={"file": ("broken.png", b"not an image", "image/png")}
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "invalid_file_signature"


def test_health_check_reports_database(client: TestClient) -> None:
    """Confirm the health endpoint checks the configured database connection."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}