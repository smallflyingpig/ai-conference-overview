from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from conference_overview.models import VenueRequest

_VENUES_RESOURCE = files("conference_overview").joinpath("venues.yaml")
_SOURCE_VENUES_PATH = Path(__file__).resolve().parents[2] / "config" / "venues.yaml"


def _load_venues() -> dict[str, Any]:
    venues_path = _VENUES_RESOURCE if _VENUES_RESOURCE.is_file() else _SOURCE_VENUES_PATH
    with venues_path.open(encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)["venues"]


def normalize_request(venue: str, year: int, track: str | None) -> VenueRequest:
    venues = _load_venues()
    canonical_venue = venue.strip().upper()
    canonical_venue = next(
        (
            name
            for name, definition in venues.items()
            if canonical_venue == name
            or canonical_venue in {alias.upper() for alias in definition.get("aliases", [])}
        ),
        canonical_venue,
    )
    canonical_track = track.strip().lower() if track else None
    route = (
        venues.get(canonical_venue, {})
        .get("years", {})
        .get(year, {})
        .get("tracks", {})
        .get(canonical_track, {})
    )

    return VenueRequest(
        venue=canonical_venue,
        year=year,
        track=canonical_track,
        source_key=route.get("source_key"),
        bibtex_url=route.get("bibtex_url"),
        volume_url=route.get("volume_url"),
        official_award_hosts=tuple(route.get("official_award_hosts", ())),
    )


def official_award_hosts(venue: str, year: int, track: str) -> tuple[str, ...]:
    """Return the configured, canonical official award host policy for a scope."""
    return normalize_request(venue, year, track).official_award_hosts
