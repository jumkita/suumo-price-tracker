"""Static site builder tests."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_site import _filter_options, build_site
from src.diff import PriceChange


def test_build_site_writes_index(tmp_path: Path) -> None:
    publish = tmp_path / "published"
    site = tmp_path / "site"
    publish.mkdir()
    payload = {
        "snapshot_date": "2026-09-08",
        "generated_at": "2026-09-08T08:00:00+09:00",
        "config_count": 1,
        "listing_count": 1,
        "configs": [
            {
                "name": "千代田区 中古マンション",
                "search_url": "https://suumo.jp/x",
                "max_pages": 1,
                "enabled": True,
                "listing_count": 1,
                "fetched_at": "2026-09-08T08:00:00",
                "listings": [
                    {
                        "property_id": "fp1",
                        "name": "テストマンション",
                        "address": "東京都千代田区",
                        "price_man": 4800,
                        "area_sqm": 60.0,
                        "layout": "2LDK",
                        "built_year": "2010年",
                        "station": "東京メトロ半蔵門線「半蔵門」徒歩5分",
                        "walk_minutes": 5,
                        "floor": "3階",
                        "url": "https://suumo.jp/x",
                    }
                ],
            }
        ],
    }
    prev = {
        **payload,
        "snapshot_date": "2026-09-07",
        "configs": [
            {
                **payload["configs"][0],
                "listings": [
                    {
                        **payload["configs"][0]["listings"][0],
                        "price_man": 5000,
                    }
                ],
            }
        ],
    }
    (publish / "daily_prices.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    (publish / "daily_prices_2026-09-07.json").write_text(
        json.dumps(prev, ensure_ascii=False),
        encoding="utf-8",
    )
    (publish / "daily_prices_2026-09-08.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    index = build_site(publish, site, enrich_floor=False)
    html = index.read_text(encoding="utf-8")
    assert "SUUMO価格トラッキング" in html
    assert "値下げ一覧（全エリア横断）" in html
    assert "X投稿下書き（23区+市部まとめて）" in html
    assert "東京23区+市部 中古マンション" in html
    assert "監視エリア数" in html
    assert "テストマンション" in html
    assert "半蔵門" in html
    assert "徒歩5分" in html
    assert "60.00m2" in html
    assert "2LDK" in html
    assert "3階" in html
    assert "viewport" in html
    assert "価格履歴" in html
    assert "2026-09-07 5000万円" in html
    assert "2026-09-08 4800万円" in html
    assert "平均価格の推移" not in html
    assert "東京都千代田区" in html
    assert "千代田区" in html
    assert "4000万円〜5000万円" in html
    assert "5000万円〜6000万円" in html
    assert "60〜70m2" in html
    assert 'data-old-filter="5000万円〜6000万円"' in html
    assert 'data-new-filter="4000万円〜5000万円"' in html
    assert 'data-area-filter="60〜70m2"' in html
    assert "5分以内" in html
    assert "data-filter=" in html
    assert 'data-filter-mode="text"' in html
    assert 'data-filter-mode="walk"' in html
    assert "data-key=" in html
    assert "drops-table" in html
    assert "築16年" in html
    assert "<select" in html
    assert 'input type="search"' in html
    assert "並び替え" in html
    assert "昇順" in html
    assert "降順" in html
    assert "すべて" in html
    assert "今日の読み取り" in html
    assert "値下げが広め" in html


def test_filter_options_sort_price_and_area_numerically() -> None:
    cheap = PriceChange(
        property_id="cheap",
        name="安い物件",
        old_price_man=2500,
        new_price_man=2000,
        delta_man=-500,
        url="https://suumo.jp/ms/chuko/tokyo/sc_chiyoda/nc_1/",
        address="東京都千代田区",
        station="",
        station_name="東京",
        walk_minutes=3,
        area_sqm=25.0,
        layout="1K",
        floor="2階",
        ward_name="千代田区",
        built_year="2010年",
    )
    expensive = PriceChange(
        property_id="expensive",
        name="高い物件",
        old_price_man=200000,
        new_price_man=190000,
        delta_man=-10000,
        url="https://suumo.jp/ms/chuko/tokyo/sc_chiyoda/nc_2/",
        address="東京都港区",
        station="",
        station_name="半蔵門",
        walk_minutes=25,
        area_sqm=125.0,
        layout="3LDK",
        floor="10階",
        ward_name="港区",
        built_year="2015年",
    )
    options = _filter_options([expensive, cheap], {}, "2026-09-08")
    assert options["band"] == ["2000万円〜3000万円", "19億円〜19億1000万円"]
    assert options["old"] == ["2000万円〜3000万円", "20億円〜20億1000万円"]
    assert options["new"] == ["2000万円〜3000万円", "19億円〜19億1000万円"]
    assert options["area"] == ["20〜30m2", "120〜130m2"]
