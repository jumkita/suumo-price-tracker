#!/usr/bin/env python
"""Export local SQLite snapshots to data/published/*.json."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.publish import publish_daily


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish daily prices JSON")
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    snapshot_date = date.fromisoformat(args.date) if args.date else None
    dated, latest, payload = publish_daily(
        snapshot_date=snapshot_date,
        db_path=args.db,
        publish_dir=args.out_dir,
    )
    print(
        f"wrote {dated} and {latest} "
        f"(configs={payload['config_count']} listings={payload['listing_count']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
