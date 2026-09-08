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
                        "price_man": 5000,
                        "area_sqm": 60.0,
                        "layout": "2LDK",
                        "built_year": "2010年",
                        "station": "半蔵門",
                        "url": "https://suumo.jp/x",
                    }
                ],
            }
        ],
    }
    (publish / "daily_prices.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    index = build_site(publish, site)
    html = index.read_text(encoding="utf-8")
    assert "SUUMO価格トラッキング" in html
    assert "千代田区 中古マンション" in html
    assert "viewport" in html
