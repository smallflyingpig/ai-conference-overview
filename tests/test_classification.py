import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from conference_overview.classification import (
    Assignment,
    PublicationBlocked,
    assert_theme_publishable,
    audit_theme,
    export_batches,
    load_assignments,
    validate_assignment,
)
from conference_overview.models import PaperRecord, RecordStatus, SourceRef


def taxonomy() -> dict[str, object]:
    return {
        "version": "2026-08-24-v1",
        "topics": [
            {"id": "foundation_models", "name": "Foundation Models", "definition": "Models."},
            {"id": "evaluation", "name": "Evaluation", "definition": "Assessment."},
        ],
    }


def record(paper_id: str = "acl:2026.acl-long.1") -> PaperRecord:
    return PaperRecord(
        paper_id=paper_id,
        title="A Paper",
        normalized_title="a paper",
        authors=["A. Author"],
        venue="ACL",
        year=2026,
        track="long",
        landing_url="https://aclanthology.org/2026.acl-long.1/",
        source=SourceRef(
            name="ACL Anthology",
            url="https://aclanthology.org/volumes/2026.acl-long/",
            retrieved_at=datetime(2026, 8, 24, tzinfo=UTC),
        ),
        status=RecordStatus.COMPLETE,
        abstract="An abstract.",
        keywords=["taxonomy"],
        subject_areas=["Language Generation"],
        native_metadata={"session": "oral"},
    )


def assignment(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "paper_id": "acl:2026.acl-long.1",
        "primary_topic": "Foundation Models",
        "secondary_topics": ["Evaluation"],
        "confidence": "0.75",
        "rationale": "The abstract describes model pretraining.",
        "taxonomy_version": "2026-08-24-v1",
    }
    value.update(overrides)
    return value


def write_assignments(path: Path, *values: dict[str, object]) -> None:
    path.write_text("".join(json.dumps(value) + "\n" for value in values))


def test_export_batches_includes_reproducible_context_and_sorts_papers() -> None:
    batches = export_batches([record("paper-z"), record("paper-a")], taxonomy(), size=1)

    assert [batch["papers"][0]["paper_id"] for batch in batches] == ["paper-a", "paper-z"]
    assert batches[0]["taxonomy"] == taxonomy()
    assert batches[0]["papers"][0]["abstract"] == "An abstract."
    assert batches[0]["papers"][0]["venue_native_metadata"] == {
        "venue": "ACL",
        "year": 2026,
        "track": "long",
        "keywords": ["taxonomy"],
        "subject_areas": ["Language Generation"],
        "native_metadata": {"session": "oral"},
    }
    assert "official_metadata" in batches[0]["evidence_label_instructions"]


def test_assignment_rejects_unknown_topic() -> None:
    with pytest.raises(ValueError, match="unknown topic"):
        validate_assignment(assignment(primary_topic="Unknown"), taxonomy())


def test_assignment_rejects_duplicate_or_primary_secondary_topics() -> None:
    with pytest.raises(ValueError, match="duplicate secondary topic"):
        validate_assignment(assignment(secondary_topics=["Evaluation", "Evaluation"]), taxonomy())

    with pytest.raises(ValueError, match="primary topic cannot be repeated"):
        validate_assignment(assignment(secondary_topics=["Foundation Models"]), taxonomy())


@pytest.mark.parametrize("confidence", ["-0.01", "1.01"])
def test_assignment_rejects_confidence_outside_closed_unit_interval(confidence: str) -> None:
    with pytest.raises(ValueError, match="confidence"):
        validate_assignment(assignment(confidence=confidence), taxonomy())


def test_load_assignments_rejects_missing_and_duplicate_paper_ids(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.jsonl"
    write_assignments(missing_path, assignment(paper_id=""))

    with pytest.raises(ValueError, match="missing paper_id"):
        load_assignments(missing_path, taxonomy())

    duplicate_path = tmp_path / "duplicate.jsonl"
    write_assignments(duplicate_path, assignment(), assignment())

    with pytest.raises(ValueError, match="duplicate paper_id"):
        load_assignments(duplicate_path, taxonomy())


def test_load_assignments_rejects_taxonomy_version_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "assignments.jsonl"
    write_assignments(path, assignment(taxonomy_version="2025-01-01-v1"))

    with pytest.raises(ValueError, match="taxonomy version"):
        load_assignments(path, taxonomy())


def test_load_assignments_retains_low_confidence_assignment_for_review(tmp_path: Path) -> None:
    path = tmp_path / "assignments.jsonl"
    write_assignments(path, assignment(confidence="0.01"))

    loaded = load_assignments(path, taxonomy())

    assert loaded == [
        Assignment(
            paper_id="acl:2026.acl-long.1",
            primary_topic="Foundation Models",
            secondary_topics=("Evaluation",),
            confidence=Decimal("0.01"),
            rationale="The abstract describes model pretraining.",
            taxonomy_version="2026-08-24-v1",
        )
    ]


def test_theme_gate_requires_precision_and_lower_bound() -> None:
    audit = audit_theme([True] * 46 + [False] * 4)

    assert audit.observed_precision == Decimal("0.92")
    assert audit.wilson_lower_95 >= Decimal("0.80")
    assert_theme_publishable(audit)


def test_theme_gate_rejects_low_precision_empty_samples_and_weak_wilson_bound() -> None:
    with pytest.raises(PublicationBlocked, match="observed precision"):
        assert_theme_publishable(audit_theme([True] * 89 + [False] * 11))

    with pytest.raises(PublicationBlocked, match="Wilson"):
        assert_theme_publishable(audit_theme([True] * 45 + [False] * 5))

    with pytest.raises(PublicationBlocked, match="empty"):
        assert_theme_publishable(audit_theme([]))
