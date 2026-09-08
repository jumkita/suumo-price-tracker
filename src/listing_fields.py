"""Parse station / walk / floor text from SUUMO fields."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

FLOOR_PATTERNS = (
    re.compile(r"所在階[/／].*?(\d+階|B\d+階|地下\d+階)"),
    re.compile(r"(?<![0-9])(\d+階|B\d+階|地下\d+階)"),
)
WALK_PATTERN = re.compile(r"徒?歩\s*([0-9０-９]+)\s*分")
STATION_QUOTED = re.compile(r"「([^」]+)」")
STATION_FALLBACK = re.compile(r"([^\s/／]+駅)")


def _to_half_width_digits(text: str) -> str:
    table = str.maketrans("０１２３４５６７８９", "0123456789")
    return text.translate(table)


def parse_walk_minutes(station_text: str) -> int | None:
    match = WALK_PATTERN.search(_to_half_width_digits(station_text or ""))
    if not match:
        return None
    return int(match.group(1))


def parse_station_name(station_text: str) -> str:
    text = (station_text or "").strip()
    if not text:
        return ""
    quoted = STATION_QUOTED.search(text)
    if quoted:
        return quoted.group(1)
    fallback = STATION_FALLBACK.search(text)
    if fallback:
        return fallback.group(1).replace("駅", "")
    # e.g. 東京メトロ丸ノ内線「淡路町」徒歩2分 already handled;
    # otherwise keep a short prefix before 徒歩
    if "徒歩" in text:
        return text.split("徒歩", 1)[0].strip(" /／")
    return text


def parse_floor_text(*texts: str) -> str:
    for text in texts:
        raw = _to_half_width_digits(text or "")
        if not raw:
            continue
        for pattern in FLOOR_PATTERNS:
            match = pattern.search(raw)
            if match:
                return match.group(1)
    return ""


def parse_floor_from_detail_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for th in soup.select("th"):
        label = " ".join(th.get_text(" ", strip=True).split())
        if "所在階" not in label:
            continue
        td = th.find_next("td")
        if td is None:
            continue
        value = " ".join(td.get_text(" ", strip=True).split())
        parsed = parse_floor_text(value)
        if parsed:
            return parsed
        # e.g. "10階/RC13階建"
        if "階" in value:
            return value.split("/", 1)[0].strip()
    return ""
