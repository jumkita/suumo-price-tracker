"""Citywide comparison tests."""

from __future__ import annotations

from src.citywide import compare_citywide


def _listing(property_id: str, name: str, price: int, url_slug: str) -> dict:
    return {
        "property_id": property_id,
        "name": name,
        "address": "東京都",
        "price_man": price,
        "area_sqm": 60.0,
        "layout": "2LDK",
        "built_year": "2010年",
        "station": "徒歩5分",
        "walk_minutes": 5,
        "floor": "3階",
        "url": f"https://suumo.jp/ms/chuko/tokyo/{url_slug}/",
    }


def test_compare_citywide_includes_new_city_as_new_listings() -> None:
    previous = {
        "listing_count": 1,
        "configs": [
            {
                "name": "千代田区 中古マンション",
                "listings": [_listing("w1", "区の物件", 5000, "sc_chiyoda/nc_1")],
            }
        ],
    }
    current = {
        "listing_count": 3,
        "configs": [
            {
                "name": "千代田区 中古マンション",
                "listings": [_listing("w1", "区の物件", 4800, "sc_chiyoda/nc_1")],
            },
            {
                "name": "八王子市 中古マンション",
                "listings": [
                    _listing("c1", "市の物件A", 3000, "sc_hachioji/nc_2"),
                    _listing("c2", "市の物件B", 2800, "sc_hachioji/nc_3"),
                ],
            },
        ],
    }
    comparison = compare_citywide(current, previous)
    assert comparison is not None
    assert len(comparison.drops) == 1
    assert comparison.drops[0].property_id == "w1"
    assert {item.ward: item.cur_count for item in comparison.wards} == {
        "千代田区": 1,
        "八王子市": 2,
    }
    hachioji = next(item for item in comparison.wards if item.ward == "八王子市")
    assert hachioji.prev_count == 0
    assert hachioji.new_count == 2
    assert hachioji.drop_count == 0
    assert hachioji.matched == 0
    assert comparison.new_count == 2
