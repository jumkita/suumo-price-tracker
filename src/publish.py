"""Publish daily snapshots as JSON for GitHub / Streamlit Cloud."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.db import (
    ListingRow,
    get_listings_for_snapshot,
    init_db,
    list_snapshots,
    list_watch_configs,
    resolve_db_path,
)
from src.publish_guard import assert_publish_not_too_thin

JST = ZoneInfo("Asia/Tokyo")
DEFAULT_PUBLISH_DIR = Path(__file__).resolve().parent.parent / "data" / "published"


def listing_to_dict(row: ListingRow) -> dict:
    return {
        "property_id": row.property_id,
        "name": row.name,
        "address": row.address,
        "price_man": row.price_man,
        "area_sqm": row.area_sqm,
        "layout": row.layout,
        "built_year": row.built_year,
        "station": row.station,
        "walk_minutes": row.walk_minutes,
        "floor": row.floor,
        "url": row.url,
    }


def build_daily_payload(
    *,
    snapshot_date: date | None = None,
    db_path: Path | None = None,
) -> dict:
    init_db(db_path)
    day = snapshot_date or datetime.now(JST).date()
    day_text = day.isoformat()
    configs_out: list[dict] = []

    for config in list_watch_configs(db_path=db_path):
        snaps = list_snapshots(config.id, db_path=db_path)
        match = next((s for s in snaps if s.snapshot_date == day_text), None)
        if match is None:
            continue
        listings = get_listings_for_snapshot(match.id, db_path=db_path)
        configs_out.append(
            {
                "name": config.name,
                "search_url": config.search_url,
                "max_pages": config.max_pages,
                "enabled": config.enabled,
                "listing_count": len(listings),
                "fetched_at": match.fetched_at,
                "listings": [listing_to_dict(item) for item in listings],
            }
        )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(JST).isoformat(timespec="seconds"),
        "snapshot_date": day_text,
        "timezone": "Asia/Tokyo",
        "db_path": str(resolve_db_path(db_path)),
        "config_count": len(configs_out),
        "listing_count": sum(c["listing_count"] for c in configs_out),
        "configs": configs_out,
    }


def write_published_json(
    payload: dict,
    publish_dir: Path | None = None,
    *,
    skip_thin_guard: bool = False,
) -> tuple[Path, Path]:
    out_dir = publish_dir or DEFAULT_PUBLISH_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    dated = out_dir / f"daily_prices_{payload['snapshot_date']}.json"
    latest = out_dir / "daily_prices.json"
    if not skip_thin_guard:
        assert_publish_not_too_thin(payload, latest)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    dated.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return dated, latest


def publish_daily(
    *,
    snapshot_date: date | None = None,
    db_path: Path | None = None,
    publish_dir: Path | None = None,
    skip_thin_guard: bool = False,
) -> tuple[Path, Path, dict]:
    payload = build_daily_payload(snapshot_date=snapshot_date, db_path=db_path)
    if not payload["configs"]:
        raise RuntimeError(
            f"no snapshots found for {payload['snapshot_date']}; run scrape first"
        )
    dated, latest = write_published_json(
        payload,
        publish_dir=publish_dir,
        skip_thin_guard=skip_thin_guard,
    )
    return dated, latest, payload
