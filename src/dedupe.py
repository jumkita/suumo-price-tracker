"""Collapse multi-agency duplicate listings into one cheapest unit."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict

from src.scraper.suumo import Listing

# Marketing / agency noise often appended to titles
_NOISE_PATTERNS = (
    re.compile(r"[【\[（(][^】\]）)]*[】\]）)]"),
    re.compile(r"(仲介手数料無料|リノベ|フルリノベ|リフォーム済|即入居可)"),
)


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.lower()
    for pattern in _NOISE_PATTERNS:
        text = pattern.sub("", text)
    text = re.sub(r"[\s\u3000・･./／\-ー_]+", "", text)
    return text.strip()


def property_fingerprint(listing: Listing) -> str:
    """Stable identity across agencies for the same physical unit."""
    area_key = (
        f"{round(listing.area_sqm, 1):.1f}" if listing.area_sqm is not None else ""
    )
    payload = "|".join(
        [
            normalize_text(listing.name),
            normalize_text(listing.address),
            normalize_text(listing.layout),
            area_key,
        ]
    )
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return f"fp_{digest}"


def _price_sort_key(listing: Listing) -> tuple[int, int]:
    # Prefer known prices; among them, cheapest first.
    if listing.price_man is None:
        return (1, 10**12)
    return (0, listing.price_man)


def collapse_to_cheapest(listings: list[Listing]) -> list[Listing]:
    """Keep one row per physical property, using the lowest asking price."""
    groups: dict[str, list[Listing]] = defaultdict(list)
    for listing in listings:
        groups[property_fingerprint(listing)].append(listing)

    collapsed: list[Listing] = []
    for fingerprint, group in groups.items():
        best = sorted(group, key=_price_sort_key)[0]
        collapsed.append(
            Listing(
                property_id=fingerprint,
                name=best.name,
                address=best.address,
                price_man=best.price_man,
                area_sqm=best.area_sqm,
                layout=best.layout,
                built_year=best.built_year,
                station=best.station,
                url=best.url,
                walk_minutes=best.walk_minutes,
                floor=best.floor,
            )
        )

    collapsed.sort(key=lambda item: (item.name, item.property_id))
    return collapsed
