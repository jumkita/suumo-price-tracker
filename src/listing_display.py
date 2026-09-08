"""Display labels for listings (ward, price band, building age)."""

from __future__ import annotations

import re
from typing import Literal, Never, get_args

WARD_SUFFIX = " 中古マンション"
BUILT_YEAR_PATTERN = re.compile(r"(1[89]\d{2}|20\d{2})")

PRICE_UNIT_MAN = 1000
AREA_UNIT_SQM = 10
WalkFilterToken = Literal["lte5", "lte10", "lte15", "lte20", "gte20"]
WALK_FILTERS: tuple[tuple[WalkFilterToken, str], ...] = (
    ("lte5", "5分以内"),
    ("lte10", "10分以内"),
    ("lte15", "15分以内"),
    ("lte20", "20分以内"),
    ("gte20", "20分以上"),
)


def ward_label(ward_name: str) -> str:
    text = (ward_name or "").strip()
    if text.endswith(WARD_SUFFIX):
        text = text[: -len(WARD_SUFFIX)].strip()
    return text or "-"


def _man_label(value: int) -> str:
    if value >= 10000:
        oku = value // 10000
        man = value % 10000
        if man == 0:
            return f"{oku}億円"
        return f"{oku}億{man}万円"
    return f"{value}万円"


def price_band_start(price_man: int | None, unit: int = PRICE_UNIT_MAN) -> int | None:
    if price_man is None:
        return None
    return (int(price_man) // unit) * unit


def price_band(price_man: int | None, unit: int = PRICE_UNIT_MAN) -> str:
    start = price_band_start(price_man, unit)
    if start is None:
        return "-"
    end = start + unit
    if start <= 0:
        return f"〜{_man_label(end)}"
    return f"{_man_label(start)}〜{_man_label(end)}"


def area_unit_band(area_sqm: float | None, unit: int = AREA_UNIT_SQM) -> str:
    if area_sqm is None:
        return "-"
    start = int(area_sqm // unit) * unit
    return f"{start}〜{start + unit}m2"


def walk_filter_label(token: str) -> str:
    for key, label in WALK_FILTERS:
        if key == token:
            return label
    return token


def walk_matches(minutes: int | None, token: str) -> bool:
    if minutes is None or token not in get_args(WalkFilterToken):
        return False
    known: WalkFilterToken = token  # type: ignore[assignment]
    match known:
        case "lte5":
            return minutes <= 5
        case "lte10":
            return minutes <= 10
        case "lte15":
            return minutes <= 15
        case "lte20":
            return minutes <= 20
        case "gte20":
            return minutes >= 20
        case _:
            unreachable: Never = known
            raise ValueError(unreachable)


def parse_built_year(built_year: str) -> int | None:
    match = BUILT_YEAR_PATTERN.search(built_year or "")
    if match is None:
        return None
    return int(match.group(1))


def built_age_years(built_year: str, snapshot_date: str) -> int | None:
    year = parse_built_year(built_year)
    if year is None or not snapshot_date or len(snapshot_date) < 4:
        return None
    try:
        snapshot_year = int(snapshot_date[:4])
    except ValueError:
        return None
    return max(0, snapshot_year - year)


def format_built_age(built_year: str, snapshot_date: str) -> str:
    age = built_age_years(built_year, snapshot_date)
    if age is None:
        return (built_year or "").strip() or "-"
    return f"築{age}年"
