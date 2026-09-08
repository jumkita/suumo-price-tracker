"""Per-property price history across archived daily snapshots."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from src.diff import format_man
from src.history import load_dated_payloads
from src.scraper.suumo import listing_key

__all__ = [
    "PricePoint",
    "build_property_histories",
    "changed_histories",
    "format_price_history",
    "history_for_listing",
    "listing_key",
]


@dataclass(frozen=True)
class PricePoint:
    snapshot_date: str
    price_man: int | None
    name: str
    url: str
    ward_name: str


def build_property_histories(publish_dir) -> dict[str, list[PricePoint]]:
    histories: dict[str, list[PricePoint]] = defaultdict(list)
    for payload in load_dated_payloads(publish_dir):
        day = str(payload.get("snapshot_date") or "")
        if not day:
            continue
        for block in payload.get("configs") or []:
            ward_name = str(block.get("name") or "")
            for item in block.get("listings") or []:
                url = str(item.get("url") or "")
                key = listing_key(url, str(item.get("property_id") or ""))
                if not key:
                    continue
                histories[key].append(
                    PricePoint(
                        snapshot_date=day,
                        price_man=item.get("price_man"),
                        name=str(item.get("name") or ""),
                        url=url,
                        ward_name=ward_name,
                    )
                )
    for key, points in histories.items():
        points.sort(key=lambda item: item.snapshot_date)
        histories[key] = _unique_days(points)
    return dict(histories)


def _unique_days(points: list[PricePoint]) -> list[PricePoint]:
    best: dict[str, PricePoint] = {}
    for point in points:
        current = best.get(point.snapshot_date)
        if current is None:
            best[point.snapshot_date] = point
            continue
        if _price_sort_key(point) < _price_sort_key(current):
            best[point.snapshot_date] = point
    return [best[day] for day in sorted(best)]


def _price_sort_key(point: PricePoint) -> tuple[int, int]:
    if point.price_man is None:
        return (1, 10**12)
    return (0, point.price_man)


def format_price_history(points: list[PricePoint] | list[tuple[str, int | None]]) -> str:
    if not points:
        return "-"
    parts: list[str] = []
    for item in points:
        if isinstance(item, PricePoint):
            day = item.snapshot_date
            price = item.price_man
        else:
            day, price = item
        parts.append(f"{day} {format_man(price)}")
    return " → ".join(parts)


def changed_histories(
    histories: dict[str, list[PricePoint]],
) -> dict[str, list[PricePoint]]:
    changed: dict[str, list[PricePoint]] = {}
    for key, points in histories.items():
        prices = [p.price_man for p in points if p.price_man is not None]
        if len(points) >= 2 and len(set(prices)) >= 2:
            changed[key] = points
    return changed


def history_for_listing(
    histories: dict[str, list[PricePoint]],
    url: str,
    property_id: str = "",
) -> list[PricePoint]:
    return histories.get(listing_key(url, property_id), [])
