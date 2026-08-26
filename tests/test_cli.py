import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import conference_overview.cli as cli_module
from conference_overview.cli import app
from conference_overview.validate import PublicationBlocked

runner = CliRunner()


def payload(result: object) -> dict[str, object]:
    return json.loads(result.stdout.strip())  # type: ignore[attr-defined]


def test_cli_exposes_all_pipeline_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in (
        "collect",
        "validate",
        "export-classification",
        "import-classification",
        "import-low-confidence-review",
        "import-audit-decisions",
        "export-chinese-content",
        "check-chinese-content-sources",
        "import-chinese-content",
        "build-chinese-content",
        "analyze",
        "awards",
        "build-site",
    ):
        assert command in result.stdout


def test_import_classification_accepts_icml_sources(tmp_path: Path, monkeypatch) -> None:
    first = tmp_path / "review-a.jsonl"
    second = tmp_path / "review-b.jsonl"

    def fake_import(request, root, inputs):
        assert (request.venue, request.year, request.track) == ("ICML", 2025, "main")
        assert root == tmp_path
        assert inputs == [first, second]
        return [SimpleNamespace(), SimpleNamespace()]

    monkeypatch.setattr(cli_module, "import_semantic_assignments_scope", fake_import)
    result = runner.invoke(
        app,
        [
            "import-classification",
            "--venues",
            "ICML",
            "--years",
            "2025",
            "--tracks",
            "main",
            "--input",
            str(first),
            "--input",
            str(second),
            "--root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert payload(result) == {
        "command": "import-classification",
        "paper_count": 2,
        "source_count": 2,
        "status": "imported",
    }


def test_classification_review_import_commands_report_completion(
    tmp_path: Path, monkeypatch
) -> None:
    classification = tmp_path / "data/classification/icml/2025-main"
    classification.mkdir(parents=True)
    assignment_bytes = b'{"paper_id":"pmlr:v267:test25a"}\n'
    (classification / "assignments.jsonl").write_bytes(assignment_bytes)
    source = tmp_path / "review.json"
    source.write_text("{}", encoding="utf-8")

    def fake_low(request, root, input_path):
        assert (request.venue, request.year, request.track) == ("ICML", 2025, "main")
        assert (root, input_path) == (tmp_path, source)
        return SimpleNamespace(
            pending_ids=(), rejected_ids=(), reviewed_ids=("pmlr:v267:test25a",)
        )

    def fake_audit(request, root, input_path):
        assert (request.venue, request.year, request.track) == ("ICML", 2025, "main")
        assert (root, input_path) == (tmp_path, source)
        return {"Evaluation": SimpleNamespace()}

    monkeypatch.setattr(
        cli_module, "import_low_confidence_decisions_scope", fake_low
    )
    monkeypatch.setattr(cli_module, "import_audit_decisions_scope", fake_audit)
    common = [
        "--venue",
        "ICML",
        "--year",
        "2025",
        "--track",
        "main",
        "--input",
        str(source),
        "--root",
        str(tmp_path),
    ]

    low = runner.invoke(app, ["import-low-confidence-review", *common])
    audit = runner.invoke(app, ["import-audit-decisions", *common])

    expected_sha = hashlib.sha256(assignment_bytes).hexdigest()
    assert low.exit_code == 0
    assert payload(low) == {
        "assignments_sha256": expected_sha,
        "command": "import-low-confidence-review",
        "pending_count": 0,
        "rejected_count": 0,
        "review_complete": True,
        "reviewed_count": 1,
        "status": "imported",
    }
    assert audit.exit_code == 0
    assert payload(audit) == {
        "assignments_sha256": expected_sha,
        "command": "import-audit-decisions",
        "review_complete": True,
        "status": "imported",
        "theme_count": 1,
    }


def test_export_chinese_content_routes_to_scope_orchestration(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_export(request, root, *, shard_count):
        assert request.source_key == "2026.acl-long"
        assert root == tmp_path
        assert shard_count == 16
        return [tmp_path / f"source-{index}.jsonl" for index in range(17)]

    monkeypatch.setattr(cli_module, "export_chinese_content_scope", fake_export)
    result = runner.invoke(
        app,
        [
            "export-chinese-content",
            "--venue",
            "ACL",
            "--year",
            "2026",
            "--track",
            "long",
            "--root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert payload(result) == {
        "command": "export-chinese-content",
        "source_count": 17,
        "status": "exported",
    }


def test_unsupported_collect_returns_structured_non_success() -> None:
    result = runner.invoke(
        app,
        ["collect", "--venues", "NEURIPS", "--years", "2025"],
    )

    assert result.exit_code == 2
    assert payload(result)["command"] == "collect"
    assert payload(result)["status"] == "unsupported"
    assert "unsupported" in str(payload(result)["message"])


def test_acl_collect_routes_to_real_orchestration(tmp_path: Path, monkeypatch) -> None:
    def fake_collect(request, root):
        assert request.source_key == "2026.acl-long"
        assert root == tmp_path
        return SimpleNamespace(
            manifest_path=tmp_path / "data/manifests/acl/2026-long.json",
            normalized_path=tmp_path / "data/normalized/acl/2026-long.jsonl",
            validation=SimpleNamespace(
                discovered_count=3,
                excluded_count=1,
                included_count=2,
            ),
        )

    monkeypatch.setattr(cli_module, "collect_scope", fake_collect)
    result = runner.invoke(
        app,
        [
            "collect",
            "--venues",
            "ACL",
            "--years",
            "2026",
            "--tracks",
            "long",
            "--root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert payload(result) == {
        "command": "collect",
        "discovered_count": 3,
        "excluded_count": 1,
        "included_count": 2,
        "manifest": "data/manifests/acl/2026-long.json",
        "normalized": "data/normalized/acl/2026-long.jsonl",
        "status": "collected",
    }


def test_icml_collect_routes_to_generic_orchestration(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_collect(request, root):
        assert (request.venue, request.year, request.track) == ("ICML", 2026, "main")
        assert root == tmp_path
        return SimpleNamespace(
            manifest_path=tmp_path / "data/manifests/icml/2026-main.json",
            normalized_path=tmp_path / "data/normalized/icml/2026-main.jsonl",
            validation=SimpleNamespace(
                discovered_count=5,
                excluded_count=2,
                included_count=3,
            ),
        )

    monkeypatch.setattr(cli_module, "collect_scope", fake_collect)
    result = runner.invoke(
        app,
        [
            "collect",
            "--venues",
            "ICML",
            "--years",
            "2026",
            "--tracks",
            "main",
            "--root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert payload(result)["included_count"] == 3


def test_reconcile_final_reports_not_published_without_writing(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_reconcile(request, root):
        assert (request.venue, request.year, request.track) == ("ICML", 2026, "main")
        assert root == tmp_path
        return {"status": "not_published"}

    monkeypatch.setattr(cli_module, "reconcile_final_scope", fake_reconcile)
    result = runner.invoke(
        app,
        [
            "reconcile-final", "--venues", "ICML", "--years", "2026",
            "--tracks", "main", "--root", str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert payload(result) == {
        "command": "reconcile-final",
        "status": "not_published",
        "venue": "ICML",
        "year": 2026,
        "track": "main",
    }
    assert list(tmp_path.rglob("*")) == []


def test_acl_awards_infers_the_only_configured_track(tmp_path: Path, monkeypatch) -> None:
    def fake_awards(request, root):
        assert request.track == "long"
        assert request.source_key == "2026.acl-long"
        assert root == tmp_path
        return [{} for _ in range(30)]

    monkeypatch.setattr(cli_module, "parse_award_inventory_scope", fake_awards)
    result = runner.invoke(
        app,
        [
            "awards",
            "--venue",
            "ACL",
            "--year",
            "2026",
            "--root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert payload(result)["award_count"] == 30


def test_acl_awards_rejects_an_explicit_unconfigured_track() -> None:
    result = runner.invoke(
        app,
        ["awards", "--venue", "ACL", "--year", "2026", "--track", "short"],
    )

    assert result.exit_code == 2
    assert payload(result)["status"] == "unsupported"


def test_invalid_input_returns_structured_exit_two() -> None:
    result = runner.invoke(
        app,
        ["analyze", "--venues", "ACL", "--years", "not-a-year", "--tracks", "long"],
    )

    assert result.exit_code == 2
    assert payload(result)["command"] == "analyze"
    assert payload(result)["status"] == "invalid_input"
    assert "years" in str(payload(result)["message"])


def test_blocked_release_returns_structured_exit_three(
    tmp_path: Path, monkeypatch
) -> None:
    def blocked(*_args, **_kwargs):
        raise PublicationBlocked("release validation blocks publication")

    monkeypatch.setattr(cli_module, "build_site_scope", blocked)
    result = runner.invoke(
        app,
        ["build-site", "--root", str(tmp_path)],
    )

    assert result.exit_code == 3
    assert payload(result)["command"] == "build-site"
    assert payload(result)["status"] == "publication_blocked"


def test_invalid_release_document_returns_structured_exit_two(
    tmp_path: Path, monkeypatch
) -> None:
    def invalid(*_args, **_kwargs):
        raise ValueError("invalid release current pointer")

    monkeypatch.setattr(cli_module, "build_site_scope", invalid)
    result = runner.invoke(app, ["build-site", "--root", str(tmp_path)])

    assert result.exit_code == 2
    assert payload(result)["status"] == "invalid_input"


def test_malformed_utf8_release_document_returns_structured_exit_two(
    tmp_path: Path, monkeypatch
) -> None:
    def invalid(*_args, **_kwargs):
        raise UnicodeError("invalid UTF-8 release document")

    monkeypatch.setattr(cli_module, "build_site_scope", invalid)
    result = runner.invoke(app, ["build-site", "--root", str(tmp_path)])

    assert result.exit_code == 2
    assert payload(result)["status"] == "invalid_input"
