import hashlib
import json
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
    validate_acl_scope,
)
from conference_overview.registry import normalize_request
from conference_overview.reports import resolve_current_release

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "acl"
BIB = (FIXTURE_DIR / "2026-long-sample.bib").read_bytes()
HTML = b"""<!doctype html>
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
    decisions = json.loads(
        (tmp_path / "data/classification/acl/2026-long/audit-decisions.json").read_text()
    )
    assert decisions["themes"] == {
        "Evaluation": [],
        "Reasoning and Agents": [],
    }
    assert decisions["status"] == "pending_semantic_review"


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
