import csv
import hashlib
import json
import os
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from conference_overview import reports
from conference_overview.awards import (
    AwardAnnouncement,
    AwardRecord,
    AwardStatus,
    DeepRead,
    MethodDiagram,
    MethodEdge,
    MethodNode,
    ResultClaim,
)
from conference_overview.classification import Assignment, ThemeAudit, audit_theme
from conference_overview.metrics import (
    CrossVenueSpread,
    EmergingScore,
    cross_venue_spread,
    emerging_score,
)
from conference_overview.models import (
    AdvanceCategory,
    AdvanceRecord,
    EvidenceClaim,
    EvidenceType,
    PaperRecord,
    RecordStatus,
    SourceRef,
    ThemeDisclosure,
    ThemeDisclosureStatus,
)
from conference_overview.reports import (
    ArtifactValidationError,
    ReleaseBundle,
    resolve_current_release,
    write_release,
)
from conference_overview.validate import PublicationBlocked, validate_records


def paper(paper_id: str) -> PaperRecord:
    return PaperRecord(
        paper_id=paper_id,
        title=f"Title {paper_id}",
        normalized_title=f"title {paper_id}",
        authors=["A. Author"],
        venue="ACL",
        year=2026,
        track="long",
        landing_url=f"https://aclanthology.org/{paper_id}/",
        source=SourceRef(
            name="ACL Anthology",
            url="https://aclanthology.org/volumes/2026.acl-long/",
            retrieved_at=datetime(2026, 8, 24, 1, 2, 3, tzinfo=UTC),
            sha256="a" * 64,
        ),
        status=RecordStatus.COMPLETE,
        abstract="Abstract.",
        doi=f"10.1000/{paper_id}",
        pdf_url=f"https://aclanthology.org/{paper_id}.pdf",
    )


def assignment(paper_id: str) -> Assignment:
    return Assignment(
        paper_id=paper_id,
        primary_topic="Foundation Models",
        secondary_topics=("Evaluation",),
        confidence=Decimal("0.95"),
        rationale="The abstract explicitly discusses model pretraining.",
        taxonomy_version="2026-08-24-v1",
    )


def paper_claim(
    text: str, *, evidence_type: EvidenceType = EvidenceType.PAPER_REPORTED
) -> EvidenceClaim:
    return EvidenceClaim(
        claim=text,
        evidence_type=evidence_type,
        source_urls=["https://aclanthology.org/paper-a.pdf"],
        locator="Section 3",
    )


def award_deep_read() -> DeepRead:
    return DeepRead(
        paper_id="paper-a",
        research_problem=paper_claim("The paper studies a disclosed problem."),
        contribution=paper_claim("The paper contributes a disclosed method."),
        method_summary=paper_claim("The method transforms records into predictions."),
        result_claims=[
            ResultClaim(
                claim="Accuracy reaches 81.4%.",
                evidence_type=EvidenceType.PAPER_REPORTED,
                source_urls=["https://aclanthology.org/paper-a.pdf"],
                locator="Table 2, p. 7",
                metric="Accuracy",
                value="81.4",
                evaluation_setting="Held-out test split",
            )
        ],
        why_it_matters=[
            paper_claim(
                "The result supports a cross-paper interpretation.",
                evidence_type=EvidenceType.CROSS_PAPER_SYNTHESIS,
            )
        ],
        limitations=[paper_claim("The paper evaluates one bounded setting.")],
        data_training_setup=[paper_claim("The paper discloses the training setup.")],
        prior_work_differences=[
            paper_claim("The paper differs from prior work in its objective.")
        ],
        reproducibility_assessment=[
            paper_claim("The appendix discloses reproducibility details.")
        ],
        transferable_implications=[
            paper_claim(
                "The method may transfer to data-quality pipelines.",
                evidence_type=EvidenceType.INFERENCE,
            )
        ],
        method_diagram=MethodDiagram(
            nodes=[
                MethodNode(identifier="input", label="Input", paper_section="3.1"),
                MethodNode(identifier="model", label="Model", paper_section="3.2"),
            ],
            edges=[
                MethodEdge(
                    source="input",
                    target="model",
                    data_flow_rationale="The disclosed input enters the model.",
                )
            ],
        ),
    )


