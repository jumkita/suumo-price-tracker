"""Diff engine tests."""

from __future__ import annotations

from src.db import ListingRow
from src.diff import compare_listings, format_man


def _listing(
    property_id: str,
    name: str,
    price: int | None,
) -> ListingRow:
    return ListingRow(
        property_id=property_id,
        name=name,
        address="東京都千代田区",
        price_man=price,
        area_sqm=60.0,
        layout="2LDK",
        built_year="2010年1月",
        station="半蔵門",
        url=f"https://suumo.jp/ms/chuko/nc_{property_id}/",
    )


def test_compare_listings_detects_drop_rise_new_removed() -> None:
    previous = [
        _listing("1", "Aマンション", 5000),
        _listing("2", "Bマンション", 6000),
        _listing("3", "Cマンション", 7000),
    ]
    current = [
        _listing("1", "Aマンション", 4800),  # drop
        _listing("2", "Bマンション", 6200),  # rise
        _listing("4", "Dマンション", 5500),  # new
    ]

    diff = compare_listings(previous, current)
    assert diff.drop_count == 1
    assert diff.price_drops[0].property_id == "1"
    assert diff.price_drops[0].delta_man == -200
    assert diff.rise_count == 1
    assert diff.price_rises[0].property_id == "2"
    assert diff.new_count == 1
    assert diff.new_listings[0].property_id == "4"
    assert diff.removed_count == 1
    assert diff.removed_listings[0].property_id == "3"


def test_compare_listings_unchanged() -> None:
    previous = [_listing("1", "A", 5000)]
    current = [_listing("1", "A", 5000)]
    diff = compare_listings(previous, current)
    assert diff.unchanged_count == 1
    assert diff.drop_count == 0


def test_format_man() -> None:
    assert format_man(5980) == "5980万円"
    assert format_man(12800) == "1億2800万円"
    assert format_man(20000) == "2億円"
    assert format_man(None) == "-"
