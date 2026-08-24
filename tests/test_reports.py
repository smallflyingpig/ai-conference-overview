import csv
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from conference_overview.awards import AwardRecord, AwardStatus
from conference_overview.classification import Assignment, ThemeAudit, audit_theme
from conference_overview.metrics import CrossVenueSpread, emerging_score
from conference_overview.models import (
    EvidenceClaim,
    EvidenceType,
    PaperRecord,
    RecordStatus,
    SourceRef,
)
from conference_overview.reports import ReleaseBundle, write_release
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
            sha256="abc123",
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
        claims=(
            EvidenceClaim(
                claim="The papers form a source-backed distribution snapshot.",
                evidence_type=EvidenceType.CROSS_PAPER_SYNTHESIS,
                source_urls=["https://aclanthology.org/volumes/2026.acl-long/"],
                locator="ACL 2026 long-paper volume",
            ),
        ),
        taxonomy_version="2026-08-24-v1",
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

    provenance = json.loads((tmp_path / "provenance.json").read_text())
    validation = json.loads((tmp_path / "validation.json").read_text())
    overview = json.loads((tmp_path / "overview.json").read_text())

    assert provenance["source_sha256"] == "abc123"
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
    assert validation["unresolved_record_ids"] == []
    assert overview["audits"]["Foundation Models"]["sample_size"] == 50
    assert overview["audits"]["Foundation Models"]["thresholds"] == {
        "minimum_observed_precision": "0.90",
        "minimum_wilson_lower_95": "0.80",
    }
    assert overview["awards"][0]["status"] == "verified"
    assert overview["metrics"]["emerging_score"]["components"] == {
        "novelty": "0.25",
        "share_growth": "0.8",
        "spread_growth": "0.5",
    }


def test_release_orders_paper_outputs_and_derives_csv_from_the_same_payload(
    tmp_path: Path,
) -> None:
    write_release(publishable_bundle(), tmp_path)

    papers = json.loads((tmp_path / "papers.json").read_text())
    with (tmp_path / "papers.csv").open(newline="", encoding="utf-8") as csv_file:
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
        path.name: path.read_bytes() for path in first.iterdir()
    } == {path.name: path.read_bytes() for path in second.iterdir()}


def test_markdown_renders_only_typed_evidence_claims(tmp_path: Path) -> None:
    bundle = publishable_bundle()
    write_release(bundle, tmp_path / "valid")

    markdown = (tmp_path / "valid" / "overview.md").read_text()
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
