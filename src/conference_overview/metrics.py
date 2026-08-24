"""Deterministic, decimal-based conference distribution metrics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise
from types import MappingProxyType
from typing import Final


class InvalidDenominator(ValueError):
    """Raised when a ratio's denominator is zero or negative."""


class InsufficientTrendWindow(ValueError):
    """Raised when years cannot support an unqualified trend claim."""


class InvalidScoreComponent(ValueError):
    """Raised when an Emerging Score component is outside the unit interval."""


_EMERGING_WEIGHTS: Final[Mapping[str, Decimal]] = MappingProxyType(
    {
        "share_growth": Decimal("0.45"),
        "spread_growth": Decimal("0.35"),
        "novelty": Decimal("0.20"),
    }
)


@dataclass(frozen=True)
class EmergingScore:
    """Published score plus the inputs and weights needed to reproduce it."""

    score: Decimal
    components: Mapping[str, str]
    weights: Mapping[str, str]

    def to_dict(self) -> dict[str, Decimal | dict[str, str]]:
        """Return a public representation of the score contract."""
        return {
            "score": self.score,
            "components": dict(self.components),
            "weights": dict(self.weights),
        }


def _as_decimal(value: Decimal | int | str) -> Decimal:
    """Convert supported exact numeric inputs without introducing floats."""
    if isinstance(value, Decimal):
        return value
    return Decimal(value)


def _require_positive_denominator(value: Decimal | int | str) -> Decimal:
    denominator = _as_decimal(value)
    if denominator <= 0:
        raise InvalidDenominator("denominator must be greater than zero")
    return denominator


def topic_share(topic_count: Decimal | int | str, included_count: Decimal | int | str) -> Decimal:
    """Return a topic's share using the included venue-year count as denominator."""
    return _as_decimal(topic_count) / _require_positive_denominator(included_count)


def yoy_share_delta(current_share: Decimal | int | str, prior_share: Decimal | int | str) -> Decimal:
    """Return the year-over-year percentage-point difference between shares."""
    return _as_decimal(current_share) - _as_decimal(prior_share)


def venue_enrichment(
    venue_share: Decimal | int | str, baseline_share: Decimal | int | str
) -> Decimal:
    """Return the ratio of a venue's topic share to the comparison baseline."""
    return _as_decimal(venue_share) / _require_positive_denominator(baseline_share)


def cross_venue_spread(shares: Sequence[Decimal | int | str]) -> Decimal:
    """Return the range of a topic's shares across venues."""
    values = [_as_decimal(share) for share in shares]
    if not values:
        raise ValueError("at least one venue share is required")
    return max(values) - min(values)


def validate_trend_window(years: Sequence[int]) -> None:
    """Require three or more distinct, consecutive years for trend language."""
    ordered_years = sorted(years)
    if len(ordered_years) < 3 or any(
        current != previous + 1
        for previous, current in pairwise(ordered_years)
    ):
        raise InsufficientTrendWindow(
            "an unqualified trend requires at least three distinct consecutive years"
        )


def quantize_for_display(value: Decimal | int | str, *, decimal_places: int = 2) -> Decimal:
    """Quantize a metric for display without changing its stored Decimal value."""
    if decimal_places < 0:
        raise ValueError("decimal_places must be non-negative")
    return _as_decimal(value).quantize(Decimal(1).scaleb(-decimal_places))


def emerging_score(
    *,
    share_growth: Decimal | int | str,
    spread_growth: Decimal | int | str,
    novelty: Decimal | int | str,
) -> EmergingScore:
    """Calculate the published Emerging Score and retain reproducibility inputs."""
    raw_components = {
        "share_growth": _as_decimal(share_growth),
        "spread_growth": _as_decimal(spread_growth),
        "novelty": _as_decimal(novelty),
    }
    for name, value in raw_components.items():
        if not Decimal(0) <= value <= Decimal(1):
            raise InvalidScoreComponent(f"{name} must be within [0, 1]")

    return EmergingScore(
        score=sum(raw_components[name] * weight for name, weight in _EMERGING_WEIGHTS.items()),
        components={name: str(value) for name, value in raw_components.items()},
        weights={name: str(weight) for name, weight in _EMERGING_WEIGHTS.items()},
    )
