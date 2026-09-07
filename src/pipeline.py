"""Orchestrate scrape -> store -> diff for one or all watch configs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.db import (
    ListingRow,
    WatchConfig,
    average_price_by_date,
    get_latest_two_snapshots,
    get_listings_for_snapshot,
    get_watch_config,
    init_db,
    list_watch_configs,
    upsert_snapshot,
)
from src.dedupe import collapse_to_cheapest
from src.diff import DiffResult, average_price, compare_listings
from src.scraper.suumo import Listing, scrape_search_results

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunResult:
    config: WatchConfig
    snapshot_id: int
    listing_count: int
    raw_listing_count: int
    diff: DiffResult | None
    current_avg_price: float | None
    previous_avg_price: float | None
    error: str | None = None


def _to_row(listing: Listing) -> ListingRow:
    return ListingRow(
        property_id=listing.property_id,
        name=listing.name,
        address=listing.address,
        price_man=listing.price_man,
        area_sqm=listing.area_sqm,
        layout=listing.layout,
        built_year=listing.built_year,
        station=listing.station,
        url=listing.url,
    )


def load_diff_for_config(
    config_id: int,
    db_path: Path | None = None,
) -> tuple[WatchConfig | None, DiffResult | None, float | None, float | None]:
    config = get_watch_config(config_id, db_path=db_path)
    if config is None:
        return None, None, None, None

    current_meta, previous_meta = get_latest_two_snapshots(config_id, db_path=db_path)
    if current_meta is None:
        return config, None, None, None

    current = get_listings_for_snapshot(current_meta.id, db_path=db_path)
    current_avg = average_price(current)
    if previous_meta is None:
        return config, None, current_avg, None

    previous = get_listings_for_snapshot(previous_meta.id, db_path=db_path)
    diff = compare_listings(previous, current)
    return config, diff, current_avg, average_price(previous)


def run_config(
    config_id: int,
    *,
    snapshot_date: date | None = None,
    db_path: Path | None = None,
    request_interval_sec: float = 2.0,
) -> RunResult:
    init_db(db_path)
    config = get_watch_config(config_id, db_path=db_path)
    if config is None:
        raise ValueError(f"watch config not found: {config_id}")

    try:
        scraped = scrape_search_results(
            config.search_url,
            max_pages=config.max_pages,
            request_interval_sec=request_interval_sec,
        )
        deduped = collapse_to_cheapest(scraped)
        rows = [_to_row(item) for item in deduped]
        logger.info(
            "config_id=%s raw=%s deduped=%s removed_dupes=%s",
            config_id,
            len(scraped),
            len(deduped),
            len(scraped) - len(deduped),
        )
        snapshot_id = upsert_snapshot(
            config.id,
            rows,
            snapshot_date=snapshot_date,
            db_path=db_path,
        )
        _, diff, current_avg, previous_avg = load_diff_for_config(
            config.id,
            db_path=db_path,
        )
        return RunResult(
            config=config,
            snapshot_id=snapshot_id,
            listing_count=len(rows),
            raw_listing_count=len(scraped),
            diff=diff,
            current_avg_price=current_avg,
            previous_avg_price=previous_avg,
        )
    except Exception as exc:  # noqa: BLE001 - capture for UI/CLI reporting
        logger.exception("failed to run config_id=%s", config_id)
        return RunResult(
            config=config,
            snapshot_id=0,
            listing_count=0,
            raw_listing_count=0,
            diff=None,
            current_avg_price=None,
            previous_avg_price=None,
            error=str(exc),
        )


def run_all_enabled(
    *,
    snapshot_date: date | None = None,
    db_path: Path | None = None,
    request_interval_sec: float = 2.0,
) -> list[RunResult]:
    init_db(db_path)
    results: list[RunResult] = []
    for config in list_watch_configs(db_path=db_path):
        if not config.enabled:
            continue
        results.append(
            run_config(
                config.id,
                snapshot_date=snapshot_date,
                db_path=db_path,
                request_interval_sec=request_interval_sec,
            )
        )
    return results


def price_history(
    config_id: int,
    db_path: Path | None = None,
) -> list[tuple[str, float]]:
    return average_price_by_date(config_id, db_path=db_path)
