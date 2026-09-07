"""Bootstrap a previous-day snapshot so diffs work from day one."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import (
    get_listings_for_snapshot,
    get_latest_two_snapshots,
    init_db,
    list_watch_configs,
    upsert_snapshot,
)
from src.publish import publish_daily

JST = ZoneInfo("Asia/Tokyo")


def bootstrap_previous_day(db_path: Path | None = None) -> int:
    """If a config has only one snapshot, copy it to the previous calendar day."""
    init_db(db_path)
    created = 0
    for config in list_watch_configs(db_path=db_path):
        current, previous = get_latest_two_snapshots(config.id, db_path=db_path)
        if current is None or previous is not None:
            continue
        current_day = date.fromisoformat(current.snapshot_date)
        prev_day = current_day - timedelta(days=1)
        listings = get_listings_for_snapshot(current.id, db_path=db_path)
        upsert_snapshot(
            config.id,
            listings,
            snapshot_date=prev_day,
            db_path=db_path,
        )
        created += 1
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap previous-day snapshots")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--export", action="store_true", help="Also export published JSON")
    args = parser.parse_args()

    created = bootstrap_previous_day(db_path=args.db)
    print(f"bootstrapped_configs={created}")
    if args.export:
        today = datetime.now(JST).date()
        yesterday = today - timedelta(days=1)
        for day in (yesterday, today):
            try:
                dated, latest, payload = publish_daily(
                    snapshot_date=day,
                    db_path=args.db,
                )
                print(
                    f"exported {day} listings={payload['listing_count']} -> {dated.name}"
                )
            except RuntimeError as exc:
                print(f"skip {day}: {exc}")
        print(f"latest -> {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
