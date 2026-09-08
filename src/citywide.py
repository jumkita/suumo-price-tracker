"""Citywide (all wards) price-drop aggregation."""

from __future__ import annotations

from typing import Any

from src.db import ListingRow
from src.diff import PriceChange, compare_listings
from src.listing_fields import parse_walk_minutes


def listing_from_dict(item: dict[str, Any]) -> ListingRow:
    station = str(item.get("station") or "")
    walk = item.get("walk_minutes")
    if walk is None:
        walk = parse_walk_minutes(station)
    return ListingRow(
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


def citywide_price_drops(current: dict[str, Any], previous: dict[str, Any] | None) -> list[PriceChange]:
    if previous is None:
        return []

    prev_map = {
        str(block.get("name") or ""): block for block in previous.get("configs") or []
    }
    drops: list[PriceChange] = []
    for block in current.get("configs") or []:
        ward_name = str(block.get("name") or "")
        prev_block = prev_map.get(ward_name)
        if prev_block is None:
            continue
        current_rows = [listing_from_dict(item) for item in block.get("listings") or []]
        previous_rows = [
            listing_from_dict(item) for item in prev_block.get("listings") or []
        ]
        diff = compare_listings(previous_rows, current_rows, ward_name=ward_name)
        drops.extend(diff.price_drops)

    drops.sort(
        key=lambda item: (
            item.delta_man if item.delta_man is not None else 0,
            item.name,
        )
    )
    return drops
