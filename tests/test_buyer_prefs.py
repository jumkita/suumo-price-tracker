"""Buyer preference matching for personal highlights."""

from __future__ import annotations

from src.buyer_prefs import (
    BuyerPrefs,
    drop_matches_prefs,
    filter_drops_by_prefs,
    layout_matches,
    select_pref_highlights,
)
from src.diff import PriceChange


def _drop(
    *,
    property_id: str = "1",
    name: str = "サンプル",
    old: int = 6000,
    new: int = 5400,
    ward: str = "世田谷区",
    area: float | None = 65.0,
    layout: str = "2LDK",
    walk: int | None = 8,
    built_year: str = "2012年",
) -> PriceChange:
    return PriceChange(
        property_id=property_id,
        name=name,
        old_price_man=old,
        new_price_man=new,
        delta_man=new - old,
        url=f"https://suumo.jp/ms/chuko/nc_{property_id}/",
        address=f"東京都{ward}",
        station="",
        station_name="桜新町",
        walk_minutes=walk,
        area_sqm=area,
        layout=layout,
        floor="3階",
        ward_name=f"{ward} 中古マンション",
        built_year=built_year,
    )


def test_empty_prefs_keep_all_drops() -> None:
    drops = [_drop(ward="港区"), _drop(property_id="2", ward="八王子市")]
    assert filter_drops_by_prefs(drops, BuyerPrefs(), "2026-10-15") == drops


def test_prefs_exclude_other_ward_and_high_price() -> None:
    wanted = _drop(property_id="ok", ward="世田谷区", new=5200, old=5800)
    other_ward = _drop(property_id="ward", ward="港区", new=5200, old=5800)
    too_expensive = _drop(property_id="yen", ward="世田谷区", old=18000, new=16000)
    prefs = BuyerPrefs(wards=("世田谷区", "目黒区"), price_min_man=4000, price_max_man=8000)
    matched = filter_drops_by_prefs(
        [wanted, other_ward, too_expensive],
        prefs,
        "2026-10-15",
    )
    assert [item.property_id for item in matched] == ["ok"]


def test_prefs_exclude_old_cheap_high_rate_listings() -> None:
    wreck = _drop(
        property_id="old",
        name="築古安値",
        old=1800,
        new=900,
        ward="足立区",
        area=28.0,
        layout="1K",
        walk=18,
        built_year="1978年",
    )
    family = _drop(
        property_id="fam",
        name="希望どおり",
        old=6200,
        new=5800,
        ward="世田谷区",
        area=68.0,
        layout="3LDK",
        walk=7,
        built_year="2015年",
    )
    prefs = BuyerPrefs(
        wards=("世田谷区",),
        price_min_man=4000,
        price_max_man=9000,
        max_built_age=25,
        min_area_sqm=55,
        max_walk_minutes=15,
        layouts=("2LDK", "3LDK", "4LDK+"),
    )
    chosen = select_pref_highlights([wreck, family], 3, prefs, "2026-10-15")
    assert [item.property_id for item in chosen] == ["fam"]
    assert drop_matches_prefs(wreck, prefs, "2026-10-15") is False


def test_missing_fields_fail_strict_constraints() -> None:
    unknown_age = _drop(built_year="")
    prefs = BuyerPrefs(max_built_age=20)
    assert drop_matches_prefs(unknown_age, prefs, "2026-10-15") is False


def test_price_bounds_are_swapped_when_reversed() -> None:
    item = _drop(new=5000, old=5500)
    prefs = BuyerPrefs(price_min_man=8000, price_max_man=4000)
    assert drop_matches_prefs(item, prefs, "2026-10-15") is True


def test_layout_matches_sldk_and_four_plus() -> None:
    assert layout_matches("2SLDK", ("2LDK",)) is True
    assert layout_matches("1K", ("1LDK",)) is False
    assert layout_matches("1LDK", ("1K",)) is False
    assert layout_matches("4LDK", ("4LDK+",)) is True
    assert layout_matches("5LDK", ("4LDK+",)) is True
    assert layout_matches("3LDK", ("4LDK+",)) is False
