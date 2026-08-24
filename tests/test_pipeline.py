import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import yaml

import conference_overview.pipeline as pipeline_module
from conference_overview.pipeline import (
    UnsupportedPipelineRoute,
    analyze_acl_scope,
    assisted_classify_scope,
    build_site_scope,
    collect_acl_scope,
    export_classification_scope,
    load_scope_records,
    parse_award_inventory_scope,
    rebuild_acl_scope_from_snapshots,
    validate_acl_scope,
)
from conference_overview.registry import normalize_request
from conference_overview.reports import resolve_current_release

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "acl"
BIB = (FIXTURE_DIR / "2026-long-sample.bib").read_bytes()
HTML = b"""<!doctype html>
<a href=/2026.acl-long.0/>Proceedings front matter</a>
<div class=\"d-sm-flex align-items-stretch mb-3\">
  <div class=\"d-block me-2 list-button-row\">
    <span title=\"Outstanding Paper\" aria-label=\"Outstanding Paper\"><i></i></span>
  </div>
  <span class=d-block><strong><a href=/2026.acl-long.1/>Tool-Using Agents for NLP</a></strong></span>
</div>
<div class=\"card bg-light collapse abstract-collapse\" id=abstract-2026--acl-long--1>
  <div class=\"card-body p-3 small\">This paper studies tool-using agents.</div>
</div>
<div class=\"d-sm-flex align-items-stretch mb-3\">
  <span class=d-block><strong><a href=/2026.acl-long.2/>A Title Collision</a></strong></span>
</div>
<div class=\"card bg-light collapse abstract-collapse\" id=abstract-2026--acl-long--2>
  <div class=\"card-body p-3 small\">We introduce a benchmark for evaluation.</div>
</div>
"""


