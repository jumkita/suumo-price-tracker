"""Daily snapshot diff helpers."""

from __future__ import annotations

from dataclasses import dataclass

from src.db import ListingRow
from src.listing_fields import parse_station_name, parse_walk_minutes


@dataclass(frozen=True)
class PriceChange:
    property_id: str
    name: str
    old_price_man: int | None
    new_price_man: int | None
    delta_man: int | None
    url: str
    address: str
    station: str
    station_name: str = ""
    walk_minutes: int | None = None
    area_sqm: float | None = None
    layout: str = ""
    floor: str = ""
    ward_name: str = ""


@dataclass(frozen=True)
class DiffResult:
    price_drops: list[PriceChange]
    price_rises: list[PriceChange]
    new_listings: list[ListingRow]
    removed_listings: list[ListingRow]
    unchanged_count: int

    @property
    def drop_count(self) -> int:
        return len(self.price_drops)

    @property
    def rise_count(self) -> int:
        return len(self.price_rises)

    @property
    def new_count(self) -> int:
        return len(self.new_listings)

    @property
    def removed_count(self) -> int:
        return len(self.removed_listings)


def _delta(old: int | None, new: int | None) -> int | None:
    if old is None or new is None:
        return None
    return new - old


def _to_change(
    prev: ListingRow,
    curr: ListingRow,
    delta: int | None,
    *,
    ward_name: str = "",
) -> PriceChange:
    walk = curr.walk_minutes
    if walk is None:
        walk = parse_walk_minutes(curr.station)
    return PriceChange(
        property_id=curr.property_id,
        name=curr.name,
        old_price_man=prev.price_man,
        new_price_man=curr.price_man,
        delta_man=delta,
        url=curr.url,
        address=curr.address,
        station=curr.station,
        station_name=parse_station_name(curr.station),
        walk_minutes=walk,
        area_sqm=curr.area_sqm,
        layout=curr.layout,
        floor=curr.floor or "",
        ward_name=ward_name,
    )


def compare_listings(
    previous: list[ListingRow],
    current: list[ListingRow],
    *,
    ward_name: str = "",
) -> DiffResult:
    prev_map = {item.property_id: item for item in previous}
    curr_map = {item.property_id: item for item in current}

    drops: list[PriceChange] = []
    rises: list[PriceChange] = []
    unchanged = 0

    for property_id, curr in curr_map.items():
        prev = prev_map.get(property_id)
        if prev is None:
            continue
        delta = _delta(prev.price_man, curr.price_man)
        change = _to_change(prev, curr, delta, ward_name=ward_name)
        if delta is None:
            unchanged += 1
        elif delta < 0:
            drops.append(change)
        elif delta > 0:
            rises.append(change)
        else:
            unchanged += 1

    drops.sort(key=lambda item: (item.delta_man if item.delta_man is not None else 0, item.name))
    rises.sort(
        key=lambda item: (
            -(item.delta_man if item.delta_man is not None else 0),
            item.name,
        )
    )

    new_listings = [
        curr for property_id, curr in curr_map.items() if property_id not in prev_map
    ]
    removed_listings = [
        prev for property_id, prev in prev_map.items() if property_id not in curr_map
    ]
    new_listings.sort(key=lambda item: item.name)
    removed_listings.sort(key=lambda item: item.name)

    return DiffResult(
        price_drops=drops,
        price_rises=rises,
        new_listings=new_listings,
        removed_listings=removed_listings,
        unchanged_count=unchanged,
    )


def average_price(listings: list[ListingRow]) -> float | None:
    prices = [item.price_man for item in listings if item.price_man is not None]
    if not prices:
        return None
    return sum(prices) / len(prices)


def format_man(value: int | None) -> str:
    if value is None:
        return "-"
    if value >= 10000:
        oku = value // 10000
        man = value % 10000
        if man == 0:
            return f"{oku}億円"
        return f"{oku}億{man}万円"
    return f"{value}万円"
