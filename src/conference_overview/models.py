from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class RecordStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    EXCLUDED = "excluded"
    UNRESOLVED = "unresolved"


class EvidenceType(str, Enum):
    OFFICIAL_METADATA = "official_metadata"
    PAPER_REPORTED = "paper_reported"
    CROSS_PAPER_SYNTHESIS = "cross_paper_synthesis"
    INFERENCE = "inference"


class SourceRef(BaseModel):
    name: str
    url: HttpUrl
    retrieved_at: datetime | None = None
    sha256: str | None = None


class EvidenceClaim(BaseModel):
    claim: str
    evidence_type: EvidenceType
    source_urls: list[HttpUrl]
    locator: str | None = None


class PaperRecord(BaseModel):
    paper_id: str
    title: str
    normalized_title: str
    authors: list[str]
    venue: str
    year: int
    track: str
    landing_url: HttpUrl
    source: SourceRef
    status: RecordStatus
    abstract: str | None = None
    keywords: list[str] = Field(default_factory=list)
    subject_areas: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    native_metadata: dict[str, str | list[str]] = Field(default_factory=dict)
    doi: str | None = None
    pdf_url: HttpUrl | None = None
    code_url: HttpUrl | None = None


class VenueRequest(BaseModel):
    venue: str
    year: int
    track: str | None = None
    source_key: str | None = None
    bibtex_url: HttpUrl | None = None
    volume_url: HttpUrl | None = None
