"""Daily insight copy tests."""

from __future__ import annotations

from src.daily_insight import (
    build_daily_insight,
    format_insight_markdown,
    render_insight_html,
    write_insight_files,
)


def _listing(index: int, price: int) -> dict:
    return {
        "property_id": f"id{index}",
        "name": f"テストマンション{index}",
        "address": "東京都千代田区",
        "price_man": price,
        "area_sqm": 60.0,
        "layout": "2LDK",
        "built_year": "2010年",
        "station": "半蔵門 徒歩5分",
        "walk_minutes": 5,
        "floor": "3階",
        "url": f"https://suumo.jp/ms/chuko/tokyo/sc_chiyoda/nc_{index}/",
    }


def _payload(day: str, prices: list[int]) -> dict:
    listings = [_listing(index, price) for index, price in enumerate(prices, start=1)]
    return {
        "snapshot_date": day,
        "listing_count": len(listings),
        "config_count": 1,
        "configs": [
            {
                "name": "千代田区 中古マンション",
                "listings": listings,
            }
        ],
    }


def test_first_day_insight_waits_for_previous() -> None:
    insight = build_daily_insight(_payload("2026-09-08", [5000]), None)
    assert insight.headline_kind == "first_day"
    assert "翌日" in insight.lead


def test_small_adjust_headline_for_low_rate_shallow_cuts() -> None:
    previous = _payload("2026-09-07", [5000] * 100)
    current_prices = [5000] * 100
    current_prices[0] = 4900
    current_prices[1] = 4850
    current = _payload("2026-09-08", current_prices)
    insight = build_daily_insight(current, previous)
    assert insight.headline_kind == "small_adjust"
    assert insight.drop_count == 2
    assert insight.headline.startswith("値下げ2件は、相場崩壊ではなく")
    assert "いま言えること" in format_insight_markdown(insight)


def test_no_drop_headline() -> None:
    previous = _payload("2026-09-07", [5000, 6000])
    current = _payload("2026-09-08", [5000, 6000])
    insight = build_daily_insight(current, previous)
    assert insight.headline_kind == "no_drop"
    assert insight.drop_count == 0


def test_write_insight_files(tmp_path) -> None:
    previous = _payload("2026-09-07", [5000, 6000])
    current = _payload("2026-09-08", [4800, 6000])
    json_path, md_path = write_insight_files(tmp_path, current, previous)
    assert json_path.exists()
    assert md_path.exists()
    markdown = md_path.read_text(encoding="utf-8")
    assert "今日の読み取り" in markdown
    assert "東京23区・市部全体が下落局面" in markdown
    assert "23区全体が下落局面" not in markdown


def test_new_city_watch_is_explained_in_caveat() -> None:
    previous = {
        "snapshot_date": "2026-09-10",
        "listing_count": 1,
        "config_count": 1,
        "configs": [
            {
                "name": "千代田区 中古マンション",
                "listings": [_listing(1, 5000)],
            }
        ],
    }
    current = {
        "snapshot_date": "2026-09-11",
        "listing_count": 2,
        "config_count": 2,
        "configs": [
            {
                "name": "千代田区 中古マンション",
                "listings": [_listing(1, 5000)],
            },
            {
                "name": "八王子市 中古マンション",
                "listings": [
                    {
                        **_listing(2, 3000),
                        "address": "東京都八王子市",
                        "url": "https://suumo.jp/ms/chuko/tokyo/sc_hachioji/nc_2/",
                    }
                ],
            },
        ],
    }
    insight = build_daily_insight(current, previous)
    assert "市部1市（1件）" in insight.caveat
    assert "新規監視" in insight.caveat
    assert "翌日以降" in insight.caveat
    markdown = format_insight_markdown(insight)
    assert "市部1市（1件）" in markdown


def test_highlights_prefer_drop_rate_over_amount() -> None:
    previous = _payload("2026-09-07", [20000, 3000])
    current = _payload("2026-09-08", [18000, 2400])
    insight = build_daily_insight(current, previous)
    assert [item.name for item in insight.largest_drops] == [
        "テストマンション2",
        "テストマンション1",
    ]
    assert insight.largest_drops[0].drop_pct == 20.0
    assert insight.largest_drops[1].drop_pct == 10.0
    markdown = format_insight_markdown(insight)
    assert "値下げ率が大きい物件" in markdown
    assert "値下げ額が大きい物件" not in markdown
    assert "△20.0% / -600万円" in markdown
    assert "△10.0% / -2000万円" in markdown
    html = render_insight_html(insight)
    assert "値下げ率が大きい物件" in html
    assert "△20.0%" in html

