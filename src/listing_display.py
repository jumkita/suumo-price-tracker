"""Display labels for listings (ward, price band)."""

from __future__ import annotations

WARD_SUFFIX = " 中古マンション"

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
