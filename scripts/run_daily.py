#!/usr/bin/env python
"""Run daily scrape for all enabled watch configs."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import init_db, list_watch_configs
from src.pipeline import run_all_enabled


def _configure_logging() -> Path:
    log_dir = ROOT / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"daily_{datetime.now():%Y%m%d}.log"
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )
    return log_path


def main() -> int:
    parser = argparse.ArgumentParser(description="SUUMO daily price scrape")
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Seconds between page requests (default: 2.0)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Optional SQLite path",
    )
    args = parser.parse_args()

    log_path = _configure_logging()
    logging.info("log_file=%s", log_path)

    init_db(args.db)
    configs = [c for c in list_watch_configs(args.db) if c.enabled]
    if not configs:
        logging.warning("有効な監視設定がありません。Streamlitで検索URLを登録してください。")
        return 1

    results = run_all_enabled(db_path=args.db, request_interval_sec=args.interval)
    exit_code = 0
    for result in results:
        if result.error:
            exit_code = 1
            logging.error("[%s] failed: %s", result.config.name, result.error)
            continue
        drop = result.diff.drop_count if result.diff else 0
        new = result.diff.new_count if result.diff else 0
        logging.info(
            "[%s] raw=%s deduped=%s drops=%s new=%s snapshot_id=%s",
            result.config.name,
            result.raw_listing_count,
            result.listing_count,
            drop,
            new,
            result.snapshot_id,
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
