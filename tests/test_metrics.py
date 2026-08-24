from decimal import Decimal

import pytest

from conference_overview.metrics import (
    CrossVenueSpread,
    EmergingScore,
    InsufficientTrendWindow,
    InvalidDenominator,
    InvalidMetricInput,
    InvalidScoreComponent,
    InvalidVenueConfiguration,
    cross_venue_spread,
    emerging_score,
    quantize_for_display,
    topic_share,
    validate_trend_window,
    venue_enrichment,
    yoy_share_delta,
)


def test_topic_share_uses_venue_year_denominator() -> None:
    assert topic_share(topic_count=25, included_count=100) == Decimal("0.25")


@pytest.mark.parametrize("included_count", [0, -1])
def test_topic_share_rejects_non_positive_denominator(included_count: int) -> None:
    with pytest.raises(InvalidDenominator):
        topic_share(topic_count=1, included_count=included_count)


def test_yoy_delta_is_percentage_point_difference() -> None:
    assert yoy_share_delta(Decimal("0.25"), Decimal("0.20")) == Decimal("0.05")


def test_venue_enrichment_is_venue_share_divided_by_baseline_share() -> None:
    assert venue_enrichment(Decimal("0.30"), Decimal("0.20")) == Decimal("1.5")


@pytest.mark.parametrize("baseline_share", [Decimal(0), Decimal("-0.1")])
def test_venue_enrichment_rejects_non_positive_baseline(
    baseline_share: Decimal,
) -> None:
    with pytest.raises(InvalidDenominator):
        venue_enrichment(Decimal("0.30"), baseline_share)


def test_cross_venue_spread_reports_topic_presence_across_configured_venues() -> None:
    result = cross_venue_spread(
        topic_counts={"ACL": 4, "EMNLP": 0, "NAACL": 1, "COLING": 0},
        configured_venues={"ACL", "EMNLP", "NAACL", "COLING"},
    )

    assert result == CrossVenueSpread(
        present_venue_count=2,
        present_venue_fraction=Decimal("0.5"),
        configured_venues=("ACL", "COLING", "EMNLP", "NAACL"),
        present_venues=("ACL", "NAACL"),
    )


def test_cross_venue_spread_canonicalizes_configured_and_present_venue_order() -> None:
    forward = cross_venue_spread(
        topic_counts={"NAACL": 1, "ACL": 4, "EMNLP": 0},
        configured_venues=["NAACL", "EMNLP", "ACL"],
    )
    reverse = cross_venue_spread(
        topic_counts={"EMNLP": 0, "ACL": 4, "NAACL": 1},
        configured_venues=["ACL", "EMNLP", "NAACL"],
    )

    assert forward == reverse
    assert forward.configured_venues == ("ACL", "EMNLP", "NAACL")
    assert forward.present_venues == ("ACL", "NAACL")


def test_cross_venue_spread_reports_zero_present_venues() -> None:
    result = cross_venue_spread(
        topic_counts={"ACL": 0, "EMNLP": 0},
        configured_venues={"ACL", "EMNLP", "NAACL", "COLING"},
    )

    assert result.present_venue_count == 0
    assert result.present_venue_fraction == Decimal(0)


def test_cross_venue_spread_rejects_empty_configured_venues() -> None:
    with pytest.raises(InvalidVenueConfiguration):
        cross_venue_spread(topic_counts={}, configured_venues=set())


def test_cross_venue_spread_rejects_unconfigured_venue_input() -> None:
    with pytest.raises(InvalidVenueConfiguration):
        cross_venue_spread(
            topic_counts={"ACL": 1, "ICLR": 1},
            configured_venues={"ACL", "EMNLP"},
        )


@pytest.mark.parametrize("years", [[2026], [2024, 2026], [2024, 2025, 2025]])
def test_incomplete_or_duplicate_years_cannot_be_called_trend(years: list[int]) -> None:
    with pytest.raises(InsufficientTrendWindow):
        validate_trend_window(years)


def test_three_distinct_consecutive_years_can_be_called_trend() -> None:
    validate_trend_window([2024, 2025, 2026])


def test_display_quantization_does_not_change_stored_share() -> None:
    stored_share = topic_share(topic_count=1, included_count=3)

    assert stored_share == Decimal(1) / Decimal(3)
    assert quantize_for_display(stored_share, decimal_places=2) == Decimal("0.33")
    assert stored_share == Decimal(1) / Decimal(3)


def test_emerging_score_has_published_components() -> None:
    result = emerging_score(
        share_growth=Decimal("0.8"),
        spread_growth=Decimal("0.5"),
        novelty=Decimal("0.25"),
    )

    assert isinstance(result, EmergingScore)
    assert result.score == Decimal("0.585")
    assert result.components == {
        "share_growth": "0.8",
        "spread_growth": "0.5",
        "novelty": "0.25",
    }
    assert result.weights == {
        "share_growth": "0.45",
        "spread_growth": "0.35",
        "novelty": "0.20",
    }


@pytest.mark.parametrize("component", [Decimal("-0.01"), Decimal("1.01")])
def test_emerging_score_rejects_out_of_range_components(component: Decimal) -> None:
    with pytest.raises(InvalidScoreComponent):
        emerging_score(
            share_growth=component,
            spread_growth=Decimal("0.5"),
            novelty=Decimal("0.25"),
        )


@pytest.mark.parametrize("denominator", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_topic_share_rejects_non_finite_denominator(denominator: Decimal) -> None:
    with pytest.raises(InvalidDenominator):
        topic_share(topic_count=1, included_count=denominator)


@pytest.mark.parametrize("component", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_emerging_score_rejects_non_finite_components(component: Decimal) -> None:
    with pytest.raises(InvalidScoreComponent):
        emerging_score(
            share_growth=component,
            spread_growth=Decimal("0.5"),
            novelty=Decimal("0.25"),
        )


def test_metric_functions_reject_runtime_floats() -> None:
    with pytest.raises(InvalidMetricInput):
        topic_share(topic_count=0.5, included_count=1)

    with pytest.raises(InvalidScoreComponent):
        emerging_score(share_growth=0.5, spread_growth=Decimal("0.5"), novelty=Decimal("0.25"))
