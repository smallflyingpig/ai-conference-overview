from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from conference_overview.adapters.pmlr import (
    FinalSourceStatus,
    PmlrReconciliationError,
    check_final_source,
    parse_pmlr_citeproc,
    parse_pmlr_volume,
    reconcile_pmlr_records,
)
from conference_overview.models import PaperRecord, RecordStatus, SourceRef
from conference_overview.registry import normalize_request


def record(paper_id: str, title: str, *, doi: str | None = None) -> PaperRecord:
    return PaperRecord(
        paper_id=paper_id,
        title=title,
        normalized_title=title.casefold(),
        authors=["A. Author"],
        venue="ICML",
        year=2026,
        track="main",
        landing_url=f"https://openreview.net/forum?id={paper_id}",
        source=SourceRef(
            name="official",
            url="https://icml.cc/virtual/2026/papers.html",
            retrieved_at=datetime(2026, 8, 26, tzinfo=UTC),
            sha256="a" * 64,
        ),
        status=RecordStatus.COMPLETE,
        abstract="Preliminary abstract.",
        doi=doi,
        pdf_url=f"https://openreview.net/pdf?id={paper_id}",
    )


def test_pmlr_404_is_not_published() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(404, request=request)
    )
    with httpx.Client(transport=transport) as client:
        status = check_final_source(normalize_request("ICML", 2026, "main"), client)

    assert status is FinalSourceStatus.NOT_PUBLISHED


def test_pmlr_diff_requires_exact_one_to_one_identity() -> None:
    preliminary = [record("forum-1", "Same Paper")]
    final = [
        record("pmlr:v306:one", "Same Paper", doi="10.5555/final").model_copy(
            update={
                "abstract": "Final abstract.",
                "pdf_url": "https://proceedings.mlr.press/v306/one.pdf",
            }
        )
    ]

    report = reconcile_pmlr_records(preliminary, final)

    assert report.preliminary_count == report.final_count == report.matched_count == 1
    assert report.only_preliminary_ids == ()
    assert report.only_final_ids == ()
    assert report.field_differences[0].fields == ("abstract", "doi", "pdf_url")


def test_pmlr_diff_rejects_ambiguous_title_fallback() -> None:
    preliminary = [record("forum-1", "Duplicate"), record("forum-2", "Duplicate")]
    final = [record("pmlr:v306:one", "Duplicate")]

    with pytest.raises(PmlrReconciliationError, match="ambiguous"):
        reconcile_pmlr_records(preliminary, final)


def test_parse_pmlr_volume_extracts_typed_final_record() -> None:
    source = record("source", "Source").source.model_copy(
        update={"url": "https://proceedings.mlr.press/v306/"}
    )
    data = (
        Path(__file__).parent / "fixtures/pmlr/icml-2026-small.html"
    ).read_bytes()

    records = parse_pmlr_volume(
        data, normalize_request("ICML", 2026, "main"), source
    )

    assert [item.paper_id for item in records] == ["pmlr:v306:example1"]
    assert records[0].doi == "10.5555/v306-example1"
    assert str(records[0].pdf_url) == (
        "https://proceedings.mlr.press/v306/example1/example1.pdf"
    )


def test_parse_pmlr_citeproc_preserves_final_paper_identity_and_abstract() -> None:
    data = (
        Path(__file__).parent / "fixtures/pmlr/icml-2025-citeproc-small.yaml"
    ).read_bytes()
    source = SourceRef(
        name="PMLR Volume 267 metadata",
        url="https://proceedings.mlr.press/v267/assets/bib/citeproc.yaml",
        retrieved_at=datetime(2026, 8, 26, tzinfo=UTC),
        sha256="b" * 64,
    )

    records = parse_pmlr_citeproc(
        data, normalize_request("ICML", 2025, "main"), source
    )

    assert [item.paper_id for item in records] == [
        "pmlr:v267:a-mancisidor25a",
        "pmlr:v267:aamand25a",
    ]
    assert records[0].authors == ["Rogelio A. Mancisidor", "Robert Jenssen"]
    assert records[0].abstract == (
        "CoDE aggregates dependent experts for multimodal variational autoencoders."
    )
    assert records[0].native_metadata == {
        "pmlr_id": "a-mancisidor25a",
        "pages": "1-26",
        "volume": "267",
    }
