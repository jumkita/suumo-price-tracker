"""Fetch published JSON from GitHub and import into local SQLite."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from src.db import (
    ListingRow,
    add_watch_config,
    find_watch_config_by_name,
    init_db,
    upsert_snapshot,
)

DEFAULT_REMOTE_JSON_URL = (
    "https://raw.githubusercontent.com/jumkita/suumo-price-tracker/main/"
    "data/published/daily_prices.json"
)


@dataclass(frozen=True)
class SyncResult:
    source_url: str
    snapshot_date: str
    config_count: int
    listing_count: int
    generated_at: str | None


def resolve_remote_json_url(override: str | None = None) -> str:
    if override and override.strip():
        return override.strip()
    for key in ("DAILY_PRICES_JSON_URL", "SUUMO_PRICES_JSON_URL"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return DEFAULT_REMOTE_JSON_URL


def with_cache_buster(url: str, ts: int | None = None) -> str:
    if not url:
        return url
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))
    query["_ts"] = str(ts if ts is not None else int(time.time()))
    return urlunparse(parsed._replace(query=urlencode(query)))


def dated_url_for(latest_url: str, snapshot_date: str) -> str:
    """Convert .../daily_prices.json to .../daily_prices_YYYY-MM-DD.json."""
    if latest_url.endswith("daily_prices.json"):
        return latest_url[: -len("daily_prices.json")] + f"daily_prices_{snapshot_date}.json"
    return latest_url


def fetch_json(url: str, timeout: float = 60.0) -> dict[str, Any]:
    busted = with_cache_buster(url)
    headers = {"Cache-Control": "no-cache", "Pragma": "no-cache"}
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        response = client.get(busted)
        response.raise_for_status()
        return response.json()


def _listings_from_payload(config_block: dict[str, Any]) -> list[ListingRow]:
    rows: list[ListingRow] = []
    for item in config_block.get("listings") or []:
        station = str(item.get("station") or "")
        walk = item.get("walk_minutes")
        rows.append(
            ListingRow(
                property_id=str(item["property_id"]),
                name=str(item.get("name") or ""),
                address=str(item.get("address") or ""),
                price_man=item.get("price_man"),
                area_sqm=item.get("area_sqm"),
                layout=str(item.get("layout") or ""),
                built_year=str(item.get("built_year") or ""),
                station=station,
                url=str(item.get("url") or ""),
                walk_minutes=walk,
                floor=str(item.get("floor") or ""),
            )
        )
    return rows


def import_payload(payload: dict[str, Any], db_path: Path | None = None) -> SyncResult:
    init_db(db_path)
    snapshot_date = str(payload.get("snapshot_date") or "")
    if not snapshot_date:
        raise ValueError("payload missing snapshot_date")
    day = date.fromisoformat(snapshot_date)

    imported_listings = 0
    imported_configs = 0
    for block in payload.get("configs") or []:
        name = str(block.get("name") or "").strip()
        search_url = str(block.get("search_url") or "").strip()
        if not name or not search_url:
            continue
        existing = find_watch_config_by_name(name, db_path=db_path)
        if existing is None:
            config_id = add_watch_config(
                name,
                search_url,
                max_pages=int(block.get("max_pages") or 50),
                db_path=db_path,
            )
        else:
            config_id = existing.id
        listings = _listings_from_payload(block)
        upsert_snapshot(config_id, listings, snapshot_date=day, db_path=db_path)
        imported_configs += 1
        imported_listings += len(listings)

    return SyncResult(
        source_url="",
        snapshot_date=snapshot_date,
        config_count=imported_configs,
        listing_count=imported_listings,
        generated_at=str(payload.get("generated_at") or "") or None,
    )


def sync_from_remote(
    url: str | None = None,
    *,
    db_path: Path | None = None,
    also_previous_day: bool = True,
) -> SyncResult:
    target = (url or resolve_remote_json_url()).strip()
    payload = fetch_json(target)
    result = import_payload(payload, db_path=db_path)

    if also_previous_day:
        # Best-effort: import previous dated file when present for diffs.
        from datetime import timedelta

        day = date.fromisoformat(result.snapshot_date)
        prev = (day - timedelta(days=1)).isoformat()
        prev_url = dated_url_for(target, prev)
        try:
            prev_payload = fetch_json(prev_url)
            import_payload(prev_payload, db_path=db_path)
        except Exception:
            pass

    return SyncResult(
        source_url=target,
        snapshot_date=result.snapshot_date,
        config_count=result.config_count,
        listing_count=result.listing_count,
        generated_at=result.generated_at,
    )


def load_local_published(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
