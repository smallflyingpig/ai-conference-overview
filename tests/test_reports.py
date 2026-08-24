import csv
import json
import os
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from conference_overview import reports
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
    assert overview["metrics"]["emerging_score"]["components"] == {
        "novelty": "0.25",
        "share_growth": "0.8",
        "spread_growth": "0.5",
    }


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
        path.name: path.read_bytes() for path in resolve_current_release(first).iterdir()
    } == {
        path.name: path.read_bytes() for path in resolve_current_release(second).iterdir()
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
    assert sorted(path.name for path in output.iterdir()) == ["current.json", "generations"]
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


def test_current_release_resolver_rejects_artifact_hash_mismatch(tmp_path: Path) -> None:
    output = tmp_path / "release"
    write_release(publishable_bundle(), output)
    generation = resolve_current_release(output)
    (generation / "overview.md").write_text("corrupted", encoding="utf-8")

    with pytest.raises(ArtifactValidationError, match="hash"):
        resolve_current_release(output)


def test_symlink_release_root_is_rejected_without_touching_target(tmp_path: Path) -> None:
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
        write_release(replace(publishable_bundle(), claims=(claim,)), tmp_path / "release")


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