def publishable_bundle() -> ReleaseBundle:
    records = (paper("paper-z"), paper("paper-a"))
    return ReleaseBundle(
        records=records,
        validation=validate_records(records, [], expected_included=2),
        assignments=tuple(assignment(record.paper_id) for record in records),
        audits={"Foundation Models": audit_theme([True] * 46 + [False] * 4)},
        metrics={
            "emerging_score": emerging_score(
                share_growth="0.8", spread_growth="0.5", novelty="0.25"
            ),
            "cross_venue_spread": CrossVenueSpread(
                present_venue_count=2,
                present_venue_fraction=Decimal("0.5"),
                configured_venues=("ACL", "EMNLP", "NAACL", "NeurIPS"),
                present_venues=("ACL", "EMNLP"),
            ),
        },
        awards=(
            AwardRecord(
                paper_id="paper-a",
                award_type="Best Paper",
                status=AwardStatus.VERIFIED,
                evidence_url="https://2026.aclweb.org/awards/",
            ),
        ),
        award_announcement=AwardAnnouncement(status=AwardStatus.NOT_VERIFIED),
        award_deep_reads=(award_deep_read(),),
        advances=(
            AdvanceRecord(
                advance_id="data-quality",
                title="Evidence-backed data quality",
                category=AdvanceCategory.DATA_TRAINING,
                supporting_paper_ids=("paper-a",),
                claims=(
                    paper_claim(
                        "The accepted work supports a data-quality advance.",
                        evidence_type=EvidenceType.CROSS_PAPER_SYNTHESIS,
                    ),
                ),
            ),
        ),
        theme_disclosures=(
            ThemeDisclosure(
                theme="Sparse expert routing",
                status=ThemeDisclosureStatus.EXPERIMENTAL,
                reason=paper_claim(
                    "This theme remains experimental pending audit.",
                    evidence_type=EvidenceType.INFERENCE,
                ),
            ),
        ),
        claims=(
            EvidenceClaim(
                claim="The papers form a source-backed distribution snapshot.",
                evidence_type=EvidenceType.CROSS_PAPER_SYNTHESIS,
                source_urls=["https://aclanthology.org/volumes/2026.acl-long/"],
                locator="ACL 2026 long-paper volume",
            ),
        ),
        taxonomy_version="2026-08-24-v1",
        generated_at=datetime(2026, 8, 24, 2, 3, 4, tzinfo=UTC),
    )


def test_report_refuses_unpublishable_validation_without_touching_release(
    tmp_path: Path,
) -> None:
    output = tmp_path / "release"
    output.mkdir()
    sentinel = output / "last-valid.txt"
    sentinel.write_text("keep me", encoding="utf-8")
    bundle = publishable_bundle()
    blocked = replace(
        bundle,
        validation=replace(
            bundle.validation,
            expected_count_matches=False,
            publishable=False,
        ),
    )

    with pytest.raises(PublicationBlocked):
        write_release(blocked, output)

    assert sentinel.read_text(encoding="utf-8") == "keep me"
    assert sorted(path.name for path in output.iterdir()) == ["last-valid.txt"]


def test_report_honors_explicit_unpublishable_validation_state(tmp_path: Path) -> None:
    bundle = publishable_bundle()

    with pytest.raises(PublicationBlocked, match="marked unpublishable"):
        write_release(
            replace(bundle, validation=replace(bundle.validation, publishable=False)),
            tmp_path / "release",
        )

    assert not (tmp_path / "release").exists()


def test_valid_release_contains_complete_provenance_and_diagnostics(
    tmp_path: Path,
) -> None:
    write_release(publishable_bundle(), tmp_path)
    release = resolve_current_release(tmp_path)

    provenance = json.loads((release / "provenance.json").read_text())
    validation = json.loads((release / "validation.json").read_text())
    overview = json.loads((release / "overview.json").read_text())

    assert provenance["source_sha256"] == "a" * 64
    assert provenance["source_url"] == (
        "https://aclanthology.org/volumes/2026.acl-long/"
    )
    assert provenance["source_retrieved_at"] == "2026-08-24T01:02:03Z"
    assert provenance["taxonomy_version"] == "2026-08-24-v1"
    assert validation["definite_duplicate_count"] == 0
    assert validation["duplicate_candidate_count"] == 0
    assert validation["definite_duplicate_pairs"] == []
    assert validation["duplicate_candidates"] == []
    assert validation["status_mismatch_ids"] == []
    assert validation["status_mismatch_count"] == 0
    assert validation["unresolved_record_ids"] == []
    assert validation["unresolved_record_count"] == 0
    assert validation["missing_abstract_count"] == 0
    assert validation["missing_pdf_count"] == 0
    assert validation["missing_doi_count"] == 0
    assert validation["snapshot_addition_count"] == 0
    assert validation["snapshot_removal_count"] == 0
    assert overview["audits"]["Foundation Models"]["sample_size"] == 50
    assert overview["audits"]["Foundation Models"]["thresholds"] == {
        "minimum_observed_precision": "0.90",
        "minimum_wilson_lower_95": "0.80",
    }
    assert overview["awards"][0]["status"] == "verified"
    assert overview["awards"][0]["verification"] == {
        "allowed_hosts": ["2026.aclweb.org", "aclanthology.org"],
        "evidence_host": "2026.aclweb.org",
        "validator": "validate_award-v1",
    }
    assert overview["award_deep_reads"][0]["contribution"]["claim"].startswith(
        "The paper contributes"
    )
    assert overview["advances"][0]["category"] == "data_training"
    assert overview["theme_disclosures"][0]["status"] == "experimental"
    assert overview["build_metadata"] == {
        "generated_at": "2026-08-24T02:03:04Z",
        "producer": "conference_overview.reports.write_release",
        "schema_version": "release-build-v1",
    }
    assert overview["metrics"]["emerging_score"]["components"] == {
        "novelty": "0.25",
        "share_growth": "0.8",
        "spread_growth": "0.5",
    }


