"""Validate upload metadata and file signatures before OCR processing."""

from pathlib import Path
from typing import BinaryIO

from app.services.errors import DocumentProcessingError

SUPPORTED_FILES = {
    ".jpg": ("image/jpeg", "jpeg"),
    ".jpeg": ("image/jpeg", "jpeg"),
    ".png": ("image/png", "png"),
    ".pdf": ("application/pdf", "pdf"),
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def validate_upload(
    file_stream: BinaryIO,
    filename: str | None,
    content_type: str | None,
    max_size_bytes: int,
) -> tuple[bytes, str, str]:
    """Read a bounded upload and verify its extension, MIME type, and signature."""

    extension = Path(filename or "").suffix.lower()
    file_metadata = SUPPORTED_FILES.get(extension)
    if file_metadata is None:
        raise DocumentProcessingError(
            "Supported file types are JPG, PNG, and PDF.", 415, "unsupported_file_type"
        )

    expected_mime, file_kind = file_metadata
    declared_mime = (content_type or "application/octet-stream").split(";")[0].lower()
    if declared_mime not in (expected_mime, "application/octet-stream"):
        raise DocumentProcessingError(
            "The declared content type does not match the file extension.",
            415,
            "content_type_mismatch",
        )

    file_stream.seek(0)
    contents = file_stream.read(max_size_bytes + 1)
    file_stream.seek(0)
    if len(contents) > max_size_bytes:
        raise DocumentProcessingError("The file exceeds the upload size limit.", 413, "file_too_large")
    if not contents:
        raise DocumentProcessingError("The uploaded file is empty.", 400, "empty_file")

    if file_kind == "pdf":
        signature_is_valid = contents.startswith(b"%PDF-")
    elif file_kind == "png":
        signature_is_valid = contents.startswith(PNG_SIGNATURE)
    else:
        signature_is_valid = contents.startswith(b"\xff\xd8\xff")

    if not signature_is_valid:
        raise DocumentProcessingError(
            "The file content does not match its declared format.", 415, "invalid_file_signature"
        )

    return contents, expected_mime, extension