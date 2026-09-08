"""Static site builder tests."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_site import build_site


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
    assert "値下げ一覧（全区横断）" in html
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
    assert "3000万〜5000万円" in html
    assert "data-filter=" in html
    assert "data-key=" in html
    assert "drops-table" in html
