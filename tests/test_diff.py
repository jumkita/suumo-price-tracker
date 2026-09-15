"""Diff engine tests."""

from __future__ import annotations

from src.db import ListingRow
from src.diff import (
    PriceChange,
    compare_listings,
    drop_rate_pct,
    format_highlight_change,
    format_man,
    select_highlight_drops,
)

_AUTO = object()


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


def test_compare_listings_follows_nc_id_when_fingerprint_changes() -> None:
    previous = [
        ListingRow(
            property_id="fp_old",
            name="キャッチコピー",
            address="東京都千代田区",
            price_man=5000,
            area_sqm=60.0,
            layout="2LDK",
            built_year="2010年1月",
            station="半蔵門",
            url="https://suumo.jp/ms/chuko/tokyo/sc_chiyoda/nc_21351233/",
        )
    ]
    current = [
        ListingRow(
            property_id="fp_new",
            name="テストマンション",
            address="東京都千代田区",
            price_man=4800,
            area_sqm=60.0,
            layout="2LDK",
            built_year="2010年1月",
            station="半蔵門",
            url="https://suumo.jp/ms/chuko/tokyo/sc_chiyoda/nc_21351233/",
        )
    ]
    diff = compare_listings(previous, current)
    assert diff.drop_count == 1
    assert diff.price_drops[0].delta_man == -200
    assert diff.new_count == 0
    assert diff.removed_count == 0


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


def _change(
    property_id: str,
    name: str,
    old: int | None,
    new: int | None,
    delta: int | None | object = _AUTO,
) -> PriceChange:
    if delta is _AUTO:
        resolved: int | None = None if old is None or new is None else new - old
    elif delta is None or isinstance(delta, int):
        resolved = delta
    else:
        raise TypeError("delta must be int, None, or omitted")
    return PriceChange(
        property_id=property_id,
        name=name,
        old_price_man=old,
        new_price_man=new,
        delta_man=resolved,
        url="https://suumo.jp/x",
        address="",
        station="",
    )


def test_select_highlight_drops_prefers_rate_over_amount() -> None:
    expensive_small_rate = _change("hi", "高額少額率", 20000, 18000)
    cheap_high_rate = _change("lo", "低額高率", 3000, 2400)
    chosen = select_highlight_drops(
        [expensive_small_rate, cheap_high_rate],
        limit=2,
    )
    assert [item.property_id for item in chosen] == ["lo", "hi"]
    assert drop_rate_pct(chosen[0]) == 20.0
    assert drop_rate_pct(chosen[1]) == 10.0


def test_select_highlight_drops_ties_break_by_amount_then_name() -> None:
    smaller_amount = _change("b", "B棟", 5000, 4500)
    larger_amount = _change("a", "A棟", 10000, 9000)
    same_rate_same_amount_b = _change("d", "D棟", 4000, 3600)
    same_rate_same_amount_c = _change("c", "C棟", 4000, 3600)
    chosen = select_highlight_drops(
        [smaller_amount, larger_amount, same_rate_same_amount_b, same_rate_same_amount_c],
        limit=4,
    )
    assert [item.property_id for item in chosen] == ["a", "b", "c", "d"]


def test_select_highlight_drops_excludes_invalid_and_rises() -> None:
    valid = _change("ok", "有効", 5000, 4000)
    missing_old = _change("no-old", "旧価格なし", None, 4000, delta=-1000)
    zero_old = _change("zero", "ゼロ割", 0, 0, delta=-500)
    rise = _change("up", "値上げ", 4000, 4500)
    chosen = select_highlight_drops(
        [rise, missing_old, zero_old, valid],
        limit=10,
    )
    assert [item.property_id for item in chosen] == ["ok"]
    assert drop_rate_pct(missing_old) is None
    assert drop_rate_pct(zero_old) is None
    assert drop_rate_pct(rise) is None


def test_format_highlight_change_puts_rate_before_amount() -> None:
    change = _change("1", "サンプル", 3000, 2400)
    assert format_highlight_change(change) == "3000万円→2400万円（△20.0% / -600万円）"
