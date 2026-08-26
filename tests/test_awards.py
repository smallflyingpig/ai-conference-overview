from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from conference_overview.awards import (
    AwardRecord,
    AwardStatus,
    DeepRead,
    MethodDiagram,
    MethodEdge,
    MethodNode,
    NoNumericResult,
    ResultClaim,
    validate_award,
    validate_deep_read,
)
from conference_overview.models import EvidenceClaim, EvidenceType


def award_record(
    *, evidence_url: str | None, status: AwardStatus | None = None
) -> AwardRecord:
    return AwardRecord(
        paper_id="acl:2026.acl-long.1",
        award_type="Best Paper",
        status=status
        or (
            AwardStatus.VERIFIED
            if evidence_url is not None
            else AwardStatus.NOT_ANNOUNCED
        ),
        evidence_url=evidence_url,
    )


def result_claim(
    *,
    value: object = "52.0",
    locator: str | None = "Table 2",
    metric: str = "Accuracy",
    evaluation_setting: str = "ACL 2026 synthetic evaluation",
    claim: str = "The method reaches the reported score.",
) -> ResultClaim:
    return ResultClaim(
        claim=claim,
        evidence_type=EvidenceType.PAPER_REPORTED,
        source_urls=["https://aclanthology.org/2026.acl-long.1.pdf"],
        metric=metric,
        value=value,
        evaluation_setting=evaluation_setting,
        locator=locator,
    )


def method_diagram(*, node: MethodNode | None = None) -> MethodDiagram:
    return MethodDiagram(
        nodes=[
            node
            or MethodNode(identifier="planner", label="Planner", paper_section="3.1")
        ],
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
        research_problem=evidence_claim(
            "The paper studies a disclosed research problem."
        ),
        contribution=evidence_claim("The paper contributes a disclosed method."),
        method_summary=evidence_claim(
            "The disclosed method connects inputs to outputs."
        ),
        result_claims=[result_claim(value=value, locator=locator)],
        why_it_matters=[
            EvidenceClaim(
                claim="The paper reports this result under the stated setting.",
                evidence_type=EvidenceType.PAPER_REPORTED,
                source_urls=["https://aclanthology.org/2026.acl-long.1.pdf"],
                locator="Section 5",
            )
        ],
        limitations=[evidence_claim("The paper reports a bounded limitation.")],
        **required_deep_read_sections(),
    )


def deep_read_with_diagram(diagram: MethodDiagram) -> DeepRead:
    return DeepRead(
        paper_id="acl:2026.acl-long.1",
        research_problem=evidence_claim(
            "The paper studies a disclosed research problem."
        ),
        contribution=evidence_claim("The paper contributes a disclosed method."),
        method_summary=evidence_claim(
            "The disclosed method connects inputs to outputs."
        ),
        result_claims=[result_claim()],
        why_it_matters=[
            EvidenceClaim(
                claim="The architecture is described in the paper.",
                evidence_type=EvidenceType.PAPER_REPORTED,
                source_urls=["https://aclanthology.org/2026.acl-long.1.pdf"],
                locator="Section 3",
            )
        ],
        limitations=[evidence_claim("The paper reports a bounded limitation.")],
        **required_deep_read_sections(),
        method_diagram=diagram,
    )


def evidence_claim(claim: str) -> EvidenceClaim:
    return EvidenceClaim(
        claim=claim,
        evidence_type=EvidenceType.PAPER_REPORTED,
        source_urls=["https://aclanthology.org/2026.acl-long.1.pdf"],
        locator="Section 3",
    )


