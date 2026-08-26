import hashlib
import json
from pathlib import Path

import httpx
import pytest
import yaml

import conference_overview.pipeline as pipeline_module
from conference_overview import conference_pipeline
from conference_overview.conference_pipeline import (
    build_preliminary_release,
    collect_scope,
    rebuild_scope_from_snapshots,
    reconcile_final_scope,
    validate_scope,
)
from conference_overview.models import PaperRecord, VenueRequest
from conference_overview.pipeline import (
    export_classification_scope,
    import_semantic_assignments_scope,
)
from conference_overview.registry import normalize_request
from conference_overview.reports import resolve_current_release
from conference_overview.validate import PublicationBlocked, validate_records

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "icml"


def icml_client() -> httpx.Client:
    first = (FIXTURE_DIR / "events-page-1.json").read_bytes()
    second = (FIXTURE_DIR / "events-page-2.json").read_bytes()
    abstracts = (FIXTURE_DIR / "abstracts.json").read_bytes()
    openreview = (FIXTURE_DIR / "openreview-accepted.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("icml-2026-orals-posters.json"):
            return httpx.Response(200, content=first, request=request)
        if url == "https://icml.cc/api/miniconf/events?offset=2":
            return httpx.Response(200, content=second, request=request)
        if url.endswith("icml-2026-abstracts.json"):
            return httpx.Response(200, content=abstracts, request=request)
        if url.startswith("https://api2.openreview.net/notes?"):
            return httpx.Response(200, content=openreview, request=request)
        raise AssertionError(f"unexpected request: {url}")

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_collect_scope_preserves_acl_dispatch(tmp_path: Path, monkeypatch) -> None:
    expected = object()
    monkeypatch.setattr(
        conference_pipeline, "collect_acl_scope", lambda *_args, **_kwargs: expected
    )

    assert collect_scope(normalize_request("ACL", 2026, "long"), tmp_path) is expected


def test_collect_icml_persists_sources_and_reconciled_records(
    tmp_path: Path,
) -> None:
    request = normalize_request("ICML", 2026, "main")
    with icml_client() as client:
        result = collect_scope(request, tmp_path, client=client)
    manifest = json.loads(result.manifest_path.read_text())

    assert manifest["schema_version"] == "conference-collection-manifest-v1"
    assert manifest["scope"] == {"venue": "ICML", "year": 2026, "track": "main"}
    assert manifest["publication_status"] == "preliminary_official_program"
    assert manifest["counts"] == {
        "discovered": 5,
        "duplicate_candidates": 0,
        "excluded": 2,
        "included": 3,
        "unresolved": 0,
        "presentation_rows": 4,
    }
    assert all(
        Path(item["snapshot_path"]).is_relative_to(
            "data/snapshots/icml/2026-main"
        )
        for item in manifest["sources"]
    )


def test_rebuild_rejects_modified_snapshot_before_writing_normalized(
    tmp_path: Path,
) -> None:
    request = normalize_request("ICML", 2026, "main")
    with icml_client() as client:
        result = collect_scope(request, tmp_path, client=client)
    manifest = json.loads(result.manifest_path.read_text())
    snapshot = tmp_path / manifest["sources"][0]["snapshot_path"]
    snapshot.write_bytes(snapshot.read_bytes() + b"x")
    normalized_before = result.normalized_path.read_bytes()

    with pytest.raises(ValueError, match="snapshot"):
        rebuild_scope_from_snapshots(request, tmp_path)
    assert result.normalized_path.read_bytes() == normalized_before


def test_validate_rejects_manifest_count_mutation(tmp_path: Path) -> None:
    request = normalize_request("ICML", 2026, "main")
    with icml_client() as client:
        result = collect_scope(request, tmp_path, client=client)
    manifest = json.loads(result.manifest_path.read_text())
    manifest["counts"]["included"] = 4
    result.manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="count"):
        validate_scope(request, tmp_path)


