"""Create the FastAPI application and initialize its database schema."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes.documents import router as documents_router
from app.core.logging import configure_logging
from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.session import engine, get_db_session
from app.services.errors import DocumentProcessingError

configure_logging()


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create registered tables before serving requests."""

    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Document AI Pipeline",
    description="OCR and structured extraction for PDF and image documents.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(documents_router)


@app.exception_handler(DocumentProcessingError)
async def document_processing_error_handler(
    request: Any, error: DocumentProcessingError
) -> JSONResponse:
    """Return stable error codes without exposing internals or document data."""

    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.error_code, "message": str(error)}},
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Any, error: StarletteHTTPException) -> JSONResponse:
    """Keep standard HTTP errors in the API's predictable error envelope."""

    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": f"http_{error.status_code}", "message": error.detail}},
        headers=error.headers,
    )


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Report API readiness only when the database accepts a simple query."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Database unavailable.") from error
    return {"status": "ok", "database": "connected"}