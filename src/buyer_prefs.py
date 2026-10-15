"""Buyer search prefs so highlights are not just citywide extremes."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.diff import PriceChange, select_highlight_drops
from src.listing_display import built_age_years, ward_label
from src.wards import TOKYO_23_WARDS, TOKYO_CITIES, AreaKind

LAYOUT_CHOICES: tuple[str, ...] = (
    "1K",
    "1DK",
    "1LDK",
    "2DK",
    "2LDK",
    "3LDK",
    "4LDK+",
)
BUILT_AGE_CHOICES: tuple[int, ...] = (10, 15, 20, 25, 30, 40)
MIN_AREA_CHOICES: tuple[int, ...] = (40, 50, 55, 60, 70, 80)
MAX_WALK_CHOICES: tuple[int, ...] = (5, 10, 15, 20)
LAYOUT_TOKEN_PATTERN = re.compile(r"(\d+)(S?L?D?K)", re.IGNORECASE)


@dataclass(frozen=True)
class BuyerPrefs:
    wards: tuple[str, ...] = ()
    price_min_man: int | None = None
    price_max_man: int | None = None
    max_built_age: int | None = None
    min_area_sqm: float | None = None
    max_walk_minutes: int | None = None
    layouts: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return not (
            self.wards
            or self.price_min_man is not None
            or self.price_max_man is not None
            or self.max_built_age is not None
            or self.min_area_sqm is not None
            or self.max_walk_minutes is not None
            or self.layouts
        )

    def normalized(self) -> BuyerPrefs:
        low = self.price_min_man
        high = self.price_max_man
        if low is not None and high is not None and low > high:
            low, high = high, low
        wards = tuple(dict.fromkeys(item for item in self.wards if item and item != "-"))
        layouts = tuple(dict.fromkeys(item for item in self.layouts if item))
        return BuyerPrefs(
            wards=wards,
            price_min_man=low,
            price_max_man=high,
            max_built_age=self.max_built_age,
            min_area_sqm=self.min_area_sqm,
            max_walk_minutes=self.max_walk_minutes,
            layouts=layouts,
        )


def area_pref_choices() -> tuple[tuple[str, AreaKind], ...]:
    wards = tuple((name, "ward") for name, _code in TOKYO_23_WARDS)
    cities = tuple((name, "city") for name, _code in TOKYO_CITIES)
    return wards + cities


def parse_layout_token(text: str) -> tuple[int, str] | None:
    match = LAYOUT_TOKEN_PATTERN.search((text or "").upper().replace(" ", ""))
    if match is None:
        return None
    kind = match.group(2).upper().replace("S", "")
    return int(match.group(1)), kind


def layout_matches(listing_layout: str, wanted: tuple[str, ...]) -> bool:
    if not wanted:
        return True
    got = parse_layout_token(listing_layout)
    if got is None:
        return False
    rooms, kind = got
    for raw in wanted:
        plus = raw.endswith("+")
        token = raw[:-1] if plus else raw
        need = parse_layout_token(token)
        if need is None:
            continue
        need_rooms, need_kind = need
        if plus:
            if rooms >= need_rooms and need_kind in kind:
                return True
            continue
        if rooms == need_rooms and kind == need_kind:
            return True
    return False


def drop_matches_prefs(
    change: PriceChange,
    prefs: BuyerPrefs,
    snapshot_date: str,
) -> bool:
    prefs = prefs.normalized()
    if prefs.is_empty():
        return True
    ward = ward_label(change.ward_name)
    if prefs.wards and ward not in prefs.wards:
        return False
    price = change.new_price_man
    if prefs.price_min_man is not None and (price is None or price < prefs.price_min_man):
        return False
    if prefs.price_max_man is not None and (price is None or price > prefs.price_max_man):
        return False
    if prefs.max_built_age is not None:
        age = built_age_years(change.built_year, snapshot_date)
        if age is None or age > prefs.max_built_age:
            return False
    if prefs.min_area_sqm is not None:
        if change.area_sqm is None or change.area_sqm < prefs.min_area_sqm:
            return False
    if prefs.max_walk_minutes is not None:
        if change.walk_minutes is None or change.walk_minutes > prefs.max_walk_minutes:
            return False
    if prefs.layouts and not layout_matches(change.layout, prefs.layouts):
        return False
    return True


def filter_drops_by_prefs(
    drops: list[PriceChange],
    prefs: BuyerPrefs,
    snapshot_date: str,
) -> list[PriceChange]:
    prefs = prefs.normalized()
    if prefs.is_empty():
        return list(drops)
    return [item for item in drops if drop_matches_prefs(item, prefs, snapshot_date)]


def select_pref_highlights(
    drops: list[PriceChange],
    limit: int,
    prefs: BuyerPrefs,
    snapshot_date: str,
) -> list[PriceChange]:
    return select_highlight_drops(
        filter_drops_by_prefs(drops, prefs, snapshot_date),
        limit,
    )