def test_build_preliminary_release_selects_exact_six_generation(
    tmp_path: Path,
) -> None:
    request = normalize_request("ICML", 2026, "main")
    with icml_client() as client:
        collect_scope(request, tmp_path, client=client)

    summary = build_preliminary_release(request, tmp_path, write_release=True)
    generation = resolve_current_release(tmp_path / "data/releases/ICML/2026")

    assert sorted(path.name for path in generation.iterdir()) == [
        "overview.json",
        "overview.md",
        "papers.csv",
        "papers.json",
        "provenance.json",
        "validation.json",
    ]
    assert summary["publication_status"] == "preliminary_official_program"


def test_available_pmlr_writes_snapshot_and_diff_without_selecting_release(
    tmp_path: Path,
) -> None:
    request = normalize_request("ICML", 2026, "main")
    with icml_client() as client:
        collect_scope(request, tmp_path, client=client)
    html = (Path(__file__).parent / "fixtures/pmlr/icml-2026-small.html").read_bytes()
    transport = httpx.MockTransport(
        lambda incoming: httpx.Response(200, content=html, request=incoming)
    )

    with httpx.Client(transport=transport) as client:
        result = reconcile_final_scope(request, tmp_path, client=client)

    output = Path(result["output"])
    assert result["status"] == "available"
    assert output.parent.name == result["source_sha256"]
    assert output.name == "diff.json"
    assert json.loads(output.read_text())["matched_count"] == 1
    assert (output.parent / "source.html").read_bytes() == html
    assert not (tmp_path / "data/releases/ICML/2026/current.json").exists()


