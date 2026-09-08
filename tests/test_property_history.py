"""Per-property history tests."""

from __future__ import annotations

import json
from pathlib import Path

from src.property_history import (
    build_property_histories,
    changed_histories,
    format_price_history,
    listing_key,
)


def test_listing_key_uses_nc_id() -> None:
    assert (
        listing_key("https://suumo.jp/ms/chuko/tokyo/sc_chiyoda/nc_21351233/")
        == "nc_21351233"
    )


def test_build_property_histories_keeps_all_days(tmp_path: Path) -> None:
    for day, price in (("2026-09-06", 5000), ("2026-09-07", 5000), ("2026-09-08", 4800)):
        payload = {
            "snapshot_date": day,
            "configs": [
                {
                    "name": "千代田区 中古マンション",
                    "listings": [
                        {
                            "property_id": "fp_old" if day != "2026-09-08" else "fp_new",
                            "name": "テストマンション",
                            "price_man": price,
                            "url": "https://suumo.jp/ms/chuko/tokyo/sc_chiyoda/nc_21351233/",
                        }
                    ],
                }
            ],
        }
        (tmp_path / f"daily_prices_{day}.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    histories = build_property_histories(tmp_path)
    points = histories["nc_21351233"]
    assert [p.snapshot_date for p in points] == [
        "2026-09-06",
        "2026-09-07",
        "2026-09-08",
    ]
    assert [p.price_man for p in points] == [5000, 5000, 4800]
    text = format_price_history(points)
    assert "2026-09-06 5000万円" in text
    assert "2026-09-08 4800万円" in text
    assert "nc_21351233" in changed_histories(histories)
