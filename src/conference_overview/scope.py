import re
from dataclasses import dataclass
from pathlib import Path

from conference_overview.models import VenueRequest

_SAFE_SCOPE_SEGMENT = re.compile(r"[A-Za-z0-9-]+\Z")


def _safe_segment(value: str) -> str:
    if _SAFE_SCOPE_SEGMENT.fullmatch(value) is None:
        raise ValueError(f"not a safe scope segment: {value!r}")
    return value


@dataclass(frozen=True)
class ScopePaths:
    manifest: Path
    normalized: Path
    snapshots: Path
    analysis: Path
    release: Path
    notes: Path

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
            manifest=root / "data" / "manifests" / data_venue / f"{scope_name}.json",
            normalized=root
            / "data"
            / "normalized"
            / data_venue
            / f"{scope_name}.jsonl",
            snapshots=root / "data" / "snapshots" / data_venue / scope_name,
            analysis=root / "data" / "analysis" / data_venue / scope_name,
            release=root / "data" / "releases" / venue / year,
            notes=root / "notes" / note_name,
        )
