"""Extract searchable PDF text and recognize text in image-based documents."""

from io import BytesIO
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image, UnidentifiedImageError
from pytesseract import TesseractNotFoundError, TesseractError

from app.services.errors import DocumentProcessingError


def extract_text(file_path: Path, file_kind: str, languages: str, max_pdf_pages: int) -> str:
    """Extract PDF text natively when possible and use Tesseract otherwise."""

    try:
        if file_kind == "pdf":
            return _extract_pdf_text(file_path, languages, max_pdf_pages)
        return _extract_image_text(file_path, languages)
    except DocumentProcessingError:
        raise
    except TesseractNotFoundError as error:
        raise DocumentProcessingError(
            "The OCR engine is unavailable.", 503, "ocr_unavailable"
        ) from error
    except (TesseractError, pymupdf.FileDataError, UnidentifiedImageError, OSError) as error:
        raise DocumentProcessingError(
            "The document could not be read by the OCR engine.", 422, "ocr_failed"
        ) from error


def _extract_image_text(file_path: Path, languages: str) -> str:
    """Run image OCR after verifying that Pillow can decode the upload."""

    with Image.open(file_path) as image:
        image.verify()
    with Image.open(file_path) as image:
        return pytesseract.image_to_string(image, lang=languages).strip()


def _extract_pdf_text(file_path: Path, languages: str, max_pdf_pages: int) -> str:
    """Extract native page text and OCR pages without useful embedded text."""

    page_texts: list[str] = []
    with pymupdf.open(file_path) as pdf_document:
        if pdf_document.is_encrypted:
            raise DocumentProcessingError("Encrypted PDFs are not supported.", 422, "encrypted_pdf")
        if pdf_document.page_count > max_pdf_pages:
            raise DocumentProcessingError("The PDF exceeds the page limit.", 413, "too_many_pages")

        for page in pdf_document:
            text = page.get_text("text").strip()
            if len(text) < 20:
                image_bytes = page.get_pixmap(dpi=200).tobytes("png")
                with Image.open(BytesIO(image_bytes)) as image:
                    text = pytesseract.image_to_string(image, lang=languages).strip()
            if text:
                page_texts.append(text)

    return "\n".join(page_texts)