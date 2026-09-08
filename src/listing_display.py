"""Display labels for listings (ward, price band, building age)."""

from __future__ import annotations

import re

WARD_SUFFIX = " 中古マンション"
BUILT_YEAR_PATTERN = re.compile(r"(1[89]\d{2}|20\d{2})")

PRICE_BANDS: tuple[tuple[int, str], ...] = (
    (3000, "〜3000万円"),
    (5000, "3000万〜5000万円"),
    (8000, "5000万〜8000万円"),
    (10000, "8000万〜1億円"),
    (20000, "1億〜2億円"),
)
PRICE_BAND_OVER = "2億円〜"


def ward_label(ward_name: str) -> str:
    text = (ward_name or "").strip()
    if text.endswith(WARD_SUFFIX):
        text = text[: -len(WARD_SUFFIX)].strip()
    return text or "-"


def price_band(price_man: int | None) -> str:
    if price_man is None:
        return "-"
    for limit, label in PRICE_BANDS:
        if price_man < limit:
            return label
    return PRICE_BAND_OVER


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