def required_deep_read_sections() -> dict[str, list[EvidenceClaim]]:
    return {
        "data_training_setup": [
            evidence_claim("The paper discloses its data and training setup.")
        ],
        "prior_work_differences": [
            evidence_claim("The paper states a difference from prior work.")
        ],
        "reproducibility_assessment": [
            evidence_claim("The paper provides reproducibility evidence.")
        ],
        "transferable_implications": [
            EvidenceClaim(
                claim="The disclosed design may transfer to another setting.",
                evidence_type=EvidenceType.INFERENCE,
                source_urls=["https://aclanthology.org/2026.acl-long.1.pdf"],
                locator="Section 3",
            )
        ],
    }


def test_unofficial_award_source_is_not_verified() -> None:
    record = award_record(evidence_url="https://example.com/acl-awards")

    result = validate_award(
        record, allowed_hosts={"2026.aclweb.org", "aclanthology.org"}
    )

    assert result.status is AwardStatus.NOT_VERIFIED


def test_position_paper_can_explicitly_report_no_numeric_result() -> None:
    deep_read = deep_read_with_claim(value="52.0", locator="Table 2").model_dump()
    deep_read["result_claims"] = []
    deep_read["no_numeric_result"] = NoNumericResult(
        paper_type="position_paper",
        reason=evidence_claim(
            "The paper presents a normative position rather than an empirical method comparison."
        ),
    ).model_dump()

    parsed = validate_deep_read(DeepRead.model_validate(deep_read))

    assert parsed.result_claims == []
    assert parsed.no_numeric_result is not None


def test_ordinary_deep_read_still_requires_a_numeric_result() -> None:
    deep_read = deep_read_with_claim(value="52.0", locator="Table 2").model_dump()
    deep_read["result_claims"] = []

    with pytest.raises(ValidationError, match="numeric results"):
        DeepRead.model_validate(deep_read)


@pytest.mark.parametrize(
    "status", [AwardStatus.NOT_VERIFIED, AwardStatus.NOT_ANNOUNCED]
)
def test_official_host_does_not_promote_non_verified_award(
    status: AwardStatus,
) -> None:
    record = award_record(
        evidence_url="https://aclanthology.org/2026.acl-long.1/",
        status=status,
    )

    result = validate_award(record, allowed_hosts={"aclanthology.org"})

    assert result.status is status


def test_spoofed_official_host_is_not_verified() -> None:
    record = award_record(evidence_url="https://aclanthology.org.example.com/awards")

    result = validate_award(record, allowed_hosts={"aclanthology.org"})

    assert result.status is AwardStatus.NOT_VERIFIED


def test_official_award_source_is_verified() -> None:
    record = award_record(evidence_url="https://awards.aclanthology.org/acl-2026")

    result = validate_award(record, allowed_hosts={"aclanthology.org"})

    assert result.status is AwardStatus.VERIFIED


@pytest.mark.parametrize(
    ("evidence_url", "allowed_host"),
    [
        ("https://faß.de/awards", "xn--fa-hia.de"),
        ("https://xn--fa-hia.de/awards", "faß.de"),
    ],
)
def test_uts46_unicode_and_punycode_hosts_authorize_the_same_domain(
    evidence_url: str, allowed_host: str
) -> None:
    result = validate_award(
        award_record(evidence_url=evidence_url), allowed_hosts={allowed_host}
    )

    assert result.status is AwardStatus.VERIFIED


def test_uts46_sharp_s_domain_does_not_authorize_ascii_ss_lookalike() -> None:
    result = validate_award(
        award_record(evidence_url="https://fass.de/awards"),
        allowed_hosts={"faß.de"},
    )

    assert result.status is AwardStatus.NOT_VERIFIED


@pytest.mark.parametrize("root_separator", [".", "。"])
def test_single_terminal_root_separator_authorizes_official_host(
    root_separator: str,
) -> None:
    result = validate_award(
        award_record(evidence_url=f"https://example.com{root_separator}/awards"),
        allowed_hosts={"example.com"},
    )

    assert result.status is AwardStatus.VERIFIED


def test_double_terminal_dot_evidence_is_not_authorized() -> None:
    result = validate_award(
        award_record(evidence_url="https://example.com../awards"),
        allowed_hosts={"example.com"},
    )

    assert result.status is AwardStatus.NOT_VERIFIED