def test_release_rejects_unofficial_verified_award_before_serializing_deep_read(
    tmp_path: Path,
) -> None:
    bundle = publishable_bundle()
    unofficial = AwardRecord(
        paper_id=bundle.awards[0].paper_id,
        award_type=bundle.awards[0].award_type,
        status=AwardStatus.VERIFIED,
        evidence_url="https://example.com/awards/",
    )

    with pytest.raises(PublicationBlocked, match="official award"):
        write_release(
            replace(bundle, awards=(unofficial,)),
            tmp_path / "unofficial-award",
        )


def test_release_canonicalizes_official_evidence_host_with_trailing_dot(
    tmp_path: Path,
) -> None:
    bundle = publishable_bundle()
    trailing_dot = bundle.awards[0].model_copy(
        update={"evidence_url": "https://2026.aclweb.org./awards/"}
    )

    write_release(
        replace(bundle, awards=(trailing_dot,)),
        tmp_path / "trailing-dot-award",
    )

    overview = json.loads(
        (
            resolve_current_release(tmp_path / "trailing-dot-award") / "overview.json"
        ).read_text()
    )
    assert overview["awards"][0]["verification"]["evidence_host"] == ("2026.aclweb.org")


@pytest.mark.parametrize(
    "updates",
    [
        {"paper_id": " "},
        {"award_type": "\t"},
        {"evidence_url": "not-a-url"},
        {"evidence_url": None},
    ],
)
def test_release_reparses_awards_before_sorting_or_serializing(
    tmp_path: Path, updates: dict[str, object]
) -> None:
    bundle = publishable_bundle()
    bypassed = bundle.awards[0].model_copy(update=updates)

    with pytest.raises((ValueError, PublicationBlocked)):
        write_release(
            replace(bundle, awards=(bypassed,)),
            tmp_path / "bypassed-award",
        )

    assert not (tmp_path / "bypassed-award").exists()


def test_release_keeps_exact_six_artifacts_with_extended_overview(
    tmp_path: Path,
) -> None:
    write_release(publishable_bundle(), tmp_path)

    assert sorted(
        path.name for path in resolve_current_release(tmp_path).iterdir()
    ) == [
        "overview.json",
        "overview.md",
        "papers.csv",
        "papers.json",
        "provenance.json",
        "validation.json",
    ]


@pytest.mark.parametrize(
    "invalid_kind", ["missing-section", "result-evidence", "empty-diagram"]
)
def test_release_revalidates_deep_read_before_writing(
    tmp_path: Path, invalid_kind: str
) -> None:
    bundle = publishable_bundle()
    deep_read = bundle.award_deep_reads[0]
    if invalid_kind == "missing-section":
        invalid = deep_read.model_copy(update={"transferable_implications": []})
    elif invalid_kind == "result-evidence":
        result = deep_read.result_claims[0].model_copy(
            update={"evidence_type": EvidenceType.INFERENCE}
        )
        invalid = deep_read.model_copy(update={"result_claims": [result]})
    else:
        diagram = deep_read.method_diagram.model_copy(update={"nodes": []})  # type: ignore[union-attr]
        invalid = deep_read.model_copy(update={"method_diagram": diagram})

    with pytest.raises((ValueError, PublicationBlocked)):
        write_release(
            replace(bundle, award_deep_reads=(invalid,)),
            tmp_path / f"invalid-deep-read-{invalid_kind}",
        )

    assert not (tmp_path / f"invalid-deep-read-{invalid_kind}").exists()


@pytest.mark.parametrize("duplicate_type", [" best   paper ", "STRASSE"])
def test_release_rejects_duplicate_normalized_award_identity(
    tmp_path: Path, duplicate_type: str
) -> None:
    bundle = publishable_bundle()
    original = bundle.awards[0].model_copy(
        update={"award_type": "Straße" if duplicate_type == "STRASSE" else "Best Paper"}
    )
    duplicate = bundle.awards[0].model_copy(update={"award_type": duplicate_type})

    with pytest.raises(PublicationBlocked, match="award identities"):
        write_release(
            replace(bundle, awards=(original, duplicate)),
            tmp_path / "duplicate-award",
        )


