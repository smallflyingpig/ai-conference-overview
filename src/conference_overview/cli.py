"""Structured command-line boundary for the conference pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from conference_overview.conference_pipeline import (
    analyze_scope,
    collect_scope,
    reconcile_final_scope,
    validate_scope,
)
from conference_overview.content_pipeline import (
    build_chinese_content_scope,
    check_chinese_content_sources_scope,
    export_chinese_content_scope,
    import_chinese_content_scope,
)
from conference_overview.pipeline import (
    UnsupportedPipelineRoute,
    analyze_acl_scope,
    build_site_scope,
    export_classification_scope,
    import_semantic_assignments_scope,
    parse_award_inventory_scope,
)
from conference_overview.registry import normalize_request
from conference_overview.validate import PublicationBlocked

app = typer.Typer(
    help="Collect, validate, analyze, and publish conference overview artifacts.",
    no_args_is_help=True,
)
_DEFAULT_ROOT = Path(".")


def _exit(
    command: str, status: str, message: str, code: int, **details: object
) -> NoReturn:
    payload: dict[str, object] = {
        "command": command,
        "message": message,
        "status": status,
    }
    payload.update(details)
    typer.echo(json.dumps(payload, sort_keys=True))
    raise typer.Exit(code=code)


def _success(command: str, status: str, **details: object) -> None:
    typer.echo(
        json.dumps({"command": command, "status": status, **details}, sort_keys=True)
    )


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
            raise ValueError(
                "years must be comma-separated years or inclusive ranges"
            ) from exc
    if not years:
        raise ValueError("years must not be empty")
    return years


def _values(value: str, *, name: str) -> list[str]:
    values = [item.strip() for item in value.split(",") if item.strip()]
    if not values:
        raise ValueError(f"{name} must not be empty")
    return values


def _request(*, command: str, venues: str, years: str, tracks: str | None):
    try:
        venue_values = _values(venues, name="venues")
        year_values = _parse_years(years)
        track_values = _values(tracks, name="tracks") if tracks is not None else [None]
    except ValueError as exc:
        _exit(command, "invalid_input", str(exc), 2)
    if len(venue_values) != 1 or len(year_values) != 1 or len(track_values) != 1:
        _exit(
            command,
            "invalid_input",
            "ACL reference orchestration requires exactly one venue, year, and track",
            2,
        )
    request = normalize_request(venue_values[0], year_values[0], track_values[0])
    if request.source_key is None:
        _exit(
            command,
            "unsupported",
            (
                "unsupported venue/year/track: "
                f"{request.venue}/{request.year}/{request.track or '-'}"
            ),
            2,
        )
    return request


def _run(command: str, operation):
    try:
        return operation()
    except UnsupportedPipelineRoute as exc:
        _exit(command, "unsupported", str(exc), 2)
    except PublicationBlocked as exc:
        _exit(command, "publication_blocked", str(exc), 3)
    except (OSError, TypeError, UnicodeError, ValueError, RuntimeError) as exc:
        _exit(command, "invalid_input", str(exc), 2)


@app.command()
def collect(
    venues: str = typer.Option(..., "--venues"),
    years: str = typer.Option(..., "--years"),
    tracks: str | None = typer.Option(None, "--tracks"),
    root: Annotated[Path, typer.Option("--root")] = _DEFAULT_ROOT,
) -> None:
    """Collect immutable official conference snapshots and normalized records."""
    request = _request(command="collect", venues=venues, years=years, tracks=tracks)
    result = _run("collect", lambda: collect_scope(request, root))
    _success(
        "collect",
        "collected",
        discovered_count=result.validation.discovered_count,
        excluded_count=result.validation.excluded_count,
        included_count=result.validation.included_count,
        manifest=result.manifest_path.relative_to(root).as_posix(),
        normalized=result.normalized_path.relative_to(root).as_posix(),
    )


@app.command("validate")
def validate_command(
    venues: str = typer.Option(..., "--venues"),
    years: str = typer.Option(..., "--years"),
    tracks: str | None = typer.Option(None, "--tracks"),
    audit: bool = typer.Option(False, "--audit"),
    root: Annotated[Path, typer.Option("--root")] = _DEFAULT_ROOT,
) -> None:
    """Recompute canonical reconciliation and optional audit state."""
    request = _request(command="validate", venues=venues, years=years, tracks=tracks)
    report = _run("validate", lambda: validate_scope(request, root))
    details: dict[str, object] = {
        "discovered_count": report.discovered_count,
        "excluded_count": report.excluded_count,
        "included_count": report.included_count,
        "publishable": report.publishable,
    }
    if audit:
        analysis = _run(
            "validate",
            lambda: analyze_acl_scope(request, root, write_release=False),
        )
        details["audit"] = analysis["audit"]
        details["withheld_themes"] = analysis["withheld_themes"]
    _success("validate", "validated", **details)


@app.command("export-classification")
def export_classification(
    venues: str = typer.Option(..., "--venues"),
    years: str = typer.Option(..., "--years"),
    tracks: str | None = typer.Option(None, "--tracks"),
    batch_size: int = typer.Option(40, "--batch-size", min=1),
    root: Annotated[Path, typer.Option("--root")] = _DEFAULT_ROOT,
) -> None:
    """Export deterministic title-and-abstract classification batches."""
    request = _request(
        command="export-classification",
        venues=venues,
        years=years,
        tracks=tracks,
    )
    paths = _run(
        "export-classification",
        lambda: export_classification_scope(
            request,
            root,
            batch_size=batch_size,
        ),
    )
    _success(
        "export-classification",
        "exported",
        batch_count=len(paths),
        batch_size=batch_size,
    )


@app.command("import-classification")
def import_classification(
    inputs: Annotated[list[Path], typer.Option("--input")],
    venues: str = typer.Option(..., "--venues"),
    years: str = typer.Option(..., "--years"),
    tracks: str | None = typer.Option(None, "--tracks"),
    root: Annotated[Path, typer.Option("--root")] = _DEFAULT_ROOT,
) -> None:
    """Import exact semantic-labeling files for the requested conference."""
    request = _request(
        command="import-classification",
        venues=venues,
        years=years,
        tracks=tracks,
    )
    assignments = _run(
        "import-classification",
        lambda: import_semantic_assignments_scope(request, root, inputs),
    )
    _success(
        "import-classification",
        "imported",
        paper_count=len(assignments),
        source_count=len(inputs),
    )


@app.command("export-chinese-content")
def export_chinese_content(
    venue: str = typer.Option(..., "--venue"),
    year: str = typer.Option(..., "--year"),
    track: str | None = typer.Option(None, "--track"),
    shards: int = typer.Option(16, "--shards", min=1),
    root: Annotated[Path, typer.Option("--root")] = _DEFAULT_ROOT,
) -> None:
    """Export deterministic ordinary-summary and award deep-read sources."""
    request = _request(
        command="export-chinese-content",
        venues=venue,
        years=year,
        tracks=track,
    )
    paths = _run(
        "export-chinese-content",
        lambda: export_chinese_content_scope(request, root, shard_count=shards),
    )
    _success(
        "export-chinese-content",
        "exported",
        source_count=len(paths),
    )


@app.command("check-chinese-content-sources")
def check_chinese_content_sources(
    venue: str = typer.Option(..., "--venue"),
    year: str = typer.Option(..., "--year"),
    track: str | None = typer.Option(None, "--track"),
    root: Annotated[Path, typer.Option("--root")] = _DEFAULT_ROOT,
) -> None:
    """Check source-shard membership against the selected release."""
    request = _request(
        command="check-chinese-content-sources",
        venues=venue,
        years=year,
        tracks=track,
    )
    coverage = _run(
        "check-chinese-content-sources",
        lambda: check_chinese_content_sources_scope(request, root),
    )
    _success(
        "check-chinese-content-sources",
        "checked",
        ordinary_count=coverage.ordinary_count,
        award_count=coverage.award_count,
        total_count=coverage.total_count,
    )


@app.command("import-chinese-content")
def import_chinese_content(
    summary_files: Annotated[list[Path], typer.Option("--summary-file")],
    awards_path: Annotated[Path, typer.Option("--awards")],
    venue: str = typer.Option(..., "--venue"),
    year: str = typer.Option(..., "--year"),
    track: str | None = typer.Option(None, "--track"),
    allow_incomplete: bool = typer.Option(False, "--allow-incomplete"),
    root: Annotated[Path, typer.Option("--root")] = _DEFAULT_ROOT,
) -> None:
    """Validate authored Chinese content without selecting a generation."""
    request = _request(
        command="import-chinese-content",
        venues=venue,
        years=year,
        tracks=track,
    )
    bundle = _run(
        "import-chinese-content",
        lambda: import_chinese_content_scope(
            request,
            root,
            summary_files=summary_files,
            award_path=awards_path,
            allow_incomplete=allow_incomplete,
        ),
    )
    _success(
        "import-chinese-content",
        "validated",
        ordinary_count=bundle.ordinary_count,
        award_count=bundle.award_count,
        total_count=bundle.total_count,
        complete=not allow_incomplete,
    )


@app.command("build-chinese-content")
def build_chinese_content(
    venue: str = typer.Option(..., "--venue"),
    year: str = typer.Option(..., "--year"),
    track: str | None = typer.Option(None, "--track"),
    root: Annotated[Path, typer.Option("--root")] = _DEFAULT_ROOT,
) -> None:
    """Build and select a complete immutable Chinese content generation."""
    request = _request(
        command="build-chinese-content",
        venues=venue,
        years=year,
        tracks=track,
    )
    generation = _run(
        "build-chinese-content",
        lambda: build_chinese_content_scope(request, root),
    )
    _success(
        "build-chinese-content",
        "built",
        generation=f"generations/{generation.name}",
    )


@app.command()
def analyze(
    venues: str = typer.Option(..., "--venues"),
    years: str = typer.Option(..., "--years"),
    tracks: str | None = typer.Option(None, "--tracks"),
    write_release: bool = typer.Option(False, "--write-release"),
    root: Annotated[Path, typer.Option("--root")] = _DEFAULT_ROOT,
) -> None:
    """Run assisted analysis and optionally select an immutable release."""
    request = _request(command="analyze", venues=venues, years=years, tracks=tracks)
    summary = _run(
        "analyze",
        lambda: analyze_scope(request, root, write_release=write_release),
    )
    _success(
        "analyze",
        "release_written" if write_release else "analyzed",
        **summary,
    )


@app.command("reconcile-final")
def reconcile_final(
    venues: str = typer.Option(..., "--venues"),
    years: str = typer.Option(..., "--years"),
    tracks: str | None = typer.Option(None, "--tracks"),
    root: Annotated[Path, typer.Option("--root")] = _DEFAULT_ROOT,
) -> None:
    """Check the configured final proceedings source without auto-publishing."""
    request = _request(
        command="reconcile-final", venues=venues, years=years, tracks=tracks
    )
    result = _run(
        "reconcile-final", lambda: reconcile_final_scope(request, root)
    )
    _success(
        "reconcile-final",
        str(result["status"]),
        venue=request.venue,
        year=request.year,
        track=request.track,
    )


@app.command()
def awards(
    venue: str = typer.Option(..., "--venue"),
    year: str = typer.Option(..., "--year"),
    track: str | None = typer.Option(None, "--track"),
    root: Annotated[Path, typer.Option("--root")] = _DEFAULT_ROOT,
) -> None:
    """Parse an official volume-page award inventory without PDF deep reads."""
    request = _request(command="awards", venues=venue, years=year, tracks=track)
    inventory = _run("awards", lambda: parse_award_inventory_scope(request, root))
    _success(
        "awards",
        "official_inventory",
        award_count=len(inventory),
        deep_read_count=0,
    )


@app.command("build-site")
def build_site(
    root: Annotated[Path, typer.Option("--root")] = _DEFAULT_ROOT,
    release_dir: Annotated[Path | None, typer.Option("--release-dir")] = None,
    site_dir: Annotated[Path | None, typer.Option("--site-dir")] = None,
) -> None:
    """Build Astro only from the validated release selected by current.json."""
    dist = _run(
        "build-site",
        lambda: build_site_scope(
            root,
            release_dir=release_dir,
            site_dir=site_dir,
        ),
    )
    _success("build-site", "built", dist=str(dist))


if __name__ == "__main__":
    app()