def test_verified_award_requires_evidence_at_construction() -> None:
    with pytest.raises(ValidationError, match="evidence"):
        AwardRecord(
            paper_id="acl:2026.acl-long.1",
            award_type="Best Paper",
            status=AwardStatus.VERIFIED,
            evidence_url=None,
        )


def test_missing_award_evidence_is_not_announced() -> None:
    result = validate_award(
        award_record(evidence_url=None), allowed_hosts={"aclanthology.org"}
    )

    assert result.status is AwardStatus.NOT_ANNOUNCED


def test_numeric_claim_requires_paper_locator() -> None:
    deep_read = deep_read_with_claim(value="52.0", locator=None)

    with pytest.raises(ValueError, match="paper locator"):
        validate_deep_read(deep_read)


@pytest.mark.parametrize(
    "value",
    [
        "not-a-number",
        float("nan"),
        float("inf"),
        float("-inf"),
        "NaN",
        "Infinity",
        "-Infinity",
        "∞",
        True,
    ],
)
def test_numeric_claim_rejects_non_finite_or_non_numeric_value(value: object) -> None:
    with pytest.raises(ValidationError, match="finite number"):
        result_claim(value=value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (52, Decimal(52)),
        (Decimal("52.0"), Decimal("52.0")),
        (52.0, Decimal("52.0")),
        ("52.0", Decimal("52.0")),
    ],
)
def test_numeric_claim_canonicalizes_finite_numbers(
    value: object, expected: Decimal
) -> None:
    assert result_claim(value=value).value == expected  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    [("metric", " "), ("evaluation_setting", "\t"), ("locator", "\n")],
)
def test_numeric_claim_rejects_blank_required_text(field: str, value: str) -> None:
    values = {"metric": "Accuracy", "evaluation_setting": "test", "locator": "Table 1"}
    values[field] = value

    with pytest.raises(ValidationError):
        result_claim(**values)


def test_diagram_node_requires_paper_section() -> None:
    diagram = method_diagram(
        node=MethodNode(identifier="planner", label="Planner", paper_section=None)
    )

    with pytest.raises(ValueError, match="paper section"):
        validate_deep_read(deep_read_with_diagram(diagram))


def test_diagram_edge_requires_disclosed_data_flow_rationale() -> None:
    diagram = MethodDiagram(
        nodes=[MethodNode(identifier="planner", label="Planner", paper_section="3.1")],
        edges=[
            MethodEdge(source="planner", target="planner", data_flow_rationale=None)
        ],
    )

    with pytest.raises(ValueError, match="data-flow rationale"):
        validate_deep_read(deep_read_with_diagram(diagram))


def test_why_it_matters_rejects_official_metadata_evidence() -> None:
    deep_read = DeepRead(
        paper_id="acl:2026.acl-long.1",
        research_problem=evidence_claim(
            "The paper studies a disclosed research problem."
        ),
        contribution=evidence_claim("The paper contributes a disclosed method."),
        method_summary=evidence_claim(
            "The disclosed method connects inputs to outputs."
        ),
        result_claims=[result_claim()],
        why_it_matters=[
            EvidenceClaim(
                claim="This should not be allowed for a synthesis claim.",
                evidence_type=EvidenceType.OFFICIAL_METADATA,
                source_urls=["https://aclanthology.org/2026.acl-long.1.pdf"],
                locator="Section 1",
            )
        ],
        limitations=[evidence_claim("The paper reports a bounded limitation.")],
        **required_deep_read_sections(),
    )

    with pytest.raises(ValueError, match="why_it_matters"):
        validate_deep_read(deep_read)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: AwardRecord(paper_id=" ", award_type="Best Paper"),
        lambda: AwardRecord(paper_id="paper", award_type="\t"),
        lambda: DeepRead(paper_id="\n"),
        lambda: result_claim(value="52.0", locator="Table 1", claim=" "),
        lambda: EvidenceClaim(
            claim=" ",
            evidence_type=EvidenceType.PAPER_REPORTED,
            source_urls=["https://aclanthology.org/2026.acl-long.1.pdf"],
        ),
        lambda: MethodNode(identifier="planner", label=" ", paper_section="3.1"),
        lambda: MethodNode(identifier="planner", label="Planner", paper_section="\t"),
        lambda: MethodEdge(
            source="planner", target="planner", data_flow_rationale="\n"
        ),
    ],
)
def test_models_reject_whitespace_only_required_text(factory: object) -> None:
    with pytest.raises(ValidationError):
        factory()  # type: ignore[operator]


