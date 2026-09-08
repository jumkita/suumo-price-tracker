"""Ward / price-band label tests."""

from __future__ import annotations

from src.listing_display import (
    area_unit_band,
    format_built_age,
    price_band,
    price_band_start,
    walk_matches,
    ward_label,
)


def test_ward_label_strips_watch_suffix() -> None:
    assert ward_label("千代田区 中古マンション") == "千代田区"
    assert ward_label("港区") == "港区"
    assert ward_label("") == "-"


def test_price_band_uses_1000_man_units() -> None:
    assert price_band_start(4800) == 4000
    assert price_band_start(None) is None
    assert price_band(None) == "-"
    assert price_band(999) == "〜1000万円"
    assert price_band(4800) == "4000万円〜5000万円"
    assert price_band(8000) == "8000万円〜9000万円"
    assert price_band(15000) == "1億5000万円〜1億6000万円"
    assert price_band(20000) == "2億円〜2億1000万円"


def test_area_unit_band_uses_10m2() -> None:
    assert area_unit_band(None) == "-"
    assert area_unit_band(60.0) == "60〜70m2"
    assert area_unit_band(127.76) == "120〜130m2"


def test_walk_matches_thresholds() -> None:
    assert walk_matches(5, "lte5") is True
    assert walk_matches(6, "lte5") is False
    assert walk_matches(10, "lte10") is True
    assert walk_matches(21, "lte20") is False
    assert walk_matches(20, "gte20") is True
    assert walk_matches(19, "gte20") is False
    assert walk_matches(None, "lte10") is False
    assert walk_matches(8, "unknown") is False


def test_format_built_age_uses_snapshot_year() -> None:
    assert format_built_age("2010年1月", "2026-09-08") == "築16年"
    assert format_built_age("2010年", "2026-09-08") == "築16年"
    assert format_built_age("", "2026-09-08") == "-"
    assert format_built_age("2010年", "") == "2010年"
