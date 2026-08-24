from conference_overview.models import (
    EvidenceClaim,
    EvidenceType,
    PaperRecord,
    RecordStatus,
    SourceRef,
)


def test_paper_requires_official_source() -> None:
    paper = PaperRecord(
        paper_id="acl:2026.acl-long.1",
        title="Example",
        normalized_title="example",
        authors=["A. Author"],
        venue="ACL",
        year=2026,
        track="long",
        landing_url="https://aclanthology.org/2026.acl-long.1/",
        source=SourceRef(
            name="ACL Anthology",
            url="https://aclanthology.org/volumes/2026.acl-long/",
        ),
        status=RecordStatus.COMPLETE,
    )

    assert paper.paper_id == "acl:2026.acl-long.1"
    assert str(paper.source.url) == "https://aclanthology.org/volumes/2026.acl-long/"


def test_paper_optional_collections_are_not_shared_between_records() -> None:
    first = PaperRecord(
        paper_id="acl:2026.acl-long.1",
        title="First",
        normalized_title="first",
        authors=["A. Author"],
        venue="ACL",
        year=2026,
        track="long",
        landing_url="https://aclanthology.org/2026.acl-long.1/",
        source=SourceRef(
            name="ACL Anthology",
            url="https://aclanthology.org/volumes/2026.acl-long/",
        ),
        status=RecordStatus.COMPLETE,
    )
    second = PaperRecord(
        paper_id="acl:2026.acl-long.2",
        title="Second",
        normalized_title="second",
        authors=["B. Author"],
        venue="ACL",
        year=2026,
        track="long",
        landing_url="https://aclanthology.org/2026.acl-long.2/",
        source=SourceRef(
            name="ACL Anthology",
            url="https://aclanthology.org/volumes/2026.acl-long/",
        ),
        status=RecordStatus.COMPLETE,
    )

    first.keywords.append("evaluation")
    first.native_metadata["session"] = "oral"

    assert second.keywords == []
    assert second.native_metadata == {}


def test_evidence_claim_preserves_evidence_boundary() -> None:
    claim = EvidenceClaim(
        claim="The volume lists this paper as accepted.",
        evidence_type=EvidenceType.OFFICIAL_METADATA,
        source_urls=["https://aclanthology.org/volumes/2026.acl-long/"],
        locator="entry 1",
    )

    assert claim.evidence_type is EvidenceType.OFFICIAL_METADATA
    assert claim.locator == "entry 1"
