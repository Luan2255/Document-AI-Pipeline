"""Coordinate temporary upload handling, OCR, extraction, and persistence."""

import logging
import tempfile
import time
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Document, ExtractedData, ProcessingLog
from app.schemas.document import ExtractedDocumentData
from app.services.errors import DocumentProcessingError
from app.services.file_validation import validate_upload
from app.services.llm import extract_structured_data
from app.services.ocr import extract_text

logger = logging.getLogger(__name__)


def process_upload(
    file_stream: BinaryIO,
    filename: str | None,
    content_type: str | None,
    session: Session,
    settings: Settings,
) -> Document:
    """Run the complete pipeline and persist only successful structured results."""

    started_at = time.monotonic()
    try:
        contents, mime_type, file_extension = validate_upload(
            file_stream, filename, content_type, settings.max_upload_size_bytes
        )
        with tempfile.NamedTemporaryFile(suffix=file_extension) as temporary_file:
            temporary_file.write(contents)
            temporary_file.flush()
            text = extract_text(
                Path(temporary_file.name), file_extension.lstrip("."),
                settings.ocr_languages, settings.max_pdf_pages,
            )
            if not text.strip():
                raise DocumentProcessingError(
                    "No readable text was found in the document.", 422, "empty_ocr_result"
                )
            extracted_data = extract_structured_data(text, settings)

        document = Document(
            status="completed",
            mime_type=mime_type,
            file_size_bytes=len(contents),
            extracted_data=ExtractedData(**extracted_data.model_dump()),
        )
        session.add(document)
        session.flush()
        session.add(
            ProcessingLog(
                document_id=document.id,
                status="completed",
                duration_ms=_duration_ms(started_at),
            )
        )
        session.commit()
        session.refresh(document)
        logger.info(
            "document_processing_completed document_id=%s duration_ms=%s",
            document.id,
            _duration_ms(started_at),
        )
        return document
    except DocumentProcessingError as error:
        _record_failure(session, error.error_code, started_at)
        logger.warning(
            "document_processing_failed error_code=%s duration_ms=%s",
            error.error_code,
            _duration_ms(started_at),
        )
        raise
    except Exception as error:
        _record_failure(session, "processing_failed", started_at)
        logger.error(
            "document_processing_failed error_code=processing_failed duration_ms=%s",
            _duration_ms(started_at),
        )
        raise DocumentProcessingError(
            "The document could not be processed.", 500, "processing_failed"
        ) from error


def _record_failure(session: Session, error_code: str, started_at: float) -> None:
    """Persist only a failure code and duration, never the exception or OCR text."""

    try:
        session.rollback()
        session.add(
            ProcessingLog(
                document_id=None,
                status="failed",
                duration_ms=_duration_ms(started_at),
                error_code=error_code,
            )
        )
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        logger.warning("processing_failure_log_write_failed error_code=%s", error_code)


def _duration_ms(started_at: float) -> int:
    """Return elapsed monotonic time in integer milliseconds."""

    return int((time.monotonic() - started_at) * 1000)