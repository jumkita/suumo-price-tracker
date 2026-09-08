"""SUUMO search-result scraper for used condominiums."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from src.listing_fields import parse_floor_text, parse_walk_minutes

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; PriceTracker/1.0; +https://localhost; personal-use)"
)
DEFAULT_REQUEST_INTERVAL_SEC = 2.0
DEFAULT_MAX_PAGES = 10
MAX_RETRIES = 3
SUUMO_ORIGIN = "https://suumo.jp"

PROPERTY_ID_PATTERNS = (
    re.compile(r"/nc_(\d+)/"),
    re.compile(r"[?&]nc=(\d+)"),
    re.compile(r"/bj/(\d+)/"),
)


@dataclass(frozen=True)
class Listing:
    property_id: str
    name: str
    address: str
    price_man: int | None
    area_sqm: float | None
    layout: str
    built_year: str
    station: str
    url: str
    walk_minutes: int | None = None
    floor: str = ""


FetchFunc = Callable[[str], str]


def normalize_search_url(url: str) -> str:
    """Strip page number so we can rebuild pagination ourselves."""
    parsed = urlparse(url.strip())
    query = parse_qs(parsed.query, keep_blank_values=True)
    query.pop("pn", None)
    query.pop("page", None)
    # Keep first value for each key for stable encoding
    flat = {key: values[0] for key, values in query.items()}
    return urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc or "suumo.jp",
            parsed.path,
            parsed.params,
            urlencode(flat),
            "",
        )
    )


def build_page_url(base_url: str, page: int) -> str:
    """Build paginated URL. SUUMO mid-sale search uses `page=` (not `pn=`)."""
    normalized = normalize_search_url(base_url)
    if page <= 1:
        return normalized
    parsed = urlparse(normalized)
    query = parse_qs(parsed.query, keep_blank_values=True)
    flat = {key: values[0] for key, values in query.items()}
    flat["page"] = str(page)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(flat),
            "",
        )
    )


def extract_property_id(href: str) -> str | None:
    for pattern in PROPERTY_ID_PATTERNS:
        match = pattern.search(href)
        if match:
            return match.group(1)
    # Fallback: hash of path so we still track something stable
    path = urlparse(href).path.rstrip("/")
    if path:
        return path.rsplit("/", 1)[-1] or None
    return None


def absolute_url(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"{SUUMO_ORIGIN}{href}"
    return f"{SUUMO_ORIGIN}/{href}"


def parse_price_man(text: str) -> int | None:
    """Parse SUUMO price text into 万円 integer."""
    cleaned = text.replace(",", "").replace("，", "").replace(" ", "").strip()
    if not cleaned or cleaned in {"-", "－", "―"}:
        return None

    total = 0
    oku = re.search(r"(\d+(?:\.\d+)?)億", cleaned)
    if oku:
        total += int(float(oku.group(1)) * 10000)

    man = re.search(r"(\d+(?:\.\d+)?)万", cleaned)
    if man:
        total += int(float(man.group(1)))
    elif not oku:
        digits = re.search(r"(\d+)", cleaned)
        if digits:
            total = int(digits.group(1))
        else:
            return None

    return total if total > 0 else None


def parse_area_sqm(text: str) -> float | None:
    cleaned = text.replace(",", "").replace("㎡", "m2").replace("m²", "m2")
    match = re.search(r"(\d+(?:\.\d+)?)\s*m2", cleaned, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if match:
        return float(match.group(1))
    return None


def _text(node: Tag | None) -> str:
    if node is None:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())


def _dl_map(unit: Tag) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for dl in unit.find_all("dl"):
        dt = dl.find("dt")
        dd = dl.find("dd")
        if dt and dd:
            key = _text(dt)
            if key:
                mapping[key] = _text(dd)
    return mapping


def _pick(mapping: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in mapping and mapping[key]:
            return mapping[key]
    for key, value in mapping.items():
        for candidate in keys:
            if candidate in key and value:
                return value
    return ""


def clean_property_name(name: str) -> str:
    """Prefer bare building names; strip catch-copy suffixes."""
    text = " ".join((name or "").split()).strip()
    if not text:
        return ""
    for sep in ("◆", "■", "｜", "|"):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
    return text.strip(" ….")


def parse_listing_unit(unit: Tag) -> Listing | None:
    title = unit.select_one("h2.property_unit-title a") or unit.select_one(
        ".property_unit-title a"
    )
    if title is None:
        return None

    href = title.get("href") or ""
    if not isinstance(href, str) or not href:
        return None

    property_id = extract_property_id(href)
    if not property_id:
        return None

    url = absolute_url(href)
    mapping = _dl_map(unit)

    # h2 is usually agency catch-copy; 物件名 is the real building name.
    name = clean_property_name(_pick(mapping, "物件名")) or clean_property_name(
        _text(title)
    )

    price_text = _pick(mapping, "販売価格", "価格")
    if not price_text:
        price_span = unit.select_one("span.dottable-value")
        price_text = _text(price_span)

    station = _pick(mapping, "沿線・駅", "交通", "最寄り駅")
    floor = parse_floor_text(
        _pick(mapping, "所在階", "所在階/構造・階建", "階"),
        name,
    )
    return Listing(
        property_id=property_id,
        name=name or f"物件{property_id}",
        address=_pick(mapping, "所在地", "住所"),
        price_man=parse_price_man(price_text),
        area_sqm=parse_area_sqm(_pick(mapping, "専有面積", "面積")),
        layout=_pick(mapping, "間取り"),
        built_year=_pick(mapping, "築年月", "築年"),
        station=station,
        url=url,
        walk_minutes=parse_walk_minutes(station),
        floor=floor,
    )


def parse_search_html(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    root = soup.select_one("#js-bukkenList") or soup

    units = root.select("div.property_unit")
    if not units:
        units = root.select("div.dottable.dottable--cassette")

    listings: list[Listing] = []
    seen: set[str] = set()
    for unit in units:
        listing = parse_listing_unit(unit)
        if listing is None:
            continue
        if listing.property_id in seen:
            continue
        seen.add(listing.property_id)
        listings.append(listing)
    return listings


def default_fetch(url: str, timeout: float = 30.0) -> str:
    last_error: Exception | None = None
    headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept-Language": "ja,en;q=0.8"}
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
                response = client.get(url)
                response.raise_for_status()
                response.encoding = response.encoding or "utf-8"
                return response.text
        except Exception as exc:  # noqa: BLE001 - surface as scrape error upstream
            last_error = exc
            logger.warning("fetch failed attempt=%s url=%s error=%s", attempt, url, exc)
            if attempt < MAX_RETRIES:
                time.sleep(attempt)
    assert last_error is not None
    raise last_error


def scrape_search_results(
    search_url: str,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    request_interval_sec: float = DEFAULT_REQUEST_INTERVAL_SEC,
    fetch: FetchFunc | None = None,
) -> list[Listing]:
    """Fetch paginated SUUMO search results with polite delays."""
    if max_pages < 1:
        raise ValueError("max_pages must be >= 1")

    fetch_html = fetch or default_fetch
    all_listings: list[Listing] = []
    seen: set[str] = set()

    for page in range(1, max_pages + 1):
        page_url = build_page_url(search_url, page)
        logger.info("scraping page=%s url=%s", page, page_url)
        html = fetch_html(page_url)
        page_listings = parse_search_html(html)
        if not page_listings:
            logger.info("no listings on page=%s; stopping", page)
            break

        new_count = 0
        for listing in page_listings:
            if listing.property_id in seen:
                continue
            seen.add(listing.property_id)
            all_listings.append(listing)
            new_count += 1

        if new_count == 0:
            logger.info("no new listings on page=%s; stopping", page)
            break

        if page < max_pages:
            time.sleep(request_interval_sec)

    return all_listings