def test_release_allows_distinct_awards_for_the_same_paper(tmp_path: Path) -> None:
    bundle = publishable_bundle()
    outstanding = bundle.awards[0].model_copy(
        update={"award_type": "Outstanding Paper"}
    )

    write_release(
        replace(bundle, awards=(*bundle.awards, outstanding)),
        tmp_path / "multiple-awards",
    )

    overview = json.loads(
        (
            resolve_current_release(tmp_path / "multiple-awards") / "overview.json"
        ).read_text()
    )
    assert [award["award_type"] for award in overview["awards"]] == [
        "Best Paper",
        "Outstanding Paper",
    ]
    assert all(award["route_key"].startswith("award-") for award in overview["awards"])
    assert len({award["route_key"] for award in overview["awards"]}) == 2
    assert overview["awards"][0]["canonical_identity"] == {
        "award_type": "best paper",
        "paper_id": "paper-a",
    }


def test_release_exposes_auditable_comparison_contract(tmp_path: Path) -> None:
    write_release(publishable_bundle(), tmp_path)
    release = resolve_current_release(tmp_path)
    contract = json.loads((release / "overview.json").read_text())[
        "comparison_contract"
    ]

    assert contract["schema_version"] == "conference-comparison-v1"
    assert contract["comparison_scope"] == {
        "denominator": {
            "artifact_field": "validation.included_count",
            "description": "validated included papers after explicit exclusions",
            "unit": "paper",
        },
        "excluded_records": "kept explicit and excluded from the denominator",
        "inclusion_statuses": ["complete", "partial"],
        "track": "long",
        "venue": "ACL",
    }
    assert contract["metric_contract"]["formula_version"] == "conference-metrics-v1"
    assert contract["metric_contract"]["topic_share"] == {
        "denominator": "validation.included_count",
        "formula": "primary_topic_paper_count / validated_included_paper_count",
        "numerator": "one primary-topic assignment per included paper",
        "version": "topic-share-v1",
    }
    assert contract["metric_contract"]["emerging_score"]["weights"] == {
        "novelty": "0.20",
        "share_growth": "0.45",
        "spread_growth": "0.35",
    }
    spread_contract = contract["metric_contract"]["cross_venue_spread"]
    assert spread_contract["configured_venues"] == [
        "ACL",
        "EMNLP",
        "NAACL",
        "NeurIPS",
    ]
    assert spread_contract["configured_venue_count"] == 4
    expected_population_id = hashlib.sha256(
        json.dumps(
            ["ACL", "EMNLP", "NAACL", "NeurIPS"],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    assert spread_contract["configured_venue_id"] == expected_population_id
    identity_payload = {
        key: value for key, value in contract.items() if key != "contract_id"
    }
    expected_id = hashlib.sha256(
        json.dumps(
            identity_payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    assert contract["contract_id"] == expected_id


def test_release_rejects_mixed_venue_year_or_track_scope(tmp_path: Path) -> None:
    bundle = publishable_bundle()
    mixed_records = (
        bundle.records[0],
        bundle.records[1].model_copy(
            update={"venue": "EMNLP", "year": 2025, "track": "short"}
        ),
    )

    with pytest.raises(PublicationBlocked, match="venue/year/track scope"):
        write_release(
            replace(
                bundle,
                records=mixed_records,
                validation=validate_records(mixed_records, [], expected_included=2),
            ),
            tmp_path / "mixed-scope",
        )


def test_release_rejects_metric_values_outside_declared_formula_contract(
    tmp_path: Path,
) -> None:
    bundle = publishable_bundle()
    forged = EmergingScore(
        score=Decimal("0.60"),
        components={
            "share_growth": "0.8",
            "spread_growth": "0.5",
            "novelty": "0.25",
        },
        weights={
            "share_growth": "0.40",
            "spread_growth": "0.40",
            "novelty": "0.20",
        },
    )

    with pytest.raises(PublicationBlocked, match="metric formula contract"):
        write_release(
            replace(
                bundle,
                metrics={**bundle.metrics, "emerging_score": forged},
            ),
            tmp_path / "forged-metric",
        )


def test_release_rejects_cross_venue_fraction_contradicting_configured_population(
    tmp_path: Path,
) -> None:
    bundle = publishable_bundle()
    spread = bundle.metrics["cross_venue_spread"]
    assert isinstance(spread, CrossVenueSpread)

    with pytest.raises(PublicationBlocked, match="cross_venue_spread"):
        write_release(
            replace(
                bundle,
                metrics={
                    **bundle.metrics,
                    "cross_venue_spread": replace(
                        spread,
                        present_venue_fraction=Decimal("0.9"),
                    ),
                },
            ),
            tmp_path / "contradictory-spread",
        )


@pytest.mark.parametrize(
    "change",
    [
        {"present_venue_count": 3},
        {
            "present_venue_count": True,
            "present_venue_fraction": Decimal("0.25"),
            "present_venues": ("ACL",),
        },
        {"present_venues": ("ACL", "CVPR")},
        {"configured_venues": ("ACL", "EMNLP", "EMNLP", "NeurIPS")},
    ],
    ids=["count", "boolean-count", "topic-presence", "configured-population"],
)
def test_release_rejects_cross_venue_population_semantic_contradictions(
    tmp_path: Path,
    change: dict[str, object],
) -> None:
    bundle = publishable_bundle()
    spread = bundle.metrics["cross_venue_spread"]
    assert isinstance(spread, CrossVenueSpread)

    with pytest.raises(PublicationBlocked, match="cross_venue_spread"):
        write_release(
            replace(
                bundle,
                metrics={
                    **bundle.metrics,
                    "cross_venue_spread": replace(spread, **change),
                },
            ),
            tmp_path / "contradictory-population",
        )


def test_release_accepts_exact_cross_venue_fraction(tmp_path: Path) -> None:
    bundle = publishable_bundle()
    exact_spread = cross_venue_spread(
        topic_counts={"ACL": 1, "EMNLP": 0, "NAACL": 1, "NeurIPS": 0},
        configured_venues=["NeurIPS", "ACL", "NAACL", "EMNLP"],
    )

    write_release(
        replace(
            bundle,
            metrics={**bundle.metrics, "cross_venue_spread": exact_spread},
        ),
        tmp_path / "exact-spread",
    )

    overview = json.loads(
        (
            resolve_current_release(tmp_path / "exact-spread") / "overview.json"
        ).read_text()
    )
    assert overview["metrics"]["cross_venue_spread"] == {
        "configured_venues": ["ACL", "EMNLP", "NAACL", "NeurIPS"],
        "present_venue_count": 2,
        "present_venue_fraction": "0.5",
        "present_venues": ["ACL", "NAACL"],
    }


def test_configured_venue_population_changes_contract_identity(tmp_path: Path) -> None:
    bundle = publishable_bundle()
    acl_emnlp = cross_venue_spread(
        topic_counts={"ACL": 1, "EMNLP": 1},
        configured_venues=["ACL", "EMNLP"],
    )
    acl_naacl = cross_venue_spread(
        topic_counts={"ACL": 1, "NAACL": 1},
        configured_venues=["NAACL", "ACL"],
    )
    emnlp_acl = cross_venue_spread(
        topic_counts={"EMNLP": 1, "ACL": 1},
        configured_venues=["EMNLP", "ACL"],
    )

    write_release(
        replace(bundle, metrics={**bundle.metrics, "cross_venue_spread": acl_emnlp}),
        tmp_path / "acl-emnlp",
    )
    write_release(
        replace(bundle, metrics={**bundle.metrics, "cross_venue_spread": acl_naacl}),
        tmp_path / "acl-naacl",
    )
    write_release(
        replace(bundle, metrics={**bundle.metrics, "cross_venue_spread": emnlp_acl}),
        tmp_path / "emnlp-acl",
    )
    first = json.loads(
        (resolve_current_release(tmp_path / "acl-emnlp") / "overview.json").read_text()
    )["comparison_contract"]
    second = json.loads(
        (resolve_current_release(tmp_path / "acl-naacl") / "overview.json").read_text()
    )["comparison_contract"]
    reordered = json.loads(
        (resolve_current_release(tmp_path / "emnlp-acl") / "overview.json").read_text()
    )["comparison_contract"]

    assert first["metric_contract"]["cross_venue_spread"]["configured_venue_count"] == 2
    assert (
        second["metric_contract"]["cross_venue_spread"]["configured_venue_count"] == 2
    )
    assert (
        first["metric_contract"]["cross_venue_spread"]["configured_venue_id"]
        != second["metric_contract"]["cross_venue_spread"]["configured_venue_id"]
    )
    assert first["contract_id"] != second["contract_id"]
    assert first == reordered


def test_release_orders_paper_outputs_and_derives_csv_from_the_same_payload(
    tmp_path: Path,
) -> None:
    write_release(publishable_bundle(), tmp_path)
    release = resolve_current_release(tmp_path)

    papers = json.loads((release / "papers.json").read_text())
    with (release / "papers.csv").open(newline="", encoding="utf-8") as csv_file:
        csv_rows = list(csv.DictReader(csv_file))

    assert [item["paper_id"] for item in papers] == ["paper-a", "paper-z"]
    assert [item["paper_id"] for item in csv_rows] == ["paper-a", "paper-z"]
    assert json.loads(csv_rows[0]["authors"]) == papers[0]["authors"]


def test_equal_release_writes_are_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    write_release(publishable_bundle(), first)
    write_release(publishable_bundle(), second)

    assert {
        path.name: path.read_bytes()
        for path in resolve_current_release(first).iterdir()
    } == {
        path.name: path.read_bytes()
        for path in resolve_current_release(second).iterdir()
    }


def test_markdown_renders_only_typed_evidence_claims(tmp_path: Path) -> None:
    bundle = publishable_bundle()
    write_release(bundle, tmp_path / "valid")
    release = resolve_current_release(tmp_path / "valid")

    markdown = (release / "overview.md").read_text()
    assert "## Evidence-backed synthesis" in markdown
    assert "The papers form a source-backed distribution snapshot." in markdown
    assert "cross_paper_synthesis" in markdown
    assert "https://aclanthology.org/volumes/2026.acl-long/" in markdown

    invalid = replace(bundle, claims=("unsupported 98% improvement",))
    with pytest.raises(ValueError, match="EvidenceClaim"):
        write_release(invalid, tmp_path / "invalid")  # type: ignore[arg-type]
    assert not (tmp_path / "invalid").exists()


def test_release_reapplies_assignment_and_audit_publication_gates(
    tmp_path: Path,
) -> None:
    bundle = publishable_bundle()
    weak_audit = ThemeAudit(
        sample_size=50,
        correct_count=45,
        observed_precision=Decimal("0.90"),
        wilson_lower_95=Decimal("0.786"),
    )

    with pytest.raises(PublicationBlocked, match="Wilson"):
        write_release(
            replace(bundle, audits={"Foundation Models": weak_audit}),
            tmp_path / "weak-audit",
        )

    with pytest.raises(PublicationBlocked, match="missing assignments"):
        write_release(
            replace(bundle, assignments=(assignment("paper-a"),)),
            tmp_path / "missing-assignment",
        )


def test_release_rejects_unbound_full_theme_review_result_chain(
    tmp_path: Path,
) -> None:
    first_result = "b" * 64
    final_result = "c" * 64
    first_stage = {
        "base_assignments_sha256": "a" * 64,
        "result_assignments_sha256": first_result,
        "sources": [],
    }
    final_stage = {
        "base_assignments_sha256": first_result,
        "result_assignments_sha256": final_result,
        "sources": [],
        "prior_stages": [first_stage],
        "stage_index": 2,
    }
    lineage = {
        "assignments_sha256": final_result,
        "full_theme_review_stages": final_stage,
    }

    broken_middle = json.loads(json.dumps(lineage))
    broken_middle["full_theme_review_stages"]["prior_stages"][0][
        "result_assignments_sha256"
    ] = "f" * 64
    with pytest.raises(PublicationBlocked, match="full-theme review.*chain"):
        write_release(
            replace(publishable_bundle(), classification_lineage=broken_middle),
            tmp_path / "broken-middle",
        )

    broken_final = json.loads(json.dumps(lineage))
    broken_final["full_theme_review_stages"]["result_assignments_sha256"] = "f" * 64
    with pytest.raises(PublicationBlocked, match="full-theme review.*chain"):
        write_release(
            replace(publishable_bundle(), classification_lineage=broken_final),
            tmp_path / "broken-final",
        )

def test_release_retains_a_failed_primary_theme_audit_when_explicitly_withheld(
    tmp_path: Path,
) -> None:
    bundle = publishable_bundle()
    weak_audit = ThemeAudit(
        sample_size=50,
        correct_count=42,
        observed_precision=Decimal("0.84"),
        wilson_lower_95=Decimal("0.7149"),
    )
    disclosure = ThemeDisclosure(
        theme="Foundation Models",
        status=ThemeDisclosureStatus.EXPERIMENTAL,
        reason=EvidenceClaim(
            claim=(
                "The assisted primary label did not pass the declared audit gate "
                "and is excluded from headline claims."
            ),
            evidence_type=EvidenceType.INFERENCE,
            source_urls=["https://aclanthology.org/volumes/2026.acl-long/"],
            locator="classification audit registry",
        ),
    )

    write_release(
        replace(
            bundle,
            audits={"Foundation Models": weak_audit},
            theme_disclosures=(*bundle.theme_disclosures, disclosure),
        ),
        tmp_path / "experimental-theme",
    )

    overview = json.loads(
        (
            resolve_current_release(tmp_path / "experimental-theme") / "overview.json"
        ).read_text()
    )
    assert overview["audits"]["Foundation Models"]["observed_precision"] == "0.84"
    assert any(
        item["theme"] == "Foundation Models" and item["status"] == "experimental"
        for item in overview["theme_disclosures"]
    )


def test_release_requires_low_confidence_registry_and_theme_disclosure(
    tmp_path: Path,
) -> None:
    bundle = publishable_bundle()
    low_assignment = replace(bundle.assignments[0], confidence=Decimal("0.65"))
    low_paper_id = low_assignment.paper_id
    low_bundle = replace(
        bundle,
        assignments=(low_assignment, bundle.assignments[1]),
        low_confidence_ids=(low_paper_id,),
    )

    with pytest.raises(PublicationBlocked, match="low-confidence.*incomplete"):
        write_release(low_bundle, tmp_path / "missing-low-review")

    disclosure = ThemeDisclosure(
        theme="Foundation Models",
        status=ThemeDisclosureStatus.EXPERIMENTAL,
        reason=EvidenceClaim(
            claim="The low-confidence semantic review is incomplete.",
            evidence_type=EvidenceType.INFERENCE,
            source_urls=["https://aclanthology.org/volumes/2026.acl-long/"],
            locator="low-confidence decision registry",
        ),
    )
    write_release(
        replace(
            low_bundle,
            theme_disclosures=(*bundle.theme_disclosures, disclosure),
        ),
        tmp_path / "withheld-low-review",
    )
    overview = json.loads(
        (
            resolve_current_release(tmp_path / "withheld-low-review")
            / "overview.json"
        ).read_text()
    )
    assert overview["classification_review"] == {
        "confidence_threshold": "0.70",
        "low_confidence_ids": [low_paper_id],
        "pending_low_confidence_ids": [low_paper_id],
        "rejected_low_confidence_ids": [],
        "review_complete": False,
        "reviewed_low_confidence_ids": [],
    }


@pytest.mark.parametrize(
    "records",
    [
        (
            paper("paper-z").model_copy(update={"status": RecordStatus.UNRESOLVED}),
            paper("paper-a"),
        ),
        (paper("paper-a"), paper("paper-a")),
        (paper("paper-a"),),
    ],
    ids=["unresolved", "duplicate", "count-mismatch"],
)
def test_stale_clean_validation_cannot_publish_changed_records(
    tmp_path: Path, records: tuple[PaperRecord, ...]
) -> None:
    bundle = publishable_bundle()

    with pytest.raises(PublicationBlocked, match="stale validation"):
        write_release(replace(bundle, records=records), tmp_path / "release")

    assert not (tmp_path / "release").exists()


def test_stale_clean_validation_cannot_authorize_different_clean_record_ids(
    tmp_path: Path,
) -> None:
    bundle = publishable_bundle()
    changed_records = (paper("paper-b"), paper("paper-c"))

    with pytest.raises(PublicationBlocked, match="stale validation"):
        write_release(
            replace(
                bundle,
                records=changed_records,
                assignments=tuple(
                    assignment(record.paper_id) for record in changed_records
                ),
            ),
            tmp_path / "release",
        )

    assert not (tmp_path / "release").exists()


def test_nonempty_release_requires_complete_assignments_and_theme_audits(
    tmp_path: Path,
) -> None:
    bundle = publishable_bundle()

    with pytest.raises(PublicationBlocked, match="missing assignments"):
        write_release(
            replace(bundle, assignments=(), audits={}),
            tmp_path / "no-assignments",
        )

    with pytest.raises(PublicationBlocked, match="missing theme audits"):
        write_release(replace(bundle, audits={}), tmp_path / "no-audits")


def test_successful_release_is_fresh_and_does_not_follow_old_symlinks(
    tmp_path: Path,
) -> None:
    output = tmp_path / "release"
    write_release(publishable_bundle(), output)
    stale = output / "obsolete.txt"
    stale.write_text("old", encoding="utf-8")
    external = tmp_path / "external.txt"
    external.write_text("external must survive", encoding="utf-8")
    stale_link = output / "obsolete-link"
    stale_link.symlink_to(external)

    write_release(publishable_bundle(), output)

    current = resolve_current_release(output)
    assert sorted(path.name for path in current.iterdir()) == [
        "overview.json",
        "overview.md",
        "papers.csv",
        "papers.json",
        "provenance.json",
        "validation.json",
    ]
    assert sorted(path.name for path in output.iterdir()) == [
        "current.json",
        "generations",
    ]
    assert not stale.exists()
    assert not os.path.lexists(stale_link)
    assert external.read_text(encoding="utf-8") == "external must survive"


def test_failed_pointer_swap_keeps_previous_generation_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "release"
    bundle = publishable_bundle()
    write_release(bundle, output)
    old_pointer = (output / "current.json").read_bytes()
    old_generation = resolve_current_release(output)
    changed_claim = bundle.claims[0].model_copy(update={"claim": "Changed synthesis."})

    def fail_pointer_swap(_output: Path, _pointer: bytes) -> None:
        raise RuntimeError("injected pointer failure")

    monkeypatch.setattr(reports, "_replace_current_pointer", fail_pointer_swap)
    with pytest.raises(RuntimeError, match="injected"):
        write_release(replace(bundle, claims=(changed_claim,)), output)

    assert (output / "current.json").read_bytes() == old_pointer
    assert resolve_current_release(output) == old_generation


def test_failed_prepublication_cleanup_keeps_previous_generation_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "release"
    bundle = publishable_bundle()
    write_release(bundle, output)
    old_pointer = (output / "current.json").read_bytes()
    old_generation = resolve_current_release(output)
    changed_claim = bundle.claims[0].model_copy(update={"claim": "Changed synthesis."})

    def fail_cleanup(_output: Path) -> None:
        raise RuntimeError("injected cleanup failure")

    monkeypatch.setattr(reports, "_remove_legacy_entries", fail_cleanup)
    with pytest.raises(RuntimeError, match="injected"):
        write_release(replace(bundle, claims=(changed_claim,)), output)

    assert (output / "current.json").read_bytes() == old_pointer
    assert resolve_current_release(output) == old_generation


def test_current_release_resolver_rejects_artifact_hash_mismatch(
    tmp_path: Path,
) -> None:
    output = tmp_path / "release"
    write_release(publishable_bundle(), output)
    generation = resolve_current_release(output)
    (generation / "overview.md").write_text("corrupted", encoding="utf-8")

    with pytest.raises(ArtifactValidationError, match="hash"):
        resolve_current_release(output)


def test_symlink_release_root_is_rejected_without_touching_target(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external"
    external.mkdir()
    sentinel = external / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    output = tmp_path / "release"
    output.symlink_to(external, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        write_release(publishable_bundle(), output)

    assert output.is_symlink()
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert sorted(path.name for path in external.iterdir()) == ["sentinel.txt"]


@pytest.mark.parametrize(
    "claim",
    [
        EvidenceClaim(
            claim="The measured improvement is 12%.",
            evidence_type=EvidenceType.INFERENCE,
            source_urls=["https://aclanthology.org/paper.pdf"],
        ),
        EvidenceClaim(
            claim="The paper reports a qualitative improvement.",
            evidence_type=EvidenceType.PAPER_REPORTED,
            source_urls=["https://aclanthology.org/paper.pdf"],
        ),
    ],
    ids=["numeric", "paper-reported"],
)
def test_claims_requiring_locators_block_publication(
    tmp_path: Path, claim: EvidenceClaim
) -> None:
    with pytest.raises(PublicationBlocked, match="locator"):
        write_release(
            replace(publishable_bundle(), claims=(claim,)), tmp_path / "release"
        )


@pytest.mark.parametrize("numeric_token", ["1e6", "1E-6", "-2.3e+4"])
def test_scientific_notation_claims_require_locators(
    tmp_path: Path, numeric_token: str
) -> None:
    claim = EvidenceClaim(
        claim=f"The inferred scale is {numeric_token} parameters.",
        evidence_type=EvidenceType.INFERENCE,
        source_urls=["https://aclanthology.org/paper.pdf"],
    )

    with pytest.raises(PublicationBlocked, match="locator"):
        write_release(
            replace(publishable_bundle(), claims=(claim,)),
            tmp_path / "release",
        )


def test_alphanumeric_identifier_is_not_misread_as_scientific_notation(
    tmp_path: Path,
) -> None:
    claim = EvidenceClaim(
        claim="We compare model1e6x variants without a quantitative claim.",
        evidence_type=EvidenceType.INFERENCE,
        source_urls=["https://aclanthology.org/paper.pdf"],
    )

    write_release(replace(publishable_bundle(), claims=(claim,)), tmp_path / "release")

    assert resolve_current_release(tmp_path / "release").is_dir()


@pytest.mark.parametrize(
    ("sha256", "retrieved_at"),
    [("abc123", datetime(2026, 8, 24, tzinfo=UTC)), ("a" * 64, None)],
    ids=["invalid-hash", "missing-time"],
)
def test_incomplete_provenance_blocks_publication(
    tmp_path: Path,
    sha256: str,
    retrieved_at: datetime | None,
) -> None:
    bundle = publishable_bundle()
    records = tuple(
        record.model_copy(
            update={
                "source": record.source.model_copy(
                    update={"sha256": sha256, "retrieved_at": retrieved_at}
                )
            }
        )
        for record in bundle.records
    )

    with pytest.raises(PublicationBlocked, match="provenance"):
        write_release(
            replace(
                bundle,
                records=records,
                validation=validate_records(records, [], expected_included=2),
            ),
            tmp_path / "release",
        )


def test_non_finite_decimal_is_rejected_before_serialization(tmp_path: Path) -> None:
    bundle = publishable_bundle()
    invalid_assignment = replace(bundle.assignments[0], confidence=Decimal("NaN"))

    with pytest.raises(ArtifactValidationError, match="non-finite Decimal"):
        write_release(
            replace(bundle, assignments=(invalid_assignment, bundle.assignments[1])),
            tmp_path / "release",
        )

    assert not (tmp_path / "release").exists()
