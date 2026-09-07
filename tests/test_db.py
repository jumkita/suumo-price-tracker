"""DB upsert and snapshot comparison helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from src.db import (
    ListingRow,
    add_watch_config,
    get_latest_two_snapshots,
    get_listings_for_snapshot,
    init_db,
    upsert_snapshot,
)
from src.diff import compare_listings


def test_upsert_snapshot_and_diff(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    init_db(db)
    config_id = add_watch_config(
        "テスト区",
        "https://suumo.jp/jj/bukken/ichiran/JJ010FJ001/?ar=030&bs=011",
        db_path=db,
    )

    day1 = [
        ListingRow("1", "A", "", 5000, 60.0, "2LDK", "", "", "https://example/1"),
        ListingRow("2", "B", "", 6000, 70.0, "3LDK", "", "", "https://example/2"),
    ]
    day2 = [
        ListingRow("1", "A", "", 4800, 60.0, "2LDK", "", "", "https://example/1"),
        ListingRow("3", "C", "", 5500, 55.0, "1LDK", "", "", "https://example/3"),
    ]

    upsert_snapshot(config_id, day1, snapshot_date=date(2026, 9, 1), db_path=db)
    upsert_snapshot(config_id, day2, snapshot_date=date(2026, 9, 2), db_path=db)

    current, previous = get_latest_two_snapshots(config_id, db_path=db)
    assert current is not None and previous is not None
    assert current.snapshot_date == "2026-09-02"
    assert previous.snapshot_date == "2026-09-01"

    diff = compare_listings(
        get_listings_for_snapshot(previous.id, db_path=db),
        get_listings_for_snapshot(current.id, db_path=db),
    )
    assert diff.drop_count == 1
    assert diff.new_count == 1
    assert diff.removed_count == 1

    # Same-day upsert replaces listings
    upsert_snapshot(
        config_id,
        [ListingRow("9", "Z", "", 1000, 40.0, "1K", "", "", "https://example/9")],
        snapshot_date=date(2026, 9, 2),
        db_path=db,
    )
    current, _ = get_latest_two_snapshots(config_id, db_path=db)
    assert current is not None
    listings = get_listings_for_snapshot(current.id, db_path=db)
    assert len(listings) == 1
    assert listings[0].property_id == "9"
