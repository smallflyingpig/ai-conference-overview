from pathlib import Path

import pytest
import yaml

from conference_overview.awards import (
    AwardRecord,
    AwardStatus,
    DeepRead,
    MethodDiagram,
    MethodEdge,
    MethodNode,
    ResultClaim,
    validate_award,
    validate_deep_read,
)
from conference_overview.models import EvidenceClaim, EvidenceType


def award_record(*, evidence_url: str | None) -> AwardRecord:
    return AwardRecord(
        paper_id="acl:2026.acl-long.1",
        award_type="Best Paper",
        status=AwardStatus.VERIFIED,
        evidence_url=evidence_url,
    )


def result_claim(*, value: str = "52.0", locator: str | None = "Table 2") -> ResultClaim:
    return ResultClaim(
        claim="The method reaches the reported score.",
        evidence_type=EvidenceType.PAPER_REPORTED,
        source_urls=["https://aclanthology.org/2026.acl-long.1.pdf"],
        metric="Accuracy",
        value=value,
        evaluation_setting="ACL 2026 synthetic evaluation",
        locator=locator,
    )


def method_diagram(*, node: MethodNode | None = None) -> MethodDiagram:
    return MethodDiagram(
        nodes=[node or MethodNode(identifier="planner", label="Planner", paper_section="3.1")],
        edges=[
            MethodEdge(
                source="planner",
                target="planner",
                data_flow_rationale="The paper discloses an iterative planner state update.",
            )
        ],
    )


def deep_read_with_claim(*, value: str, locator: str | None) -> DeepRead:
    return DeepRead(
        paper_id="acl:2026.acl-long.1",
        result_claims=[result_claim(value=value, locator=locator)],
        why_it_matters=[
            EvidenceClaim(
                claim="The paper reports this result under the stated setting.",
                evidence_type=EvidenceType.PAPER_REPORTED,
                source_urls=["https://aclanthology.org/2026.acl-long.1.pdf"],
                locator="Section 5",
            )
        ],
    )


def deep_read_with_diagram(diagram: MethodDiagram) -> DeepRead:
    return DeepRead(
        paper_id="acl:2026.acl-long.1",
        result_claims=[result_claim()],
        why_it_matters=[
            EvidenceClaim(
                claim="The architecture is described in the paper.",
                evidence_type=EvidenceType.PAPER_REPORTED,
                source_urls=["https://aclanthology.org/2026.acl-long.1.pdf"],
                locator="Section 3",
            )
        ],
        method_diagram=diagram,
    )


def test_unofficial_award_source_is_not_verified() -> None:
    record = award_record(evidence_url="https://example.com/acl-awards")

    result = validate_award(
        record, allowed_hosts={"2026.aclweb.org", "aclanthology.org"}
    )

    assert result.status is AwardStatus.NOT_VERIFIED


def test_spoofed_official_host_is_not_verified() -> None:
    record = award_record(evidence_url="https://aclanthology.org.example.com/awards")

    result = validate_award(record, allowed_hosts={"aclanthology.org"})

    assert result.status is AwardStatus.NOT_VERIFIED


def test_official_award_source_is_verified() -> None:
    record = award_record(evidence_url="https://awards.aclanthology.org/acl-2026")

    result = validate_award(record, allowed_hosts={"aclanthology.org"})

    assert result.status is AwardStatus.VERIFIED


def test_missing_award_evidence_is_not_announced() -> None:
    result = validate_award(award_record(evidence_url=None), allowed_hosts={"aclanthology.org"})

    assert result.status is AwardStatus.NOT_ANNOUNCED


def test_numeric_claim_requires_paper_locator() -> None:
    deep_read = deep_read_with_claim(value="52.0", locator=None)

    with pytest.raises(ValueError, match="paper locator"):
        validate_deep_read(deep_read)


def test_numeric_claim_requires_metric_value_setting_and_source_url() -> None:
    incomplete = result_claim()
    incomplete.metric = ""
    incomplete.value = ""
    incomplete.evaluation_setting = ""
    incomplete.source_urls = []
    deep_read = DeepRead(paper_id="acl:2026.acl-long.1", result_claims=[incomplete])

    with pytest.raises(ValueError, match="metric"):
        validate_deep_read(deep_read)


def test_diagram_node_requires_paper_section() -> None:
    diagram = method_diagram(
        node=MethodNode(identifier="planner", label="Planner", paper_section=None)
    )

    with pytest.raises(ValueError, match="paper section"):
        validate_deep_read(deep_read_with_diagram(diagram))


def test_diagram_edge_requires_disclosed_data_flow_rationale() -> None:
    diagram = MethodDiagram(
        nodes=[MethodNode(identifier="planner", label="Planner", paper_section="3.1")],
        edges=[MethodEdge(source="planner", target="planner", data_flow_rationale=None)],
    )

    with pytest.raises(ValueError, match="data-flow rationale"):
        validate_deep_read(deep_read_with_diagram(diagram))


def test_why_it_matters_rejects_official_metadata_evidence() -> None:
    deep_read = DeepRead(
        paper_id="acl:2026.acl-long.1",
        why_it_matters=[
            EvidenceClaim(
                claim="This should not be allowed for a synthesis claim.",
                evidence_type=EvidenceType.OFFICIAL_METADATA,
                source_urls=["https://aclanthology.org/2026.acl-long.1.pdf"],
                locator="Section 1",
            )
        ],
    )

    with pytest.raises(ValueError, match="why_it_matters"):
        validate_deep_read(deep_read)


def test_synthetic_not_announced_fixture_is_not_an_award_claim() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "awards" / "acl-2026-awards.yaml"
    fixture = yaml.safe_load(fixture_path.read_text())

    assert fixture["synthetic_contract_fixture"] is True
    assert fixture["awards"] == []
    assert fixture["status"] == AwardStatus.NOT_ANNOUNCED.value
