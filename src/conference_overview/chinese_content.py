"""Typed, source-bound Chinese reading content for conference papers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from conference_overview.models import PaperRecord

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_RELEASE_GENERATION_PATTERN = re.compile(r"^generations/[0-9a-f]{64}$")
_PAPER_ROUTE_PATTERN = re.compile(r"^paper-[0-9a-f]{64}$")
_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_NUMERIC_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])[+-]?\d+(?:[.,]\d+)*(?:%|pp)?",
    re.IGNORECASE,
)


class ContentPublicationBlocked(ValueError):
    """Raised when Chinese content cannot be safely published."""


def _nonblank(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("public Chinese content must not be blank")
    return normalized


def _sha256_text(value: str) -> str:
    normalized = " ".join(value.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def paper_route_key(paper_id: str) -> str:
    """Return the producer-authoritative route key for an ordinary paper."""
    normalized = _nonblank(paper_id)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"paper-{digest}"


class PaperSummaryZh(BaseModel):
    """A Chinese summary grounded in an official abstract or PDF."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["paper-summary-zh-v1"]
    paper_id: str
    route_key: str
    venue: str
    year: int
    track: str
    source_title: str
    source_abstract_sha256: str | None
    source_pdf_sha256: str | None = None
    one_sentence: str
    summary_zh: str
    research_problem: str
    core_method: str
    main_findings: str
    scope_and_limitations: str
    content_method: Literal[
        "title-abstract-grounded-summary-v1",
        "official-pdf-grounded-summary-v1",
    ]

    @field_validator(
        "paper_id",
        "route_key",
        "venue",
        "track",
        "source_title",
        "one_sentence",
        "summary_zh",
        "research_problem",
        "core_method",
        "main_findings",
        "scope_and_limitations",
    )
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator("source_abstract_sha256", "source_pdf_sha256")
    @classmethod
    def validate_optional_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if _SHA256_PATTERN.fullmatch(normalized) is None:
            raise ValueError("source hash must be a lowercase SHA-256")
        return normalized

    @model_validator(mode="after")
    def validate_summary_contract(self) -> PaperSummaryZh:
        chinese_count = len(_CJK_PATTERN.findall(self.summary_zh))
        if not 150 <= chinese_count <= 250:
            raise ValueError("summary_zh must contain 150 to 250 Chinese characters")
        if self.route_key != paper_route_key(self.paper_id):
            raise ValueError("route_key must equal the full paper ID SHA-256")
        abstract_bound = self.source_abstract_sha256 is not None
        pdf_bound = self.source_pdf_sha256 is not None
        if abstract_bound == pdf_bound:
            raise ValueError("summary requires exactly one source binding")
        if (
            self.content_method == "title-abstract-grounded-summary-v1"
            and not abstract_bound
        ) or (
            self.content_method == "official-pdf-grounded-summary-v1" and not pdf_bound
        ):
            raise ValueError("content method must match its source binding")
        return self


class AwardQuickReadZh(BaseModel):
    """The three facts a reader should understand first."""

    model_config = ConfigDict(extra="forbid")

    research_problem: str
    core_method: str
    main_finding: str

    @field_validator("research_problem", "core_method", "main_finding")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _nonblank(value)


class AwardDeepReadZh(BaseModel):
    """A Chinese learning-oriented deep read grounded in an official PDF."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["award-deep-read-zh-v1"]
    paper_id: str
    source_pdf_sha256: str
    quick_read: AwardQuickReadZh
    abstract_zh: str
    background: tuple[str, ...] = Field(min_length=1)
    method_walkthrough: tuple[str, ...] = Field(min_length=1)
    why_it_matters: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)
    research_implications: tuple[str, ...] = Field(min_length=1)

    @field_validator("paper_id", "abstract_zh")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator("source_pdf_sha256")
    @classmethod
    def validate_pdf_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if _SHA256_PATTERN.fullmatch(normalized) is None:
            raise ValueError("source_pdf_sha256 must be a lowercase SHA-256")
        return normalized

    @field_validator(
        "background",
        "method_walkthrough",
        "why_it_matters",
        "limitations",
        "research_implications",
    )
    @classmethod
    def normalize_sections(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_nonblank(value) for value in values)


class ContentManifest(BaseModel):
    """Identity and hashes for one immutable Chinese content generation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["chinese-content-manifest-v1"]
    release_generation: str
    papers_sha256: str
    generated_at: datetime
    ordinary_count: int = Field(ge=0)
    award_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    artifact_sha256: dict[str, str]