def test_diagram_canonicalizes_node_identifiers_before_duplicate_checks() -> None:
    diagram = MethodDiagram(
        nodes=[
            MethodNode(identifier="planner", label="Planner", paper_section="3.1"),
            MethodNode(identifier="planner ", label="Planner 2", paper_section="3.2"),
        ]
    )

    with pytest.raises(ValueError, match="identifiers must be unique"):
        validate_deep_read(deep_read_with_diagram(diagram))


def test_diagram_rejects_duplicate_directed_edges() -> None:
    diagram = MethodDiagram(
        nodes=[MethodNode(identifier="planner", label="Planner", paper_section="3.1")],
        edges=[
            MethodEdge(
                source="planner",
                target="planner",
                data_flow_rationale="The paper discloses an update.",
            ),
            MethodEdge(
                source="planner ",
                target="planner",
                data_flow_rationale="The paper repeats the same update.",
            ),
        ],
    )

    with pytest.raises(ValueError, match="duplicate directed edges"):
        validate_deep_read(deep_read_with_diagram(diagram))


def test_synthetic_not_announced_fixture_is_not_an_award_claim() -> None:
    fixture_path = (
        Path(__file__).parent / "fixtures" / "awards" / "acl-2026-awards.yaml"
    )
    fixture = yaml.safe_load(fixture_path.read_text())

    assert fixture["synthetic_contract_fixture"] is True
    assert fixture["awards"] == []
    assert fixture["status"] == AwardStatus.NOT_ANNOUNCED.value


@pytest.mark.parametrize(
    "field",
    [
        "research_problem",
        "contribution",
        "method_summary",
        "result_claims",
        "why_it_matters",
        "limitations",
        "data_training_setup",
        "prior_work_differences",
        "reproducibility_assessment",
        "transferable_implications",
    ],
)
def test_award_deep_read_rejects_missing_required_sections(field: str) -> None:
    valid = deep_read_with_claim(value="52.0", locator="Table 2").model_dump()
    valid[field] = [] if isinstance(valid[field], list) else None

    with pytest.raises(ValidationError):
        DeepRead.model_validate(valid)


def test_result_claim_requires_paper_reported_evidence() -> None:
    payload = result_claim().model_dump()
    payload["evidence_type"] = EvidenceType.INFERENCE

    with pytest.raises(ValidationError, match="paper_reported"):
        ResultClaim.model_validate(payload)


@pytest.mark.parametrize(
    "evidence_type",
    [EvidenceType.OFFICIAL_METADATA, EvidenceType.PAPER_REPORTED],
)
def test_transferable_implications_require_interpretive_evidence(
    evidence_type: EvidenceType,
) -> None:
    deep_read = deep_read_with_claim(value="52.0", locator="Table 2")
    deep_read.transferable_implications[0].evidence_type = evidence_type

    with pytest.raises(ValueError, match="transferable_implications"):
        validate_deep_read(deep_read)


def test_present_method_diagram_requires_at_least_one_node() -> None:
    with pytest.raises(ValidationError, match="nodes"):
        MethodDiagram(nodes=[], edges=[])