def official_client() -> httpx.Client:
    request = normalize_request("ACL", 2026, "long")

    def handler(incoming: httpx.Request) -> httpx.Response:
        payload = BIB if str(incoming.url) == str(request.bibtex_url) else HTML
        return httpx.Response(
            200,
            content=payload,
            headers={"content-length": str(len(payload))},
            request=incoming,
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def official_client_with_bib(bib: bytes) -> httpx.Client:
    request = normalize_request("ACL", 2026, "long")

    def handler(incoming: httpx.Request) -> httpx.Response:
        payload = bib if str(incoming.url) == str(request.bibtex_url) else HTML
        return httpx.Response(
            200,
            content=payload,
            headers={"content-length": str(len(payload))},
            request=incoming,
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def collected_scope(root: Path) -> None:
    with official_client() as client:
        collect_acl_scope(normalize_request("ACL", 2026, "long"), root, client=client)


def test_collect_persists_both_immutable_sources_and_reconciled_records(
    tmp_path: Path,
) -> None:
    request = normalize_request("ACL", 2026, "long")

    with official_client() as client:
        result = collect_acl_scope(request, tmp_path, client=client)

    manifest_path = tmp_path / "data/manifests/acl/2026-long.json"
    normalized_path = tmp_path / "data/normalized/acl/2026-long.jsonl"
    manifest = json.loads(manifest_path.read_text())
    rows = [json.loads(line) for line in normalized_path.read_text().splitlines()]

    assert result.validation.publishable is True
    assert manifest["counts"] == {
        "discovered": 3,
        "duplicate_candidates": 0,
        "excluded": 1,
        "included": 2,
        "unresolved": 0,
    }
    assert [row["status"] for row in rows] == ["excluded", "complete", "complete"]
    assert (
        manifest["normalized"]["sha256"]
        == hashlib.sha256(normalized_path.read_bytes()).hexdigest()
    )
    assert {source["kind"] for source in manifest["sources"]} == {"bibtex", "html"}
    for source in manifest["sources"]:
        snapshot = tmp_path / source["snapshot_path"]
        assert snapshot.read_bytes() in {BIB, HTML}
        assert source["byte_size"] == len(snapshot.read_bytes())
        assert source["sha256"] == hashlib.sha256(snapshot.read_bytes()).hexdigest()


def test_collect_rejects_a_shorter_complete_bib_even_with_matching_content_length(
    tmp_path: Path,
) -> None:
    shorter_complete_bib = BIB.split(b"@inproceedings{lee-2026-title", maxsplit=1)[0]
    request = normalize_request("ACL", 2026, "long")

    with (
        official_client_with_bib(shorter_complete_bib) as client,
        pytest.raises(ValueError, match="incomplete|mismatch|HTML|IDs"),
    ):
        collect_acl_scope(request, tmp_path, client=client)


def test_rebuild_uses_existing_immutable_snapshots_without_fetching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = normalize_request("ACL", 2026, "long")
    collected_scope(tmp_path)
    snapshot_manifests = set(
        (tmp_path / "data/snapshots/acl/2026-long/manifests").iterdir()
    )

    def unexpected_fetch(*_args, **_kwargs):
        raise AssertionError("snapshot rebuild must not fetch")

    monkeypatch.setattr(pipeline_module, "fetch_bytes", unexpected_fetch)
    result = rebuild_acl_scope_from_snapshots(request, tmp_path)

    assert result.validation.included_count == 2
    assert snapshot_manifests == set(
        (tmp_path / "data/snapshots/acl/2026-long/manifests").iterdir()
    )


def test_validate_export_and_assisted_classification_preserve_every_id(
    tmp_path: Path,
) -> None:
    request = normalize_request("ACL", 2026, "long")
    collected_scope(tmp_path)

    report = validate_acl_scope(request, tmp_path)
    batch_paths = export_classification_scope(request, tmp_path, batch_size=1)
    assignments = assisted_classify_scope(request, tmp_path)
    included, excluded, _sources = load_scope_records(request, tmp_path)

    assert report.included_count == 2
    assert len(batch_paths) == 2
    assert [json.loads(path.read_text())["batch_index"] for path in batch_paths] == [
        1,
        2,
    ]
    assert {assignment.paper_id for assignment in assignments} == {
        record.paper_id for record in included
    }
    assert {assignment.primary_topic for assignment in assignments} == {
        "Evaluation",
        "Reasoning and Agents",
    }
    assert len(excluded) == 1
    assignment_path = tmp_path / "data/classification/acl/2026-long/assignments.jsonl"
    assert len(assignment_path.read_text().splitlines()) == 2
    manifest = json.loads(
        (tmp_path / "data/classification/acl/2026-long/classification-manifest.json").read_text()
    )
    assert manifest["assignments_sha256"] == hashlib.sha256(
        assignment_path.read_bytes()
    ).hexdigest()
    assert manifest["reviewed_low_confidence_ids"] == []
    assert manifest["low_confidence_review_state"] == "pending_semantic_review"
    queue_path = (
        tmp_path
        / "data/classification/acl/2026-long/low-confidence-review-queue.json"
    )
    queue = json.loads(queue_path.read_text())
    assert [item["paper_id"] for item in queue["papers"]] == [
        "acl:2026.acl-long.2"
    ]
    assert manifest["low_confidence_review_queue_sha256"] == hashlib.sha256(
        queue_path.read_bytes()
    ).hexdigest()
    low_confidence_decisions = json.loads(
        (
            tmp_path
            / "data/classification/acl/2026-long/low-confidence-decisions.json"
        ).read_text()
    )
    assert low_confidence_decisions["reviews"] == []
    decisions = json.loads(
        (tmp_path / "data/classification/acl/2026-long/audit-decisions.json").read_text()
    )
    assert decisions["themes"] == {
        "Evaluation": [],
        "Reasoning and Agents": [],
    }
    assert decisions["status"] == "pending_semantic_review"


def _semantic_partitions(root: Path, assignments: list[dict[str, object]]) -> list[Path]:
    paths: list[Path] = []
    for partition in range(8):
        path = root / f"acl2026-reclass-mod{partition}.jsonl"
        rows = [
            assignment
            for assignment in assignments
            if int(str(assignment["paper_id"]).rsplit(".", maxsplit=1)[-1]) % 8
            == partition
        ]
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )
        paths.append(path)
    return paths


def test_import_semantic_assignments_merges_exact_partitions_and_resets_reviews(
    tmp_path: Path,
) -> None:
    request = normalize_request("ACL", 2026, "long")
    collected_scope(tmp_path)
    assisted_classify_scope(request, tmp_path)
    classification = tmp_path / "data/classification/acl/2026-long"
    (classification / "audit-decisions.json").write_text(
        json.dumps({"status": "completed", "themes": {"Evaluation": [True]}}),
        encoding="utf-8",
    )
    (classification / "low-confidence-decisions.json").write_text(
        json.dumps({"status": "complete", "reviews": [{"paper_id": "stale"}]}),
        encoding="utf-8",
    )
    semantic_rows = [
        {
            "paper_id": "acl:2026.acl-long.1",
            "primary_topic": "Reasoning and Agents",
            "secondary_topics": ["Evaluation"],
            "confidence": 0.96,
            "rationale": "Agent semantic review identifies tool use as the main contribution.",
            "taxonomy_version": "2026-08-24-v1",
        },
        {
            "paper_id": "acl:2026.acl-long.2",
            "primary_topic": "Evaluation",
            "secondary_topics": [],
            "confidence": 0.62,
            "rationale": "Agent semantic review identifies evaluation as the primary contribution.",
            "taxonomy_version": "2026-08-24-v1",
        },
    ]
    parts = _semantic_partitions(tmp_path, semantic_rows)

    assert hasattr(pipeline_module, "import_semantic_assignments_scope")
    imported = pipeline_module.import_semantic_assignments_scope(
        request, tmp_path, parts
    )

    assert [assignment.paper_id for assignment in imported] == [
        "acl:2026.acl-long.1",
        "acl:2026.acl-long.2",
    ]
    assignment_rows = [
        json.loads(line)
        for line in (classification / "assignments.jsonl").read_text().splitlines()
    ]
    assert assignment_rows == [
        {**row, "confidence": str(row["confidence"])} for row in semantic_rows
    ]
    manifest = json.loads((classification / "classification-manifest.json").read_text())
    assert manifest["classifier"] == "agent-semantic-batch-review-v1"
    assert manifest["semantic_labeling"]["method"] == "explicit_agent_semantic_labeling"
    assert [source["partition"] for source in manifest["semantic_labeling"]["source_batches"]] == list(range(8))
    assert [source["paper_count"] for source in manifest["semantic_labeling"]["source_batches"]] == [0, 1, 1, 0, 0, 0, 0, 0]
    assert [source["sha256"] for source in manifest["semantic_labeling"]["source_batches"]] == [
        hashlib.sha256(path.read_bytes()).hexdigest() for path in parts
    ]
    audit_decisions = json.loads((classification / "audit-decisions.json").read_text())
    low_decisions = json.loads((classification / "low-confidence-decisions.json").read_text())
    assert audit_decisions["status"] == "pending_semantic_review"
    assert audit_decisions["themes"] == {
        "Evaluation": [],
        "Reasoning and Agents": [],
    }
    assert low_decisions["status"] == "pending_semantic_review"
    assert low_decisions["reviews"] == []

    summary = analyze_acl_scope(request, tmp_path)
    analyzed_manifest = json.loads(
        (classification / "classification-manifest.json").read_text()
    )
    assert analyzed_manifest["classifier"] == "agent-semantic-batch-review-v1"
    assert analyzed_manifest["semantic_labeling"] == manifest["semantic_labeling"]
    assert summary["classification"]["classifier"] == "agent-semantic-batch-review-v1"
    assert "explicit agent semantic assignments" in (
        tmp_path / "notes/acl-2026-long-overview.md"
    ).read_text()


def test_import_semantic_assignments_rejects_incomplete_normalized_membership(
    tmp_path: Path,
) -> None:
    request = normalize_request("ACL", 2026, "long")
    collected_scope(tmp_path)
    parts = _semantic_partitions(
        tmp_path,
        [{
            "paper_id": "acl:2026.acl-long.1",
            "primary_topic": "Reasoning and Agents",
            "secondary_topics": [],
            "confidence": 0.96,
            "rationale": "Agent semantic review identifies agent tool use.",
            "taxonomy_version": "2026-08-24-v1",
        }],
    )

    assert hasattr(pipeline_module, "import_semantic_assignments_scope")
    with pytest.raises(ValueError, match="missing paper IDs.*2026.acl-long.2"):
        pipeline_module.import_semantic_assignments_scope(request, tmp_path, parts)


def _audit_document(theme: str, decision: dict[str, object]) -> dict[str, object]:
    return {
        "method": "independent title-and-abstract semantic review",
        "schema_version": "classification-audit-v1",
        "status": "completed_semantic_review_fragment",
        "taxonomy_version": "2026-08-24-v1",
        "themes": {theme: [decision]},
    }


def test_import_full_theme_reviews_is_base_guarded_and_preserves_keep_assignments(
    tmp_path: Path,
) -> None:
    request = normalize_request("ACL", 2026, "long")
    collected_scope(tmp_path)
    parts = _semantic_partitions(
        tmp_path,
        [
            {
                "paper_id": "acl:2026.acl-long.1",
                "primary_topic": "Applications",
                "secondary_topics": [],
                "confidence": 0.91,
                "rationale": "Original application rationale.",
                "taxonomy_version": "2026-08-24-v1",
            },
                {
                    "paper_id": "acl:2026.acl-long.2",
                    "primary_topic": "Reasoning and Agents",
                    "secondary_topics": [],
                    "confidence": 0.68,
                    "rationale": "Original keep rationale.",
                "taxonomy_version": "2026-08-24-v1",
            },
        ],
    )
    pipeline_module.import_semantic_assignments_scope(request, tmp_path, parts)
    classification = tmp_path / "data/classification/acl/2026-long"
    base_sha256 = hashlib.sha256(
        (classification / "assignments.jsonl").read_bytes()
    ).hexdigest()
    application = tmp_path / "applications.json"
    application.write_text(
        json.dumps([{
            "paper_id": "acl:2026.acl-long.1",
            "old_primary_topic": "Applications",
            "decision": "change",
            "corrected_primary_topic": "Evaluation",
            "confidence": 0.98,
            "rationale": "Reviewed as an evaluation contribution.",
        }]),
        encoding="utf-8",
    )
    reasoning = tmp_path / "reasoning.json"
    reasoning.write_text(
        json.dumps({
            "schema_version": "full-theme-review-v1",
            "taxonomy_version": "2026-08-24-v1",
            "source_assignments_sha256": base_sha256,
            "source_primary_topic": "Reasoning and Agents",
            "reviews": [
                {
                    "paper_id": "acl:2026.acl-long.2",
                    "old_primary_topic": "Reasoning and Agents",
                    "decision": "keep",
                    "corrected_primary_topic": "Reasoning and Agents",
                    "confidence": 0.99,
                    "rationale": "A new review rationale that must not erase the original.",
                },
            ],
        }),
        encoding="utf-8",
    )
    duplicate = tmp_path / "duplicate-applications.json"
    duplicate.write_bytes(application.read_bytes())

    assert hasattr(pipeline_module, "import_full_theme_reviews_scope")
    with pytest.raises(ValueError, match="duplicate full-theme review paper ID"):
        pipeline_module.import_full_theme_reviews_scope(
            request, tmp_path, [application, duplicate, reasoning]
        )

    assignments = pipeline_module.import_full_theme_reviews_scope(
        request, tmp_path, [application, reasoning]
    )
    by_id = {assignment.paper_id: assignment for assignment in assignments}
    assert by_id["acl:2026.acl-long.1"].primary_topic == "Evaluation"
    assert by_id["acl:2026.acl-long.1"].confidence == Decimal("0.98")
    assert "Original application rationale." in by_id["acl:2026.acl-long.1"].rationale
    assert by_id["acl:2026.acl-long.2"].confidence == Decimal("0.68")
    assert by_id["acl:2026.acl-long.2"].rationale == "Original keep rationale."

    manifest = json.loads((classification / "classification-manifest.json").read_text())
    ledger = manifest["full_theme_reviews"]
    assert ledger["base_assignments_sha256"] == base_sha256
    assert ledger["reviewed_count"] == 2
    assert ledger["correction_count"] == 1
    assert ledger["keep_count"] == 1
    assert ledger["movement_matrix"] == {
        "Applications": {"Evaluation": 1},
        "Reasoning and Agents": {"Reasoning and Agents": 1},
    }
    assert {item["source_file"] for item in ledger["sources"]} == {
        "applications.json",
        "reasoning.json",
    }
    assert json.loads((classification / "audit-decisions.json").read_text())[
        "themes"
    ] == {
        "Evaluation": [],
        "Reasoning and Agents": [],
    }
    low_queue = json.loads(
        (classification / "low-confidence-review-queue.json").read_text()
    )
    assert [item["paper_id"] for item in low_queue["papers"]] == [
        "acl:2026.acl-long.2"
    ]
    assert json.loads(
        (classification / "low-confidence-decisions.json").read_text()
    )["reviews"] == []


def test_apply_audit_corrections_guards_old_topics_and_resets_audits(
    tmp_path: Path,
) -> None:
    request = normalize_request("ACL", 2026, "long")
    collected_scope(tmp_path)
    parts = _semantic_partitions(
        tmp_path,
        [
            {
                "paper_id": "acl:2026.acl-long.1",
                "primary_topic": "Reasoning and Agents",
                "secondary_topics": ["Evaluation"],
                "confidence": 0.96,
                "rationale": "Explicit semantic assignment for tool use.",
                "taxonomy_version": "2026-08-24-v1",
            },
            {
                "paper_id": "acl:2026.acl-long.2",
                "primary_topic": "Evaluation",
                "secondary_topics": [],
                "confidence": 0.62,
                "rationale": "Explicit low-confidence semantic assignment.",
                "taxonomy_version": "2026-08-24-v1",
            },
        ],
    )
    pipeline_module.import_semantic_assignments_scope(request, tmp_path, parts)
    classification = tmp_path / "data/classification/acl/2026-long"
    audit_a = tmp_path / "fresh-audit-a.json"
    audit_b = tmp_path / "fresh-audit-b.json"
    audit_a.write_text(
        json.dumps(
            _audit_document(
                "Reasoning and Agents",
                {
                    "paper_id": "acl:2026.acl-long.1",
                    "correct": False,
                    "corrected_primary_topic": "Evaluation",
                    "review_note": "The paper is centrally an evaluation study.",
                },
            )
        ),
        encoding="utf-8",
    )
    audit_b.write_text(
        json.dumps(
            _audit_document(
                "Evaluation",
                {
                    "paper_id": "acl:2026.acl-long.2",
                    "correct": True,
                    "review_note": "The original primary assignment remains supported.",
                },
            )
        ),
        encoding="utf-8",
    )
    queue_path = classification / "low-confidence-review-queue.json"
    low_review = tmp_path / "low-review.json"
    low_review.write_text(
        json.dumps(
            {
                "queue_sha256": hashlib.sha256(queue_path.read_bytes()).hexdigest(),
                "reviews": [{
                    "paper_id": "acl:2026.acl-long.2",
                    "decision": "accept",
                    "review_note": "Accepted after explicit independent review.",
                }],
                "schema_version": "low-confidence-review-decisions-v1",
                "status": "completed_semantic_review",
                "taxonomy_version": "2026-08-24-v1",
            }
        ),
        encoding="utf-8",
    )

    assert hasattr(pipeline_module, "apply_audit_corrections_scope")
    corrected = pipeline_module.apply_audit_corrections_scope(
        request, tmp_path, [audit_a, audit_b], low_review
    )

    by_id = {assignment.paper_id: assignment for assignment in corrected}
    assert by_id["acl:2026.acl-long.1"].primary_topic == "Evaluation"
    assert by_id["acl:2026.acl-long.1"].secondary_topics == ()
    assert by_id["acl:2026.acl-long.1"].confidence == Decimal("0.99")
    assert by_id["acl:2026.acl-long.1"].rationale.startswith(
        "independent audit correction:"
    )
    assert by_id["acl:2026.acl-long.2"].confidence == Decimal("0.62")
    manifest = json.loads((classification / "classification-manifest.json").read_text())
    assert manifest["audit_corrections"]["correction_count"] == 1
    assert manifest["audit_corrections"]["reviewed_count"] == 2
    assert manifest["audit_corrections"]["corrections"][0] == {
        "corrected_primary_topic": "Evaluation",
        "original_primary_topic": "Reasoning and Agents",
        "paper_id": "acl:2026.acl-long.1",
        "source_file": "fresh-audit-a.json",
    }
    assert [source["sha256"] for source in manifest["audit_corrections"]["sources"]] == [
        hashlib.sha256(path.read_bytes()).hexdigest() for path in (audit_a, audit_b)
    ]
    audit_decisions = json.loads((classification / "audit-decisions.json").read_text())
    low_decisions = json.loads((classification / "low-confidence-decisions.json").read_text())
    assert audit_decisions["themes"] == {"Evaluation": []}
    assert low_decisions["reviews"][0]["paper_id"] == "acl:2026.acl-long.2"
    assert low_decisions["queue_sha256"] == hashlib.sha256(
        queue_path.read_bytes()
    ).hexdigest()
    assert manifest["reviewed_low_confidence_ids"] == ["acl:2026.acl-long.2"]


def _minimal_deep_read(paper_id: str) -> dict[str, object]:
    pdf_url = f"https://aclanthology.org/{paper_id.removeprefix('acl:')}.pdf"
    reported = {
        "claim": "The paper reports a bounded contribution.",
        "evidence_type": "paper_reported",
        "source_urls": [pdf_url],
        "locator": "Section 1, PDF p. 1",
    }
    return {
        "paper_id": paper_id,
        "research_problem": reported,
        "contribution": reported,
        "method_summary": reported,
        "result_claims": [{
            **reported,
            "metric": "accuracy",
            "value": "1",
            "evaluation_setting": "bounded fixture",
        }],
        "why_it_matters": [reported],
        "limitations": [reported],
        "data_training_setup": [reported],
        "prior_work_differences": [reported],
        "reproducibility_assessment": [reported],
        "transferable_implications": [{
            **reported,
            "claim": "The disclosed design may transfer to another bounded setting.",
            "evidence_type": "inference",
        }],
        "method_diagram": {
            "nodes": [{
                "identifier": "input",
                "label": "Input",
                "paper_section": "Section 1",
            }],
            "edges": [],
        },
    }


def test_import_award_deep_reads_applies_guarded_patches_and_binds_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = normalize_request("ACL", 2026, "long")
    collected_scope(tmp_path)
    parse_award_inventory_scope(request, tmp_path)
    deep_source = tmp_path / "deep-reads.yaml"
    deep_source.write_text(
        yaml.safe_dump({"deep_reads": [_minimal_deep_read("acl:2026.acl-long.1")]}),
        encoding="utf-8",
    )
    patch_source = tmp_path / "corrections.yaml"
    patch_source.write_text(
        yaml.safe_dump(
            {
                "patches": [{
                    "paper_id": "acl:2026.acl-long.1",
                    "operation": "replace",
                    "path": "method_summary.claim",
                    "old": "The paper reports a bounded contribution.",
                    "new": "The corrected paper-grounded method summary.",
                }]
            }
        ),
        encoding="utf-8",
    )
    note_source = tmp_path / "notes.md"
    official_pdf = b"%PDF-1.7\nverified official fixture bytes\n%%EOF\n"
    official_sha256 = hashlib.sha256(official_pdf).hexdigest()
    note_source.write_text(
        "| Paper | SHA-256 | Bytes | PDF pages |\n"
        "|---|---|---:|---:|\n"
        f"| 2026.acl-long.1 | `{official_sha256}` | {len(official_pdf)} | 3 |\n",
        encoding="utf-8",
    )
    review_source = tmp_path / "review.md"
    review_source.write_text("# Independent evidence QA\n\nPASS after correction.\n")
    monkeypatch.setattr(pipeline_module, "fetch_bytes", lambda _url, _client: official_pdf)

    assert hasattr(pipeline_module, "import_award_deep_reads_scope")
    deep_reads = pipeline_module.import_award_deep_reads_scope(
        request,
        tmp_path,
        [deep_source],
        [patch_source],
        [note_source],
        [review_source],
    )

    assert len(deep_reads) == 1
    assert deep_reads[0].method_summary.claim == "The corrected paper-grounded method summary."
    output = yaml.safe_load(
        (tmp_path / "data/awards/acl/2026-long-deep-reads.yaml").read_text()
    )
    assert output["deep_reads"][0]["paper_id"] == "acl:2026.acl-long.1"
    provenance = json.loads(
        (tmp_path / "data/awards/acl/2026-long-deep-read-provenance.json").read_text()
    )
    assert provenance["deep_read_count"] == 1
    assert provenance["patch_count"] == 1
    assert provenance["pdfs"] == [{
        "byte_size": len(official_pdf),
        "pages": 3,
        "paper_id": "acl:2026.acl-long.1",
        "sha256": official_sha256,
        "source_url": "https://aclanthology.org/2026.acl-long.1.pdf",
        "verification_method": "downloaded_official_pdf_bytes",
    }]
    assert {source["source_file"] for source in provenance["sources"]} == {
        "deep-reads.yaml",
        "corrections.yaml",
        "notes.md",
        "review.md",
    }

    provenance.pop("pdf_verification")
    (tmp_path / "data/awards/acl/2026-long-deep-read-provenance.json").write_text(
        json.dumps(provenance), encoding="utf-8"
    )
    export_classification_scope(request, tmp_path, batch_size=1)
    assisted_classify_scope(request, tmp_path)
    with pytest.raises(ValueError, match="verified official PDF provenance"):
        analyze_acl_scope(request, tmp_path)

    note_source.write_text(
        "| Paper | SHA-256 | Bytes | PDF pages |\n"
        "|---|---|---:|---:|\n"
        f"| 2026.acl-long.1 | `{'a' * 64}` | 1,234 | 3 |\n",
        encoding="utf-8",
    )
    with pytest.raises(
        ValueError, match="claimed PDF provenance does not match verified official bytes"
    ):
        pipeline_module.import_award_deep_reads_scope(
            request,
            tmp_path,
            [deep_source],
            [patch_source],
            [note_source],
            [review_source],
        )


@pytest.mark.parametrize(
    ("decision", "rejected_count"), [("accept", 0), ("reject", 1)]
)
def test_low_confidence_registry_accepts_an_unsampled_review_decision(
    tmp_path: Path, decision: str, rejected_count: int
) -> None:
    request = normalize_request("ACL", 2026, "long")
    collected_scope(tmp_path)
    assisted_classify_scope(request, tmp_path)
    classification = tmp_path / "data/classification/acl/2026-long"
    samples_path = classification / "audit-samples.json"
    samples = json.loads(samples_path.read_text())
    samples["themes"]["Evaluation"] = []
    samples_path.write_text(json.dumps(samples))
    queue_path = classification / "low-confidence-review-queue.json"
    decisions_path = classification / "low-confidence-decisions.json"
    decisions = json.loads(decisions_path.read_text())
    decisions["reviews"] = [
        {
            "decision": decision,
            "paper_id": "acl:2026.acl-long.2",
            "review_note": "Explicit title-and-abstract semantic review.",
        }
    ]
    decisions["queue_sha256"] = hashlib.sha256(queue_path.read_bytes()).hexdigest()
    decisions_path.write_text(json.dumps(decisions))

    summary = analyze_acl_scope(request, tmp_path)
    manifest = json.loads((classification / "classification-manifest.json").read_text())

    assert summary["audit"]["candidate_counts"]["Evaluation"] == 0
    assert summary["audit"]["low_confidence_review"]["reviewed_count"] == 1
    assert summary["audit"]["low_confidence_review"]["pending_count"] == 0
    assert summary["audit"]["low_confidence_review"]["rejected_count"] == rejected_count
    assert manifest["reviewed_low_confidence_ids"] == ["acl:2026.acl-long.2"]


def test_award_inventory_is_bound_to_exact_official_volume_badge(
    tmp_path: Path,
) -> None:
    request = normalize_request("ACL", 2026, "long")
    collected_scope(tmp_path)

    inventory = parse_award_inventory_scope(request, tmp_path)
    payload = yaml.safe_load((tmp_path / "data/awards/acl/2026-long.yaml").read_text())

    assert inventory == payload["awards"]
    assert inventory == [
        {
            "acl_paper_id": "2026.acl-long.1",
            "award_type": "Outstanding Paper",
            "evidence_locator": (
                "volume HTML paper row 2026.acl-long.1; "
                "span[title='Outstanding Paper'][aria-label='Outstanding Paper']"
            ),
            "evidence_url": "https://aclanthology.org/volumes/2026.acl-long/",
            "landing_url": "https://aclanthology.org/2026.acl-long.1/",
            "paper_id": "acl:2026.acl-long.1",
            "pdf_url": "https://aclanthology.org/2026.acl-long.1.pdf",
            "title": "Tool-Using Agents for NLP",
        }
    ]


def test_acl_pipeline_never_accepts_an_unsupported_route(tmp_path: Path) -> None:
    unsupported = normalize_request("NEURIPS", 2025, None)

    with pytest.raises(UnsupportedPipelineRoute, match="unsupported"):
        collect_acl_scope(unsupported, tmp_path, client=official_client())


def test_preliminary_release_keeps_unaudited_themes_explicitly_experimental(
    tmp_path: Path,
) -> None:
    request = normalize_request("ACL", 2026, "long")
    collected_scope(tmp_path)
    export_classification_scope(request, tmp_path, batch_size=1)
    assisted_classify_scope(request, tmp_path)
    parse_award_inventory_scope(request, tmp_path)

    summary = analyze_acl_scope(request, tmp_path, write_release=True)
    release = resolve_current_release(tmp_path / "data/releases/ACL/2026")
    overview = json.loads((release / "overview.json").read_text())
    provenance = json.loads((release / "provenance.json").read_text())

    assert summary["language"] == "distribution_or_hotspot_not_trend"
    assert summary["audit"]["candidate_counts"] == {
        "Evaluation": 1,
        "Reasoning and Agents": 1,
    }
    assert summary["audit"]["pending_counts"] == {
        "Evaluation": 1,
        "Reasoning and Agents": 1,
    }
    assert len(overview["assignments"]) == 2
    assert set(overview["audits"]) == {"Evaluation", "Reasoning and Agents"}
    assert all(audit["sample_size"] == 0 for audit in overview["audits"].values())
    assert {item["theme"] for item in overview["theme_disclosures"]} == {
        "Evaluation",
        "Reasoning and Agents",
    }
    assert overview["awards"][0]["status"] == "verified"
    assert overview["award_deep_reads"] == []
    assert datetime.fromisoformat(
        overview["build_metadata"]["generated_at"]
    ) > max(
        datetime.fromisoformat(source["retrieved_at"])
        for source in provenance["sources"]
    )
    assert all(
        advance["advance_id"].startswith("preliminary-examples-")
        for advance in overview["advances"]
    )
    assert all(
        "no semantic representativeness or lane-purity claim" in advance["claims"][0]["claim"]
        for advance in overview["advances"]
    )
    assert sorted(path.name for path in release.iterdir()) == [
        "overview.json",
        "overview.md",
        "papers.csv",
        "papers.json",
        "provenance.json",
        "validation.json",
    ]
    note = (tmp_path / "notes/acl-2026-long-overview.md").read_text()
    assert "one-year distribution" in note
    assert "not a trend" in note
    assert "Audit candidates | Reviewed" in note
    assert "preliminary example" in note
    assert "representative" not in note


def test_build_site_resolves_relative_release_root_before_changing_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = tmp_path / "site"
    route = site / "dist/conferences/acl/2026/index.html"
    route.parent.mkdir(parents=True)
    route.write_text("built")
    release = tmp_path / "data/releases/ACL/2026"
    release.mkdir(parents=True)
    captured: dict[str, object] = {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pipeline_module, "resolve_current_release", lambda path: path)

    def fake_run(command, *, cwd, env, **kwargs):
        captured.update({"command": command, "cwd": cwd, "env": env})
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(pipeline_module.subprocess, "run", fake_run)

    assert build_site_scope(Path(".")) == site.resolve() / "dist"
    assert captured["cwd"] == site.resolve()
    assert captured["env"]["CONFERENCE_RELEASE_ROOT"] == str(
        (tmp_path / "data/releases").resolve()
    )
