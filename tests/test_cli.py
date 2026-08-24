import json
from pathlib import Path

from typer.testing import CliRunner

from conference_overview.cli import app

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
        "analyze",
        "awards",
        "build-site",
    ):
        assert command in result.stdout


def test_incomplete_collect_returns_structured_non_success() -> None:
    result = runner.invoke(
        app,
        ["collect", "--venues", "ACL", "--years", "2026", "--tracks", "long"],
    )

    assert result.exit_code == 2
    assert payload(result) == {
        "command": "collect",
        "message": "live collection orchestration is not implemented",
        "status": "unsupported",
    }


def test_invalid_input_returns_structured_exit_two() -> None:
    result = runner.invoke(
        app,
        ["analyze", "--venues", "ACL", "--years", "not-a-year", "--tracks", "long"],
    )

    assert result.exit_code == 2
    assert payload(result)["command"] == "analyze"
    assert payload(result)["status"] == "invalid_input"
    assert "years" in str(payload(result)["message"])


def test_blocked_release_returns_structured_exit_three(tmp_path: Path) -> None:
    release = tmp_path / "blocked"
    release.mkdir()
    (release / "validation.json").write_text(
        json.dumps(
            {
                "publishable": False,
                "status_mismatch_ids": ["paper-1"],
                "unresolved_record_ids": [],
                "definite_duplicate_pairs": [],
                "duplicate_candidates": [],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["build-site", "--release-dir", str(release)])

    assert result.exit_code == 3
    assert payload(result) == {
        "command": "build-site",
        "details": {
            "definite_duplicate_pairs": [],
            "duplicate_candidates": [],
            "status_mismatch_ids": ["paper-1"],
            "unresolved_record_ids": [],
        },
        "message": "release validation blocks publication",
        "status": "publication_blocked",
    }


def test_invalid_release_document_returns_structured_exit_two(tmp_path: Path) -> None:
    release = tmp_path / "invalid"
    release.mkdir()
    (release / "validation.json").write_text("not json", encoding="utf-8")

    result = runner.invoke(app, ["build-site", "--release-dir", str(release)])

    assert result.exit_code == 2
    assert payload(result)["status"] == "invalid_input"


def test_malformed_utf8_release_document_returns_structured_exit_two(
    tmp_path: Path,
) -> None:
    release = tmp_path / "invalid-utf8"
    release.mkdir()
    (release / "validation.json").write_bytes(b"\xff\xfe")

    result = runner.invoke(app, ["build-site", "--release-dir", str(release)])

    assert result.exit_code == 2
    assert payload(result)["status"] == "invalid_input"
