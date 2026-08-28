from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


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


class AdvanceCategory(str, Enum):
    TEXT_LLMS = "text_llms"
    MULTIMODAL_MODELS = "multimodal_models"
    REASONING_AGENTS = "reasoning_agents"
    DATA_TRAINING = "data_training"
    EVALUATION_TRUST = "evaluation_trust"


class ThemeDisclosureStatus(str, Enum):
    WITHHELD = "withheld"
    EXPERIMENTAL = "experimental"


class AnalysisAvailability(BaseModel):
    papers: bool
    distribution: bool
    trends: bool
    advances: bool
    awards: bool


class PublicationContext(BaseModel):
    status: Literal["preliminary_official_program", "final_proceedings"]
    final_source_status: Literal["not_published", "available"]
    final_source_url: HttpUrl
    notice: str = Field(min_length=1)
    analysis_availability: AnalysisAvailability

    @field_validator("notice")
    @classmethod
    def normalize_notice(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("publication notice must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_source_state(self) -> "PublicationContext":
        expected = {
            "preliminary_official_program": "not_published",
            "final_proceedings": "available",
        }[self.status]
        if self.final_source_status != expected:
            raise ValueError("publication status contradicts final source status")
        return self


class SourceRef(BaseModel):
    name: str
    url: HttpUrl
    retrieved_at: datetime | None = None
    sha256: str | None = None


class EvidenceClaim(BaseModel):
    claim: str
    evidence_type: EvidenceType
    source_urls: list[HttpUrl] = Field(min_length=1)
    locator: str | None = None

    @field_validator("claim")
    @classmethod
    def normalize_claim(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("claim must not be blank")
        return normalized

    @field_validator("locator")
    @classmethod
    def normalize_locator(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("locator must not be blank")
        return normalized


class AdvanceRecord(BaseModel):
    advance_id: str
    title: str
    category: AdvanceCategory
    supporting_paper_ids: tuple[str, ...] = Field(min_length=1)
    claims: tuple[EvidenceClaim, ...] = Field(min_length=1)
    research_questions: tuple[str, ...] = ()
    core_problem: EvidenceClaim | None = None
    technical_change: EvidenceClaim | None = None
    evidence_boundary: EvidenceClaim | None = None
    implications: tuple[EvidenceClaim, ...] = ()

    @field_validator("advance_id", "title")
    @classmethod
    def normalize_advance_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("advance identifier and title must not be blank")
        return normalized

    @field_validator("supporting_paper_ids")
    @classmethod
    def normalize_supporting_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized) or len(set(normalized)) != len(
            normalized
        ):
            raise ValueError("supporting paper IDs must be nonblank and unique")
        return normalized


class ThemeDisclosure(BaseModel):
    theme: str
    status: ThemeDisclosureStatus
    reason: EvidenceClaim

    @field_validator("theme")
    @classmethod
    def normalize_theme(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("theme must not be blank")
        return normalized


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
    default_track: str | None = None
    is_default_track: bool = True
    adapter: str | None = None
    source_key: str | None = None
    source_urls: dict[str, HttpUrl] = Field(default_factory=dict)
    final_source_url: HttpUrl | None = None
    publication_status: str | None = None
    bibtex_url: HttpUrl | None = None
    volume_url: HttpUrl | None = None
    official_award_hosts: tuple[str, ...] = Field(default_factory=tuple)
