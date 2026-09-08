"""Ward / price-band label tests."""

from __future__ import annotations

from src.listing_display import price_band, ward_label


def test_ward_label_strips_watch_suffix() -> None:
    assert ward_label("千代田区 中古マンション") == "千代田区"
    assert ward_label("港区") == "港区"
    assert ward_label("") == "-"


def test_price_band_uses_new_price_thresholds() -> None:
    assert price_band(None) == "-"
    assert price_band(2999) == "〜3000万円"
    assert price_band(3000) == "3000万〜5000万円"
    assert price_band(7999) == "5000万〜8000万円"
    assert price_band(8000) == "8000万〜1億円"
    assert price_band(15000) == "1億〜2億円"
    assert price_band(20000) == "2億円〜"
