import re
from dataclasses import dataclass
from pathlib import Path

from conference_overview.models import VenueRequest

_SAFE_SCOPE_SEGMENT = re.compile(r"[A-Za-z0-9-]+\Z")


def _safe_segment(value: str) -> str:
    if _SAFE_SCOPE_SEGMENT.fullmatch(value) is None:
        raise ValueError(f"not a safe scope segment: {value!r}")
    return value


def release_relative_parts(request: VenueRequest) -> tuple[str, ...]:
    """Return the registry-bound release path below ``data/releases``."""
    venue = _safe_segment(request.venue)
    year = _safe_segment(str(request.year))
    if request.track is None:
        raise ValueError("track must be configured before building release paths")
    track = _safe_segment(request.track)
    if request.is_default_track:
        return venue, year
    return venue, year, "tracks", track


@dataclass(frozen=True)
class ScopePaths:
    root: Path
    manifest: Path
    normalized: Path
    snapshots: Path
    analysis: Path
    classification: Path
    awards: Path
    award_deep_reads: Path
    award_deep_read_provenance: Path
    release: Path
    notes: Path

    @property
    def low_confidence_queue(self) -> Path:
        return self.classification / "low-confidence-review-queue.json"

    @property
    def low_confidence_decisions(self) -> Path:
        return self.classification / "low-confidence-decisions.json"

    @classmethod
    def for_request(cls, root: Path, request: VenueRequest) -> "ScopePaths":
        venue = _safe_segment(request.venue)
        year = _safe_segment(str(request.year))
        if request.track is None:
            raise ValueError("track must be configured before building scope paths")
        track = _safe_segment(request.track)
        data_venue = venue.lower()
        scope_name = f"{year}-{track}"
        note_name = f"{data_venue}-{scope_name}-overview.md"

        return cls(
            root=root,
            manifest=root / "data" / "manifests" / data_venue / f"{scope_name}.json",
            normalized=root
            / "data"
            / "normalized"
            / data_venue
            / f"{scope_name}.jsonl",
            snapshots=root / "data" / "snapshots" / data_venue / scope_name,
            analysis=root / "data" / "analysis" / data_venue / scope_name,
            classification=root
            / "data"
            / "classification"
            / data_venue
            / scope_name,
            awards=root / "data" / "awards" / data_venue / f"{scope_name}.yaml",
            award_deep_reads=root
            / "data"
            / "awards"
            / data_venue
            / f"{scope_name}-deep-reads.yaml",
            award_deep_read_provenance=root
            / "data"
            / "awards"
            / data_venue
            / f"{scope_name}-deep-read-provenance.json",
            release=root / "data" / "releases" / Path(*release_relative_parts(request)),
            notes=root / "notes" / note_name,
        )