class ContentPointer(BaseModel):
    """The selected immutable Chinese content generation."""

    model_config = ConfigDict(extra="forbid")

    generation: str
    release_generation: str
    papers_sha256: str
    artifact_sha256: dict[str, str]

    @field_validator("generation", "release_generation")
    @classmethod
    def validate_generation(cls, value: str) -> str:
        if _RELEASE_GENERATION_PATTERN.fullmatch(value) is None:
            raise ValueError("generation must name a SHA-256 generation directory")
        return value

    @field_validator("papers_sha256")
    @classmethod
    def validate_papers_sha256(cls, value: str) -> str:
        if _SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError("papers_sha256 must be a lowercase SHA-256")
        return value


class ChineseContentBundle(BaseModel):
    """Validated Chinese content ready for immutable serialization."""

    model_config = ConfigDict(extra="forbid")

    release_generation: str
    papers_sha256: str
    summaries: tuple[PaperSummaryZh, ...]
    award_deep_reads: tuple[AwardDeepReadZh, ...]
    ordinary_count: int
    award_count: int
    total_count: int


def _public_summary_text(summary: PaperSummaryZh) -> str:
    return (
        f"{summary.one_sentence} {summary.summary_zh} {summary.research_problem} "
        f"{summary.core_method} {summary.main_findings} "
        f"{summary.scope_and_limitations}"
    )


def _public_award_text(deep_read: AwardDeepReadZh) -> str:
    return " ".join(
        (
            deep_read.quick_read.research_problem,
            deep_read.quick_read.core_method,
            deep_read.quick_read.main_finding,
            deep_read.abstract_zh,
            *deep_read.background,
            *deep_read.method_walkthrough,
            *deep_read.why_it_matters,
            *deep_read.limitations,
            *deep_read.research_implications,
        )
    )


def _validate_numeric_tokens(public_text: str, source_text: str, paper_id: str) -> None:
    source_tokens = set(_NUMERIC_TOKEN_PATTERN.findall(source_text))
    unsupported = sorted(
        set(_NUMERIC_TOKEN_PATTERN.findall(public_text)).difference(source_tokens)
    )
    if unsupported:
        raise ContentPublicationBlocked(
            f"numeric token is absent from the bound source for {paper_id}: "
            + ", ".join(unsupported)
        )


def validate_summary_sources(summary: PaperSummaryZh, source_text: str) -> None:
    """Reject public numeric statements absent from the bound source."""
    try:
        reparsed = PaperSummaryZh.model_validate(summary.model_dump())
    except ValidationError as exc:
        raise ContentPublicationBlocked("invalid Chinese content") from exc
    _validate_numeric_tokens(_public_summary_text(reparsed), source_text, summary.paper_id)


def _require_unique_ids(values: Sequence[str], label: str) -> set[str]:
    identities = set(values)
    if len(identities) != len(values):
        raise ContentPublicationBlocked(f"duplicate {label} paper IDs")
    return identities


