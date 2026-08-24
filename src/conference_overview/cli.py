"""Structured command-line boundary for the conference pipeline."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from conference_overview.registry import normalize_request

app = typer.Typer(
    help="Collect, validate, analyze, and publish conference overview artifacts.",
    no_args_is_help=True,
)


def _exit(command: str, status: str, message: str, code: int, **details: object) -> NoReturn:
    payload: dict[str, object] = {
        "command": command,
        "message": message,
        "status": status,
    }
    payload.update(details)
    typer.echo(json.dumps(payload, sort_keys=True))
    raise typer.Exit(code=code)


def _parse_years(value: str) -> list[int]:
    years: list[int] = []
    for part in value.split(","):
        normalized = part.strip()
        try:
            if ":" in normalized:
                start_text, end_text = normalized.split(":", maxsplit=1)
                start = int(start_text)
                end = int(end_text)
                if end < start:
                    raise ValueError
                years.extend(range(start, end + 1))
            else:
                years.append(int(normalized))
        except ValueError as exc:
            raise ValueError("years must be comma-separated years or inclusive ranges") from exc
    if not years:
        raise ValueError("years must not be empty")
    return years


def _values(value: str, *, name: str) -> list[str]:
    values = [item.strip() for item in value.split(",") if item.strip()]
    if not values:
        raise ValueError(f"{name} must not be empty")
    return values


def _validate_venue_request(
    *, command: str, venues: str, years: str, tracks: str | None
) -> None:
    try:
        venue_values = _values(venues, name="venues")
        year_values = _parse_years(years)
        track_values: list[str | None] = (
            _values(tracks, name="tracks") if tracks is not None else [None]
        )
        for venue in venue_values:
            for year in year_values:
                for track in track_values:
                    request = normalize_request(venue, year, track)
                    if request.source_key is None:
                        raise ValueError(
                            "unsupported venue/year/track: "
                            f"{request.venue}/{request.year}/{request.track or '-'}"
                        )
    except ValueError as exc:
        _exit(command, "invalid_input", str(exc), 2)


def _unsupported_pipeline_command(
    command: str, venues: str, years: str, tracks: str | None, message: str
) -> NoReturn:
    _validate_venue_request(
        command=command,
        venues=venues,
        years=years,
        tracks=tracks,
    )
    _exit(command, "unsupported", message, 2)


@app.command()
def collect(
    venues: str = typer.Option(..., "--venues"),
    years: str = typer.Option(..., "--years"),
    tracks: str | None = typer.Option(None, "--tracks"),
) -> None:
    """Collect immutable official-source snapshots (or report unsupported)."""
    _unsupported_pipeline_command(
        "collect",
        venues,
        years,
        tracks,
        "live collection orchestration is not implemented",
    )


@app.command("validate")
def validate_command(
    venues: str = typer.Option(..., "--venues"),
    years: str = typer.Option(..., "--years"),
    tracks: str | None = typer.Option(None, "--tracks"),
    audit: bool = typer.Option(False, "--audit"),
) -> None:
    """Validate normalized records and optional audits."""
    del audit
    _unsupported_pipeline_command(
        "validate", venues, years, tracks, "validation orchestration is not implemented"
    )


@app.command("export-classification")
def export_classification(
    venues: str = typer.Option(..., "--venues"),
    years: str = typer.Option(..., "--years"),
    tracks: str | None = typer.Option(None, "--tracks"),
    batch_size: int = typer.Option(40, "--batch-size", min=1),
) -> None:
    """Export deterministic semantic-classification batches."""
    del batch_size
    _unsupported_pipeline_command(
        "export-classification",
        venues,
        years,
        tracks,
        "classification export orchestration is not implemented",
    )


@app.command()
def analyze(
    venues: str = typer.Option(..., "--venues"),
    years: str = typer.Option(..., "--years"),
    tracks: str | None = typer.Option(None, "--tracks"),
    write_release: bool = typer.Option(False, "--write-release"),
) -> None:
    """Analyze validated inputs and optionally write a release."""
    del write_release
    _unsupported_pipeline_command(
        "analyze", venues, years, tracks, "analysis orchestration is not implemented"
    )


@app.command()
def awards(
    venue: str = typer.Option(..., "--venue"),
    year: str = typer.Option(..., "--year"),
    track: str | None = typer.Option(None, "--track"),
) -> None:
    """Validate official award evidence and deep reads."""
    _unsupported_pipeline_command(
        "awards", venue, year, track, "award orchestration is not implemented"
    )


def _load_validation(command: str, release_dir: Path) -> Mapping[str, object]:
    path = release_dir / "validation.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _exit(command, "invalid_input", f"invalid validation artifact: {exc}", 2)
    if not isinstance(payload, Mapping) or not isinstance(payload.get("publishable"), bool):
        _exit(
            command,
            "invalid_input",
            "validation artifact must contain a boolean publishable field",
            2,
        )
    return payload


@app.command("build-site")
def build_site(
    release_dir: Annotated[Path | None, typer.Option("--release-dir")] = None,
) -> None:
    """Check release publication state before the later site build integration."""
    if release_dir is None:
        _exit(
            "build-site",
            "unsupported",
            "site build orchestration is not implemented",
            2,
        )
    validation = _load_validation("build-site", release_dir)
    if validation["publishable"] is False:
        detail_keys = (
            "definite_duplicate_pairs",
            "duplicate_candidates",
            "status_mismatch_ids",
            "unresolved_record_ids",
        )
        _exit(
            "build-site",
            "publication_blocked",
            "release validation blocks publication",
            3,
            details={key: validation.get(key, []) for key in detail_keys},
        )
    _exit(
        "build-site",
        "unsupported",
        "site build orchestration is not implemented",
        2,
    )


if __name__ == "__main__":
    app()
