"""Expose document upload, retrieval, listing, and deletion endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.db.models import Document
from app.db.session import get_db_session
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services.processing import process_upload

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=201)
def create_document(
    file: Annotated[UploadFile, File(...)],
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Document:
    """Process one uploaded file and return its validated extracted fields."""

    try:
        return process_upload(file.file, file.filename, file.content_type, session, settings)
    finally:
        file.file.close()


@router.get("", response_model=DocumentListResponse)
def list_documents(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    """Return a bounded page of results without exposing OCR content."""

    statement = (
        select(Document)
        .options(selectinload(Document.extracted_data))
        .order_by(Document.created_at.desc(), Document.id.desc())
        .offset(offset)
        .limit(limit)
    )
    documents = session.scalars(statement).all()
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(document) for document in documents],
        limit=limit,
        offset=offset,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> Document:
    """Return one document or a safe not-found response."""

    document = session.scalar(
        select(Document)
        .options(selectinload(Document.extracted_data))
        .where(Document.id == document_id)
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


@router.delete("/{document_id}", status_code=204, response_class=Response)
def delete_document(
    document_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    """Delete document metadata and its associated extracted fields."""

    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    session.delete(document)
    session.commit()
    return Response(status_code=204)