def validate_chinese_content_bundle(
    *,
    papers: Sequence[PaperRecord],
    award_ids: set[str],
    summaries: Sequence[PaperSummaryZh],
    award_deep_reads: Sequence[AwardDeepReadZh],
    release_generation: str,
    papers_sha256: str,
    award_pdf_sha256: Mapping[str, str],
    award_source_text: Mapping[str, str],
    ordinary_pdf_sha256: Mapping[str, str] | None = None,
    ordinary_pdf_source_text: Mapping[str, str] | None = None,
) -> ChineseContentBundle:
    """Validate exact paper coverage and all source bindings."""
    if _RELEASE_GENERATION_PATTERN.fullmatch(release_generation) is None:
        raise ContentPublicationBlocked("invalid release generation")
    if _SHA256_PATTERN.fullmatch(papers_sha256) is None:
        raise ContentPublicationBlocked("invalid papers SHA-256")
    ordinary_pdf_sha256 = ordinary_pdf_sha256 or {}
    ordinary_pdf_source_text = ordinary_pdf_source_text or {}
    try:
        parsed_summaries = tuple(
            PaperSummaryZh.model_validate(summary.model_dump()) for summary in summaries
        )
        parsed_awards = tuple(
            AwardDeepReadZh.model_validate(deep_read.model_dump())
            for deep_read in award_deep_reads
        )
    except ValidationError as exc:
        raise ContentPublicationBlocked("invalid Chinese content") from exc

    paper_by_id = {paper.paper_id: paper for paper in papers}
    if len(paper_by_id) != len(papers) or not award_ids.issubset(paper_by_id):
        raise ContentPublicationBlocked("paper ID coverage is invalid")
    summary_ids = _require_unique_ids(
        [summary.paper_id for summary in parsed_summaries], "ordinary summary"
    )
    deep_read_ids = _require_unique_ids(
        [deep_read.paper_id for deep_read in parsed_awards], "award deep-read"
    )
    expected_all = set(paper_by_id)
    expected_summaries = expected_all.difference(award_ids)
    if (
        summary_ids != expected_summaries
        or deep_read_ids != award_ids
        or summary_ids.intersection(deep_read_ids)
        or summary_ids.union(deep_read_ids) != expected_all
    ):
        raise ContentPublicationBlocked("paper ID coverage is incomplete or contradictory")

    route_keys = [summary.route_key for summary in parsed_summaries]
    if len(route_keys) != len(set(route_keys)) or any(
        _PAPER_ROUTE_PATTERN.fullmatch(route_key) is None for route_key in route_keys
    ):
        raise ContentPublicationBlocked("ordinary paper route keys are invalid")

    for summary in parsed_summaries:
        source = paper_by_id[summary.paper_id]
        if (
            summary.source_title != source.title
            or summary.venue != source.venue
            or summary.year != source.year
            or summary.track != source.track
        ):
            raise ContentPublicationBlocked(
                f"summary scope differs from paper record: {summary.paper_id}"
            )
        if summary.content_method == "title-abstract-grounded-summary-v1":
            if source.abstract is None:
                raise ContentPublicationBlocked(
                    f"abstract-grounded summary has no abstract: {summary.paper_id}"
                )
            if summary.source_abstract_sha256 != _sha256_text(source.abstract):
                raise ContentPublicationBlocked(
                    f"abstract SHA-256 mismatch: {summary.paper_id}"
                )
            source_text = f"{source.title} {source.abstract}"
        else:
            if summary.source_pdf_sha256 != ordinary_pdf_sha256.get(summary.paper_id):
                raise ContentPublicationBlocked(
                    f"PDF SHA-256 mismatch: {summary.paper_id}"
                )
            source_text = ordinary_pdf_source_text.get(summary.paper_id, "")
            if not source_text.strip():
                raise ContentPublicationBlocked(
                    f"PDF-grounded summary has no source text: {summary.paper_id}"
                )
        validate_summary_sources(summary, source_text)

    for deep_read in parsed_awards:
        if deep_read.source_pdf_sha256 != award_pdf_sha256.get(deep_read.paper_id):
            raise ContentPublicationBlocked(
                f"award PDF SHA-256 mismatch: {deep_read.paper_id}"
            )
        source_text = award_source_text.get(deep_read.paper_id, "")
        if not source_text.strip():
            raise ContentPublicationBlocked(
                f"award deep read has no source text: {deep_read.paper_id}"
            )
        _validate_numeric_tokens(
            _public_award_text(deep_read), source_text, deep_read.paper_id
        )

    ordered_summaries = tuple(sorted(parsed_summaries, key=lambda item: item.paper_id))
    ordered_awards = tuple(sorted(parsed_awards, key=lambda item: item.paper_id))
    return ChineseContentBundle(
        release_generation=release_generation,
        papers_sha256=papers_sha256,
        summaries=ordered_summaries,
        award_deep_reads=ordered_awards,
        ordinary_count=len(ordered_summaries),
        award_count=len(ordered_awards),
        total_count=len(papers),
    )
