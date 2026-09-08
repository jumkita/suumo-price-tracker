"""History aggregation tests."""

from __future__ import annotations

import json
from pathlib import Path

from src.history import build_history, summarize_payload, svg_avg_price_chart, write_history


def _payload(day: str, avg_like_prices: list[int]) -> dict:
    return {
        "snapshot_date": day,
        "listing_count": len(avg_like_prices),
        "configs": [
            {
                "name": "千代田区 中古マンション",
                "listings": [
                    {"property_id": f"p{i}", "price_man": price}
                    for i, price in enumerate(avg_like_prices)
                ],
            }
        ],
    }


def test_summarize_payload_average() -> None:
    summary = summarize_payload(_payload("2026-09-07", [1000, 2000, 3000]))
    assert summary["avg_price_man"] == 2000
    assert summary["listing_count"] == 3
    assert summary["wards"]["千代田区 中古マンション"]["avg_price_man"] == 2000


def test_build_and_write_history(tmp_path: Path) -> None:
    (tmp_path / "daily_prices_2026-09-07.json").write_text(
        json.dumps(_payload("2026-09-07", [1000, 3000]), ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "daily_prices_2026-09-08.json").write_text(
        json.dumps(_payload("2026-09-08", [2000, 4000]), ensure_ascii=False),
        encoding="utf-8",
    )
    path = write_history(tmp_path)
    history = json.loads(path.read_text(encoding="utf-8"))
    assert history["point_count"] == 2
    assert [p["snapshot_date"] for p in history["points"]] == [
        "2026-09-07",
        "2026-09-08",
    ]
    svg = svg_avg_price_chart(history["points"])
    assert "polyline" in svg
    assert "2026-09-08" in svg
    assert build_history(tmp_path)["point_count"] == 2
