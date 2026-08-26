"""Award provenance and paper deep-read evidence contracts."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from conference_overview.models import EvidenceClaim, EvidenceType
from conference_overview.registry import canonicalize_official_host


class AwardStatus(str, Enum):
    """The only publication-safe states for a conference award."""

    VERIFIED = "verified"
    NOT_ANNOUNCED = "not_announced"
    NOT_VERIFIED = "not_verified"


class AwardRecord(BaseModel):
    """A candidate award record whose status is derived from its evidence URL."""

    paper_id: str = Field(min_length=1)
    award_type: str = Field(min_length=1)
    status: AwardStatus = AwardStatus.NOT_ANNOUNCED
    evidence_url: HttpUrl | None = None
    official_citation: str | None = None

    @field_validator("paper_id", "award_type")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _normalized_required_text(value)

    @model_validator(mode="after")
    def verified_award_requires_evidence(self) -> AwardRecord:
        if self.status is AwardStatus.VERIFIED and self.evidence_url is None:
            raise ValueError("verified award requires official evidence")
        return self


class AwardAnnouncement(BaseModel):
    """Explicit official metadata about an unavailable award announcement."""

    status: AwardStatus = AwardStatus.NOT_VERIFIED
    evidence_url: HttpUrl | None = None
    claim: EvidenceClaim | None = None

    @model_validator(mode="after")
    def validate_announcement_state(self) -> AwardAnnouncement:
        if self.status is AwardStatus.VERIFIED:
            raise ValueError("verified status belongs to an AwardRecord")
        if self.status is AwardStatus.NOT_ANNOUNCED:
            if self.evidence_url is None or self.claim is None:
                raise ValueError("not_announced requires explicit official metadata")
            if self.claim.evidence_type is not EvidenceType.OFFICIAL_METADATA:
                raise ValueError("not_announced requires official_metadata evidence")
            if str(self.evidence_url) not in {
                str(url) for url in self.claim.source_urls
            }:
                raise ValueError(
                    "announcement evidence URL must be retained in its claim"
                )
        return self


class ResultClaim(EvidenceClaim):
    """A paper-reported numerical result with its experimental context."""

    evidence_type: Literal[EvidenceType.PAPER_REPORTED]
    metric: str
    value: Decimal
    evaluation_setting: str

    @field_validator("metric", "evaluation_setting")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _normalized_required_text(value)

    @field_validator("value", mode="before")
    @classmethod
    def normalize_finite_value(cls, value: object) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, (Decimal, float, int, str)):
            raise ValueError(  # noqa: TRY004 - Pydantic converts this to ValidationError.
                "numeric result value must be a finite number"
            )
        try:
            normalized = Decimal(
                value.strip() if isinstance(value, str) else str(value)
            )
        except (InvalidOperation, ValueError):
            raise ValueError("numeric result value must be a finite number") from None
        if not normalized.is_finite():
            raise ValueError("numeric result value must be a finite number")
        return normalized


class NoNumericResult(BaseModel):
    """Explicit state for a position paper whose main contribution is normative."""

    paper_type: Literal["position_paper"]
    reason: EvidenceClaim

    @model_validator(mode="after")
    def validate_reason(self) -> NoNumericResult:
        if self.reason.evidence_type is not EvidenceType.PAPER_REPORTED:
            raise ValueError("no-numeric-result reason must be paper_reported")
        if not self.reason.source_urls or not _has_text(self.reason.locator):
            raise ValueError(
                "no-numeric-result reason requires a source URL and paper locator"
            )
        return self


class MethodNode(BaseModel):
    """A diagram component that can be traced to a disclosed paper section."""

    identifier: str
    label: str
    paper_section: str | None = None

    @field_validator("identifier", "label", "paper_section")
    @classmethod
    def normalize_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalized_required_text(value)


class MethodEdge(BaseModel):
    """A directed disclosed data flow between two method components."""

    source: str
    target: str
    data_flow_rationale: str | None = None

    @field_validator("source", "target", "data_flow_rationale")
    @classmethod
    def normalize_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalized_required_text(value)


class MethodDiagram(BaseModel):
    """An original explanatory diagram derived only from disclosed architecture."""

    nodes: list[MethodNode] = Field(min_length=1)
    edges: list[MethodEdge] = Field(default_factory=list)


class DeepRead(BaseModel):
    """Evidence-bearing, publication-ready details for an award paper."""

    paper_id: str = Field(min_length=1)
    research_problem: EvidenceClaim
    contribution: EvidenceClaim
    method_summary: EvidenceClaim
    result_claims: list[ResultClaim] = Field(default_factory=list)
    no_numeric_result: NoNumericResult | None = None
    why_it_matters: list[EvidenceClaim] = Field(min_length=1)
    limitations: list[EvidenceClaim] = Field(min_length=1)
    data_training_setup: list[EvidenceClaim] = Field(min_length=1)
    prior_work_differences: list[EvidenceClaim] = Field(min_length=1)
    reproducibility_assessment: list[EvidenceClaim] = Field(min_length=1)
    transferable_implications: list[EvidenceClaim] = Field(min_length=1)
    method_diagram: MethodDiagram | None = None

    @field_validator("paper_id")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _normalized_required_text(value)

    @model_validator(mode="after")
    def require_result_or_position_state(self) -> DeepRead:
        if bool(self.result_claims) == (self.no_numeric_result is not None):
            raise ValueError(
                "deep read requires numeric results or one position-paper no-numeric-result state"
            )
        return self


_WHY_IT_MATTERS_EVIDENCE_TYPES = frozenset(
    {
        EvidenceType.PAPER_REPORTED,
        EvidenceType.CROSS_PAPER_SYNTHESIS,
        EvidenceType.INFERENCE,
    }
)
_TRANSFERABLE_EVIDENCE_TYPES = frozenset(
    {EvidenceType.CROSS_PAPER_SYNTHESIS, EvidenceType.INFERENCE}
)


def _has_text(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _normalized_required_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("required text must not be blank")
    return normalized


def canonical_award_identity(paper_id: str, award_type: str) -> dict[str, str]:
    """Return Python's authoritative normalized award identity."""
    return {
        "paper_id": paper_id,
        "award_type": " ".join(
            unicodedata.normalize("NFKC", award_type).casefold().split()
        ),
    }