def test_icml_2025_collects_final_pmlr_records_and_builds_papers_only_release(
    tmp_path: Path,
) -> None:
    fixture_root = Path(__file__).parent / "fixtures/pmlr"
    volume = (fixture_root / "icml-2025-volume-small.html").read_bytes()
    metadata = (fixture_root / "icml-2025-citeproc-small.yaml").read_bytes()
    request = normalize_request("ICML", 2025, "main")

    def handler(incoming: httpx.Request) -> httpx.Response:
        if str(incoming.url) == str(request.source_urls["volume"]):
            return httpx.Response(200, content=volume, request=incoming)
        if str(incoming.url) == str(request.source_urls["metadata"]):
            return httpx.Response(200, content=metadata, request=incoming)
        raise AssertionError(f"unexpected request: {incoming.url}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = collect_scope(request, tmp_path, client=client)
    summary = build_preliminary_release(request, tmp_path, write_release=True)
    generation = resolve_current_release(tmp_path / "data/releases/ICML/2025")
    overview = json.loads((generation / "overview.json").read_text())
    note = (tmp_path / "notes/icml-2025-main-overview.md").read_text()

    assert result.validation.included_count == 2
    assert summary["publication_status"] == "final_proceedings"
    assert overview["publication_context"]["status"] == "final_proceedings"
    assert overview["publication_context"]["final_source_status"] == "available"
    assert overview["paper_count"] == 2
    assert "- 缺少 DOI：2" in note


def test_icml_2025_classification_export_uses_its_own_scope_paths(
    tmp_path: Path,
) -> None:
    fixture_root = Path(__file__).parent / "fixtures/pmlr"
    volume = (fixture_root / "icml-2025-volume-small.html").read_bytes()
    metadata = (fixture_root / "icml-2025-citeproc-small.yaml").read_bytes()
    request = normalize_request("ICML", 2025, "main")

    def handler(incoming: httpx.Request) -> httpx.Response:
        payload = (
            volume
            if str(incoming.url) == str(request.source_urls["volume"])
            else metadata
        )
        return httpx.Response(200, content=payload, request=incoming)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        collect_scope(request, tmp_path, client=client)

    batches = export_classification_scope(request, tmp_path, batch_size=1)

    assert batches == [
        tmp_path / "data/classification/icml/2025-main/batches/batch-0001.json",
        tmp_path / "data/classification/icml/2025-main/batches/batch-0002.json",
    ]


def _write_assignment_source(
    path: Path, paper_ids: tuple[str, ...], *, confidence: str = "0.96"
) -> Path:
    rows = [
        {
            "confidence": confidence,
            "paper_id": paper_id,
            "primary_topic": "Learning and Optimization",
            "rationale": "Semantic review identifies the learning method contribution.",
            "secondary_topics": [],
            "taxonomy_version": "2026-08-24-v1",
        }
        for paper_id in paper_ids
    ]
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    return path


def _collect_small_icml_2025(root: Path) -> VenueRequest:
    fixture_root = Path(__file__).parent / "fixtures/pmlr"
    payloads = {
        "volume": (fixture_root / "icml-2025-volume-small.html").read_bytes(),
        "metadata": (fixture_root / "icml-2025-citeproc-small.yaml").read_bytes(),
    }
    request = normalize_request("ICML", 2025, "main")

    def handler(incoming: httpx.Request) -> httpx.Response:
        kind = next(
            key
            for key, url in request.source_urls.items()
            if str(incoming.url) == str(url)
        )
        return httpx.Response(200, content=payloads[kind], request=incoming)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        collect_scope(request, root, client=client)
    return request


def test_import_semantic_assignments_accepts_exact_icml_membership_and_is_stable(
    tmp_path: Path,
) -> None:
    request = _collect_small_icml_2025(tmp_path)
    first = _write_assignment_source(
        tmp_path / "review-a.jsonl", ("pmlr:v267:a-mancisidor25a",)
    )
    second = _write_assignment_source(
        tmp_path / "review-b.jsonl", ("pmlr:v267:aamand25a",)
    )

    imported = import_semantic_assignments_scope(request, tmp_path, [second, first])
    classification = tmp_path / "data/classification/icml/2025-main"
    first_bytes = (classification / "assignments.jsonl").read_bytes()
    first_manifest = json.loads(
        (classification / "classification-manifest.json").read_text()
    )
    import_semantic_assignments_scope(request, tmp_path, [first, second])

    assert [item.paper_id for item in imported] == [
        "pmlr:v267:a-mancisidor25a",
        "pmlr:v267:aamand25a",
    ]
    assert (classification / "assignments.jsonl").read_bytes() == first_bytes
    second_manifest = json.loads(
        (classification / "classification-manifest.json").read_text()
    )
    assert second_manifest["semantic_labeling"] == first_manifest["semantic_labeling"]
    assert [
        source["source_file"]
        for source in first_manifest["semantic_labeling"]["source_batches"]
    ] == ["review-a.jsonl", "review-b.jsonl"]
    assert all(
        source["byte_size"] > 0
        for source in first_manifest["semantic_labeling"]["source_batches"]
    )


@pytest.mark.parametrize(
    "case", ["missing", "extra", "duplicate", "duplicate_source", "taxonomy"]
)
def test_import_semantic_assignments_rejects_invalid_icml_union_before_write(
    tmp_path: Path, case: str
) -> None:
    request = _collect_small_icml_2025(tmp_path)
    first_ids = ("pmlr:v267:a-mancisidor25a",)
    second_ids = ("pmlr:v267:aamand25a",)
    if case == "missing":
        second_ids = ()
    elif case == "extra":
        second_ids += ("pmlr:v267:not-in-volume25a",)
    elif case == "duplicate":
        second_ids = first_ids
    first = _write_assignment_source(tmp_path / "review-a.jsonl", first_ids)
    second = _write_assignment_source(tmp_path / "review-b.jsonl", second_ids)
    if case == "taxonomy":
        second.write_text(
            second.read_text().replace("2026-08-24-v1", "wrong-version"),
            encoding="utf-8",
        )

    inputs = [first, first] if case == "duplicate_source" else [first, second]
    with pytest.raises(ValueError):
        import_semantic_assignments_scope(request, tmp_path, inputs)

    assert not (
        tmp_path / "data/classification/icml/2025-main/assignments.jsonl"
    ).exists()


def _classified_small_icml_2025(root: Path) -> tuple[VenueRequest, Path]:
    request = _collect_small_icml_2025(root)
    first = _write_assignment_source(
        root / "review-a.jsonl",
        ("pmlr:v267:a-mancisidor25a",),
        confidence="0.62",
    )
    second = _write_assignment_source(
        root / "review-b.jsonl", ("pmlr:v267:aamand25a",)
    )
    import_semantic_assignments_scope(request, root, [first, second])
    return request, root / "data/classification/icml/2025-main"


def test_import_low_confidence_review_binds_exact_icml_queue(tmp_path: Path) -> None:
    request, classification = _classified_small_icml_2025(tmp_path)
    queue = classification / "low-confidence-review-queue.json"
    assignments = classification / "assignments.jsonl"
    source = tmp_path / "low-review.json"
    source.write_text(
        json.dumps(
            {
                "assignments_sha256": hashlib.sha256(
                    assignments.read_bytes()
                ).hexdigest(),
                "queue_sha256": hashlib.sha256(queue.read_bytes()).hexdigest(),
                "reviews": [
                    {
                        "decision": "accept",
                        "paper_id": "pmlr:v267:a-mancisidor25a",
                        "review_note": "The abstract directly supports the selected topic.",
                        "reviewed_primary_topic": "Learning and Optimization",
                    }
                ],
                "status": "completed_semantic_review",
                "taxonomy_version": "2026-08-24-v1",
            }
        ),
        encoding="utf-8",
    )

    status = pipeline_module.import_low_confidence_decisions_scope(
        request, tmp_path, source
    )

    assert status.accepted_ids == ("pmlr:v267:a-mancisidor25a",)
    assert status.pending_ids == ()


@pytest.mark.parametrize("mutation", ["stale_hash", "missing_id", "wrong_topic"])
def test_import_low_confidence_review_rejects_invalid_icml_input(
    tmp_path: Path, mutation: str
) -> None:
    request, classification = _classified_small_icml_2025(tmp_path)
    queue = classification / "low-confidence-review-queue.json"
    assignments = classification / "assignments.jsonl"
    payload = {
        "assignments_sha256": hashlib.sha256(assignments.read_bytes()).hexdigest(),
        "queue_sha256": hashlib.sha256(queue.read_bytes()).hexdigest(),
        "reviews": [
            {
                "decision": "accept",
                "paper_id": "pmlr:v267:a-mancisidor25a",
                "review_note": "The abstract directly supports the selected topic.",
                "reviewed_primary_topic": "Learning and Optimization",
            }
        ],
        "status": "completed_semantic_review",
        "taxonomy_version": "2026-08-24-v1",
    }
    if mutation == "stale_hash":
        payload["assignments_sha256"] = "0" * 64
    elif mutation == "missing_id":
        payload["reviews"] = []
    else:
        payload["reviews"][0]["reviewed_primary_topic"] = "Evaluation"  # type: ignore[index]
    source = tmp_path / "invalid-low-review.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    before = (classification / "low-confidence-decisions.json").read_bytes()

    with pytest.raises(ValueError):
        pipeline_module.import_low_confidence_decisions_scope(
            request, tmp_path, source
        )

    assert (classification / "low-confidence-decisions.json").read_bytes() == before


def _completed_icml_audit_payload(classification: Path) -> dict[str, object]:
    sample_path = classification / "audit-samples.json"
    samples = json.loads(sample_path.read_text())
    themes = {
        theme: [
            {
                **row,
                "correct": True,
                "review_note": "Independent title-and-abstract semantic review.",
            }
            for row in rows
        ]
        for theme, rows in samples["themes"].items()
    }
    return {
        "method": "independent complete title-and-abstract semantic review",
        "provenance": {
            "assignments_sha256": samples["assignments_sha256"],
            "audit_samples_sha256": hashlib.sha256(
                sample_path.read_bytes()
            ).hexdigest(),
        },
        "schema_version": "classification-audit-v1",
        "status": "completed_semantic_review",
        "taxonomy_version": "2026-08-24-v1",
        "themes": themes,
    }


def test_import_audit_decisions_binds_exact_icml_samples(tmp_path: Path) -> None:
    request, classification = _classified_small_icml_2025(tmp_path)
    payload = _completed_icml_audit_payload(classification)
    source = tmp_path / "audit-review.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    audits = pipeline_module.import_audit_decisions_scope(request, tmp_path, source)

    assert set(audits) == {"Learning and Optimization"}
    assert audits["Learning and Optimization"].correct_count == 2


@pytest.mark.parametrize(
    "mutation", ["subset", "extra_id", "changed_title", "wrong_topic", "stale_hash"]
)
def test_import_audit_decisions_rejects_non_authoritative_icml_samples(
    tmp_path: Path, mutation: str
) -> None:
    request, classification = _classified_small_icml_2025(tmp_path)
    payload = _completed_icml_audit_payload(classification)
    rows = payload["themes"]["Learning and Optimization"]  # type: ignore[index]
    if mutation == "subset":
        rows.pop()
    elif mutation == "extra_id":
        rows[0]["paper_id"] = "pmlr:v267:not-sampled25a"
    elif mutation == "changed_title":
        rows[0]["title"] = "Forged title"
    elif mutation == "wrong_topic":
        rows[0]["proposed_primary_topic"] = "Evaluation"
    else:
        payload["provenance"]["assignments_sha256"] = "0" * 64  # type: ignore[index]
    source = tmp_path / "invalid-audit.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    before = (classification / "audit-decisions.json").read_bytes()

    with pytest.raises(ValueError):
        pipeline_module.import_audit_decisions_scope(request, tmp_path, source)

    assert (classification / "audit-decisions.json").read_bytes() == before


def test_collect_icml_awards_reconciles_exact_pmlr_titles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    award_titles = {
        "train for the worst, plan for the best: understanding token ordering in masked diffusions",
        "roll the dice & look before you leap: going beyond the creative limits of next-token prediction",
        "the value of prediction in identifying the worst-off",
        "score matching with missing data",
        "conformal prediction as bayesian quadrature",
        "collabllm: from passive responders to active collaborators",
        "position: the ai conference peer review crisis demands author feedback and reviewer rewards",
        "position: ai safety should prioritize the future of work",
    }
    records = [
        PaperRecord.model_validate_json(line)
        for line in (
            Path(__file__).parents[1] / "data/normalized/icml/2025-main.jsonl"
        )
        .read_text()
        .splitlines()
        if json.loads(line)["normalized_title"] in award_titles
    ]
    assert len(records) == 8
    validation = validate_records(records, (), expected_included=8)
    monkeypatch.setattr(
        pipeline_module,
        "_validated_classification_records",
        lambda _request, _root: (validation, records),
    )
    html = (
        Path(__file__).parent / "fixtures/icml/icml-2025-awards-small.html"
    ).read_bytes()
    request = normalize_request("ICML", 2025, "main")
    transport = httpx.MockTransport(
        lambda incoming: httpx.Response(
            200,
            content=html,
            headers={"content-length": str(len(html))},
            request=incoming,
        )
    )

    with httpx.Client(transport=transport) as client:
        inventory = pipeline_module.collect_icml_award_inventory_scope(
            request, tmp_path, client=client
        )

    assert len(inventory) == 8
    assert {item["paper_id"] for item in inventory} == {
        record.paper_id for record in records
    }
    assert {item["award_type"] for item in inventory}.issuperset(
        {"Outstanding Paper", "Outstanding Position Paper"}
    )
    output = yaml.safe_load(
        (tmp_path / "data/awards/icml/2025-main.yaml").read_text()
    )
    assert output["scope"] == {"track": "main", "venue": "ICML", "year": 2025}
    assert output["status"] == "official_inventory_complete_deep_reads_pending"


def test_icml_analysis_does_not_replace_papers_only_release_when_reviews_pending(
    tmp_path: Path,
) -> None:
    request = _collect_small_icml_2025(tmp_path)
    build_preliminary_release(request, tmp_path, write_release=True)
    pointer = tmp_path / "data/releases/ICML/2025/current.json"
    before = pointer.read_bytes()
    first = _write_assignment_source(
        tmp_path / "review-a.jsonl", ("pmlr:v267:a-mancisidor25a",)
    )
    second = _write_assignment_source(
        tmp_path / "review-b.jsonl", ("pmlr:v267:aamand25a",)
    )
    import_semantic_assignments_scope(request, tmp_path, [first, second])

    with pytest.raises(PublicationBlocked, match="audit"):
        conference_pipeline.analyze_scope(
            request, tmp_path, write_release=True
        )

    assert pointer.read_bytes() == before
