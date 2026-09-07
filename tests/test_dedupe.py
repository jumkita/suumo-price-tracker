"""Deduplication tests for multi-agency listings."""

from __future__ import annotations

from src.dedupe import collapse_to_cheapest, normalize_text, property_fingerprint
from src.scraper.suumo import Listing


def _listing(
    property_id: str,
    name: str,
    price: int | None,
    *,
    address: str = "東京都千代田区一番町１−１",
    area: float = 65.2,
    layout: str = "２ＬＤＫ",
) -> Listing:
    return Listing(
        property_id=property_id,
        name=name,
        address=address,
        price_man=price,
        area_sqm=area,
        layout=layout,
        built_year="2005年3月",
        station="半蔵門",
        url=f"https://suumo.jp/ms/chuko/nc_{property_id}/",
    )


def test_normalize_text_strips_noise_and_width() -> None:
    assert normalize_text("サンプルコート　千代田【仲介手数料無料】") == (
        normalize_text("サンプルコート千代田")
    )


def test_same_property_different_agency_same_fingerprint() -> None:
    a = _listing("111", "サンプルコート千代田", 5980)
    b = _listing("222", "サンプルコート　千代田【仲介】", 5800)
    assert property_fingerprint(a) == property_fingerprint(b)


def test_collapse_keeps_cheapest() -> None:
    listings = [
        _listing("111", "サンプルコート千代田", 5980),
        _listing("222", "サンプルコート　千代田【仲介手数料無料】", 5800),
        _listing("333", "別物件タワー", 9000, address="東京都千代田区麹町"),
    ]
    collapsed = collapse_to_cheapest(listings)
    assert len(collapsed) == 2
    sample = next(item for item in collapsed if "サンプル" in item.name)
    assert sample.price_man == 5800
    assert sample.property_id.startswith("fp_")
    assert sample.url.endswith("nc_222/")


def test_collapse_prefers_priced_over_missing() -> None:
    listings = [
        _listing("1", "同一物件", None),
        _listing("2", "同一物件", 5000),
    ]
    collapsed = collapse_to_cheapest(listings)
    assert len(collapsed) == 1
    assert collapsed[0].price_man == 5000
