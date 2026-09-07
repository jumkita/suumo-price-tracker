"""Parser and scrape helper tests using HTML fixtures."""

from __future__ import annotations

from pathlib import Path

from src.scraper.suumo import (
    build_page_url,
    extract_property_id,
    normalize_search_url,
    parse_area_sqm,
    parse_price_man,
    parse_search_html,
    scrape_search_results,
)

FIXTURE = Path(__file__).parent / "fixtures" / "suumo_search_page.html"


def test_parse_price_man_variants() -> None:
    assert parse_price_man("5,980万円") == 5980
    assert parse_price_man("1億2800万円") == 12800
    assert parse_price_man("2億円") == 20000
    assert parse_price_man("-") is None


def test_parse_area_sqm() -> None:
    assert parse_area_sqm("65.20m2") == 65.2
    assert parse_area_sqm("80.50㎡") == 80.5


def test_extract_property_id() -> None:
    assert extract_property_id("/ms/chuko/tokyo/sc_chiyoda/nc_111111111/") == "111111111"
    assert extract_property_id("https://suumo.jp/jj/bukken/...?nc=999") == "999"


def test_normalize_and_pagination() -> None:
    base = "https://suumo.jp/jj/bukken/ichiran/JJ010FJ001/?ar=030&bs=011&pn=3&page=4&ta=13"
    normalized = normalize_search_url(base)
    assert "pn=" not in normalized
    assert "page=" not in normalized
    page2 = build_page_url(normalized, 2)
    assert "page=2" in page2


def test_parse_search_html_fixture() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    listings = parse_search_html(html)
    assert len(listings) == 2
    assert listings[0].property_id == "111111111"
    assert listings[0].name == "サンプルコート千代田"
    assert listings[0].price_man == 5980
    assert listings[0].area_sqm == 65.2
    assert listings[0].layout == "2LDK"
    assert listings[1].price_man == 12800


def test_scrape_search_results_with_fake_fetch() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    calls: list[str] = []

    def fake_fetch(url: str) -> str:
        calls.append(url)
        if "page=2" in url:
            return "<html><body><div id='js-bukkenList'></div></body></html>"
        return html

    listings = scrape_search_results(
        "https://suumo.jp/jj/bukken/ichiran/JJ010FJ001/?ar=030&bs=011",
        max_pages=3,
        request_interval_sec=0,
        fetch=fake_fetch,
    )
    assert len(listings) == 2
    assert len(calls) == 2
