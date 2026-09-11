"""Citywide (all wards) price-change aggregation."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from src.db import ListingRow
from src.diff import PriceChange, compare_listings
from src.listing_display import ward_label
from src.listing_fields import parse_walk_minutes
from src.scraper.suumo import listing_key


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


@dataclass(frozen=True)
class WardTotals:
    ward: str
    prev_count: int
    cur_count: int
    matched: int
    drop_count: int
    rise_count: int
    new_count: int
    removed_count: int
    unchanged_count: int
    drop_yen: int

    @property
    def drop_rate_pct(self) -> float:
        if self.matched == 0:
            return 0.0
        return 100.0 * self.drop_count / self.matched


@dataclass
class CitywideComparison:
    drops: list[PriceChange] = field(default_factory=list)
    rises: list[PriceChange] = field(default_factory=list)
    new_count: int = 0
    removed_count: int = 0
    unchanged_count: int = 0
    matched_count: int = 0
    wards: list[WardTotals] = field(default_factory=list)
    prev_listing_count: int = 0
    cur_listing_count: int = 0
    prev_avg_man: float | None = None
    cur_avg_man: float | None = None
    matched_avg_old: float | None = None
    matched_avg_new: float | None = None
    removed_avg_man: float | None = None


def _rows(block: dict[str, Any]) -> list[ListingRow]:
    return [listing_from_dict(item) for item in block.get("listings") or []]


def _mean(values: list[int] | list[float]) -> float | None:
    if not values:
        return None
    return float(mean(values))


def _listing_prices(payload: dict[str, Any] | None) -> list[int]:
    if payload is None:
        return []
    prices: list[int] = []
    for block in payload.get("configs") or []:
        for item in block.get("listings") or []:
            price = item.get("price_man")
            if price is not None:
                prices.append(int(price))
    return prices


def compare_citywide(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> CitywideComparison | None:
    if previous is None:
        return None

    prev_map = {
        str(block.get("name") or ""): block for block in previous.get("configs") or []
    }
    drops: list[PriceChange] = []
    rises: list[PriceChange] = []
    wards: list[WardTotals] = []
    unchanged = 0
    new_count = 0
    removed_count = 0
    matched_old: list[int] = []
    matched_new: list[int] = []
    removed_prices: list[int] = []

    for block in current.get("configs") or []:
        ward_name = str(block.get("name") or "")
        prev_block = prev_map.get(ward_name)
        current_rows = _rows(block)
        previous_rows = _rows(prev_block) if prev_block is not None else []
        if not current_rows and not previous_rows:
            continue
        diff = compare_listings(previous_rows, current_rows, ward_name=ward_name)
        drops.extend(diff.price_drops)
        rises.extend(diff.price_rises)
        unchanged += diff.unchanged_count
        new_count += len(diff.new_listings)
        removed_count += len(diff.removed_listings)
        matched = diff.unchanged_count + len(diff.price_drops) + len(diff.price_rises)
        wards.append(
            WardTotals(
                ward=ward_label(ward_name),
                prev_count=len(previous_rows),
                cur_count=len(current_rows),
                matched=matched,
                drop_count=len(diff.price_drops),
                rise_count=len(diff.price_rises),
                new_count=len(diff.new_listings),
                removed_count=len(diff.removed_listings),
                unchanged_count=diff.unchanged_count,
                drop_yen=-sum(item.delta_man or 0 for item in diff.price_drops),
            )
        )
        _collect_price_pairs(
            previous_rows,
            current_rows,
            matched_old,
            matched_new,
            removed_prices,
        )

    drops.sort(
        key=lambda item: (
            item.delta_man if item.delta_man is not None else 0,
            item.name,
        )
    )
    rises.sort(
        key=lambda item: (
            -(item.delta_man if item.delta_man is not None else 0),
            item.name,
        )
    )
    return CitywideComparison(
        drops=drops,
        rises=rises,
        new_count=new_count,
        removed_count=removed_count,
        unchanged_count=unchanged,
        matched_count=unchanged + len(drops) + len(rises),
        wards=wards,
        prev_listing_count=int(previous.get("listing_count") or 0),
        cur_listing_count=int(current.get("listing_count") or 0),
        prev_avg_man=_mean(_listing_prices(previous)),
        cur_avg_man=_mean(_listing_prices(current)),
        matched_avg_old=_mean(matched_old),
        matched_avg_new=_mean(matched_new),
        removed_avg_man=_mean(removed_prices),
    )


def _collect_price_pairs(
    previous_rows: list[ListingRow],
    current_rows: list[ListingRow],
    matched_old: list[int],
    matched_new: list[int],
    removed_prices: list[int],
) -> None:
    prev_by_key = {listing_key(item.url, item.property_id): item for item in previous_rows}
    curr_by_key = {listing_key(item.url, item.property_id): item for item in current_rows}
    for key, prev in prev_by_key.items():
        curr = curr_by_key.get(key)
        if curr is None:
            if prev.price_man is not None:
                removed_prices.append(prev.price_man)
            continue
        if prev.price_man is not None and curr.price_man is not None:
            matched_old.append(prev.price_man)
            matched_new.append(curr.price_man)


def citywide_price_drops(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> list[PriceChange]:
    comparison = compare_citywide(current, previous)
    if comparison is None:
        return []
    return comparison.drops