def award_route_key(identity: dict[str, str]) -> str:
    """Hash a canonical identity into one path-safe route segment."""
    canonical = json.dumps(
        [identity["paper_id"], identity["award_type"]],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    return f"award-{hashlib.sha256(canonical).hexdigest()}"


def _is_official_host(url: HttpUrl, allowed_hosts: set[str]) -> bool:
    """Return whether *url* belongs to a configured host or its true subdomain."""
    hostname = urlparse(str(url)).hostname
    if hostname is None:
        return False
    try:
        normalized_host = canonicalize_official_host(hostname)
        normalized_allowed_hosts = {
            canonicalize_official_host(host) for host in allowed_hosts
        }
    except ValueError:
        return False
    return any(
        normalized_host == allowed_host or normalized_host.endswith(f".{allowed_host}")
        for allowed_host in normalized_allowed_hosts
    )


def validate_award(record: AwardRecord, *, allowed_hosts: set[str]) -> AwardRecord:
    """Derive a safe award status using only configured official source hosts."""
    if record.status is not AwardStatus.VERIFIED:
        return record
    if record.evidence_url is None:
        return record.model_copy(update={"status": AwardStatus.NOT_ANNOUNCED})
    if _is_official_host(record.evidence_url, allowed_hosts):
        return record
    return record.model_copy(update={"status": AwardStatus.NOT_VERIFIED})


def _validate_result_claim(claim: ResultClaim) -> None:
    if not _has_text(claim.metric):
        raise ValueError("numeric result claim requires a metric")
    if isinstance(claim.value, str) and not _has_text(claim.value):
        raise ValueError("numeric result claim requires a value")
    if not _has_text(claim.evaluation_setting):
        raise ValueError("numeric result claim requires an evaluation setting")
    if not claim.source_urls:
        raise ValueError("numeric result claim requires a source URL")
    if not _has_text(claim.locator):
        raise ValueError("numeric result claim requires a paper locator")


def _validate_method_diagram(diagram: MethodDiagram) -> None:
    node_ids: set[str] = set()
    for node in diagram.nodes:
        if not _has_text(node.identifier):
            raise ValueError("method diagram node requires an identifier")
        if not _has_text(node.label):
            raise ValueError("method diagram node requires a label")
        if not _has_text(node.paper_section):
            raise ValueError("method diagram node requires a paper section")
        node_id = node.identifier.strip()
        if node_id in node_ids:
            raise ValueError("method diagram node identifiers must be unique")
        node_ids.add(node_id)

    edge_pairs: set[tuple[str, str]] = set()
    for edge in diagram.edges:
        source = edge.source.strip()
        target = edge.target.strip()
        if source not in node_ids or target not in node_ids:
            raise ValueError("method diagram edge must connect disclosed nodes")
        if not _has_text(edge.data_flow_rationale):
            raise ValueError(
                "method diagram edge requires a disclosed data-flow rationale"
            )
        edge_pair = (source, target)
        if edge_pair in edge_pairs:
            raise ValueError("method diagram cannot contain duplicate directed edges")
        edge_pairs.add(edge_pair)


def validate_deep_read(deep_read: DeepRead) -> DeepRead:
    """Reject deep-read content that cannot be traced back to paper evidence."""
    for claim in deep_read.result_claims:
        _validate_result_claim(claim)

    for claim in deep_read.why_it_matters:
        if claim.evidence_type not in _WHY_IT_MATTERS_EVIDENCE_TYPES:
            raise ValueError(
                "why_it_matters evidence type must be paper_reported, "
                "cross_paper_synthesis, or inference"
            )

    for claim in deep_read.transferable_implications:
        if claim.evidence_type not in _TRANSFERABLE_EVIDENCE_TYPES:
            raise ValueError(
                "transferable_implications evidence type must be "
                "cross_paper_synthesis or inference"
            )

    evidence_sections = (
        deep_read.research_problem,
        deep_read.contribution,
        deep_read.method_summary,
        *deep_read.why_it_matters,
        *deep_read.limitations,
        *deep_read.data_training_setup,
        *deep_read.prior_work_differences,
        *deep_read.reproducibility_assessment,
        *deep_read.transferable_implications,
    )
    for claim in evidence_sections:
        if not claim.source_urls:
            raise ValueError("deep-read evidence section requires a source URL")
        if claim.evidence_type is EvidenceType.PAPER_REPORTED and not _has_text(
            claim.locator
        ):
            raise ValueError(
                "paper-reported deep-read section requires a paper locator"
            )

    if deep_read.method_diagram is not None:
        _validate_method_diagram(deep_read.method_diagram)

    return deep_read
