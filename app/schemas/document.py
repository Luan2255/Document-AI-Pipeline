"""Define validated extraction fields and document API response contracts."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class ExtractedDocumentData(BaseModel):
    """Represent structured values returned by the configured language model."""

    model_config = ConfigDict(extra="forbid")

    document_type: str | None = None
    name: str | None = None
    cpf: str | None = None
    rg: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def normalize_empty_values(cls, value: object) -> object:
        """Convert blank model responses to null and trim textual values."""

        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class ExtractedDocumentDataResponse(ExtractedDocumentData):
    """Expose the validated fields without internal database identifiers."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class DocumentResponse(BaseModel):
    """Serialize one processed document and its extracted fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: Literal["completed"]
    created_at: datetime
    extracted_data: ExtractedDocumentDataResponse


class DocumentListResponse(BaseModel):
    """Wrap one page of documents with its pagination metadata."""

    items: list[DocumentResponse]
    limit: int
    offset: int