"""Publish / remote sync tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from src.db import ListingRow, add_watch_config, init_db, upsert_snapshot
from src.publish import build_daily_payload, write_published_json
from src.remote_sync import import_payload, with_cache_buster


def test_with_cache_buster_adds_ts() -> None:
    url = with_cache_buster("https://example.com/daily_prices.json", ts=123)
    assert "_ts=123" in url


def test_publish_and_import_roundtrip(tmp_path: Path) -> None:
    src_db = tmp_path / "src.db"
    dst_db = tmp_path / "dst.db"
    init_db(src_db)
    config_id = add_watch_config(
        "千代田区 中古マンション",
        "https://suumo.jp/jj/bukken/ichiran/JJ010FJ001/?ar=030&bs=011&sc=13101",
        db_path=src_db,
    )
    upsert_snapshot(
        config_id,
        [
            ListingRow(
                "fp_abc",
                "テストマンション",
                "東京都千代田区",
                5000,
                60.0,
                "2LDK",
                "2010年",
                "半蔵門",
                "https://suumo.jp/x",
            )
        ],
        snapshot_date=date(2026, 9, 7),
        db_path=src_db,
    )

    payload = build_daily_payload(snapshot_date=date(2026, 9, 7), db_path=src_db)
    assert payload["listing_count"] == 1
    dated, latest = write_published_json(
        payload,
        publish_dir=tmp_path / "published",
        skip_thin_guard=True,
    )
    assert dated.exists() and latest.exists()

    result = import_payload(payload, db_path=dst_db)
    assert result.config_count == 1
    assert result.listing_count == 1
    assert result.snapshot_date == "2026-09-07"
