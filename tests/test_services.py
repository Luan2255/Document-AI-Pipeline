"""Verify file validation, OCR, and model configuration at service boundaries."""

import json
from io import BytesIO

import pymupdf
import pytest
from PIL import Image
from pydantic import SecretStr

from app.core.config import Settings
from app.schemas.document import ExtractedDocumentData
from app.services.errors import DocumentProcessingError
from app.services.file_validation import validate_upload
from app.services.llm import extract_structured_data
from app.services.ocr import extract_text


def test_validates_image_signature_and_size() -> None:
    """Accept a correctly signed image and reject data above the size limit."""

    stream = BytesIO(b"\xff\xd8\xffimage-data")
    contents, mime_type, extension = validate_upload(
        stream, "photo.jpg", "image/jpeg", 32
    )
    assert contents.startswith(b"\xff\xd8\xff")
    assert mime_type == "image/jpeg"
    assert extension == ".jpg"

    with pytest.raises(DocumentProcessingError) as error:
        validate_upload(stream, "photo.jpg", "image/jpeg", 4)
    assert error.value.error_code == "file_too_large"


def test_normalizes_empty_values_and_iso_date() -> None:
    """Normalize blank model fields and parse ISO-formatted dates."""

    result = ExtractedDocumentData.model_validate(
        {"name": "  Maria Silva ", "email": "", "birth_date": "1990-05-10"}
    )

    assert result.name == "Maria Silva"
    assert result.email is None
    assert result.birth_date.isoformat() == "1990-05-10"


def test_pdf_text_extraction_without_ocr(tmp_path) -> None:
    """Read native PDF text without requiring an installed OCR binary."""

    pdf_path = tmp_path / "native.pdf"
    pdf_document = pymupdf.open()
    page = pdf_document.new_page()
    page.insert_text((72, 72), "This native PDF contains searchable text.")
    pdf_document.save(pdf_path)
    pdf_document.close()

    text = extract_text(pdf_path, "pdf", "por+eng", max_pdf_pages=2)

    assert "searchable text" in text


def test_llm_requires_api_key() -> None:
    """Fail clearly before network access when no model credential is configured."""

    settings = Settings(_env_file=None, llm_api_key=None)

    with pytest.raises(DocumentProcessingError) as error:
        extract_structured_data("Recognized text", settings)

    assert error.value.status_code == 503
    assert error.value.error_code == "llm_not_configured"


def test_llm_parses_openai_compatible_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Send a structured request and validate the provider's JSON response."""

    class FakeResponse:
        """Provide the minimal successful HTTP response used by the client."""

        def raise_for_status(self) -> None:
            """Match the HTTPX response interface for successful requests."""

        def json(self) -> dict[str, object]:
            """Return one chat-completions response with structured field values."""

            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"name": "Maria Silva", "birth_date": "1990-05-10"}
                            )
                        }
                    }
                ]
            }

    class FakeClient:
        """Replace network access while checking endpoint and authorization."""

        def __init__(self, timeout: float) -> None:
            """Accept the configured timeout used by the production client."""

            assert timeout == 45

        def __enter__(self) -> "FakeClient":
            """Return the fake client as an HTTPX context manager."""

            return self

        def __exit__(self, *args: object) -> None:
            """Close the fake client context without external resources."""

        def post(self, url: str, headers: dict[str, str], json: dict[str, object]) -> FakeResponse:
            """Check the provider request shape and return structured content."""

            assert url == "https://example.test/v1/chat/completions"
            assert headers["Authorization"] == "Bearer test-key"
            assert json["response_format"] == {"type": "json_object"}
            return FakeResponse()

    monkeypatch.setattr("app.services.llm.httpx.Client", FakeClient)
    settings = Settings(
        _env_file=None,
        llm_api_key=SecretStr("test-key"),
        llm_base_url="https://example.test/v1",
    )

    result = extract_structured_data("Name: Maria Silva", settings)

    assert result.name == "Maria Silva"
    assert result.birth_date.isoformat() == "1990-05-10"