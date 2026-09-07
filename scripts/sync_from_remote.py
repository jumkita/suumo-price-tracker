#!/usr/bin/env python
"""Pull latest published JSON into local SQLite."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.remote_sync import sync_from_remote


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync prices JSON into SQLite")
    parser.add_argument("--url", default=None)
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()
    result = sync_from_remote(args.url, db_path=args.db)
    print(
        f"synced date={result.snapshot_date} configs={result.config_count} "
        f"listings={result.listing_count} from {result.source_url}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
