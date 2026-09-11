"""Tokyo 23 wards and Tama-city SUUMO search URL helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from src.scraper.suumo import normalize_search_url

CITYWIDE_AREA_LABEL = "東京23区+市部"
WARD_HASHTAG = "#東京23区"
CITY_HASHTAG = "#東京市部"

# 特別区コード (総務省市区町村コード) — SUUMO sc= パラメータ
TOKYO_23_WARDS: tuple[tuple[str, str], ...] = (
    ("千代田区", "13101"),
    ("中央区", "13102"),
    ("港区", "13103"),
    ("新宿区", "13104"),
    ("文京区", "13105"),
    ("台東区", "13106"),
    ("墨田区", "13107"),
    ("江東区", "13108"),
    ("品川区", "13109"),
    ("目黒区", "13110"),
    ("大田区", "13111"),
    ("世田谷区", "13112"),
    ("渋谷区", "13113"),
    ("中野区", "13114"),
    ("杉並区", "13115"),
    ("豊島区", "13116"),
    ("北区", "13117"),
    ("荒川区", "13118"),
    ("板橋区", "13119"),
    ("練馬区", "13120"),
    ("足立区", "13121"),
    ("葛飾区", "13122"),
    ("江戸川区", "13123"),
)

# 東京市部（多摩地域の26市）。23区と同じ JIS 市区町村コードを sc= に使う。
TOKYO_CITIES: tuple[tuple[str, str], ...] = (
    ("八王子市", "13201"),
    ("立川市", "13202"),
    ("武蔵野市", "13203"),
    ("三鷹市", "13204"),
    ("青梅市", "13205"),
    ("府中市", "13206"),
    ("昭島市", "13207"),
    ("調布市", "13208"),
    ("町田市", "13209"),
    ("小金井市", "13210"),
    ("小平市", "13211"),
    ("日野市", "13212"),
    ("東村山市", "13213"),
    ("国分寺市", "13214"),
    ("国立市", "13215"),
    ("福生市", "13218"),
    ("狛江市", "13219"),
    ("東大和市", "13220"),
    ("清瀬市", "13221"),
    ("東久留米市", "13222"),
    ("武蔵村山市", "13223"),
    ("多摩市", "13224"),
    ("稲城市", "13225"),
    ("羽村市", "13227"),
    ("あきる野市", "13228"),
    ("西東京市", "13229"),
)

# 西多摩郡（瑞穂町 13303 / 日の出町 13305 / 檜原村 13307 / 奥多摩町 13308）は
# 23区・市部と同じ中古マンション検索 URL だと SUUMO がエラーページを返すため対象外。

WATCH_NAME_SUFFIX = " 中古マンション"
AreaKind = Literal["ward", "city", "other"]


@dataclass(frozen=True)
class WardWatch:
    name: str
    ward_code: str
    search_url: str


@dataclass(frozen=True)
class AreaCoverage:
    label: str
    listing_count: int
    kind: AreaKind


def build_ward_search_url(ward_code: str) -> str:
    raw = (
        "https://suumo.jp/jj/bukken/ichiran/JJ010FJ001/"
        f"?ar=030&bs=011&ta=13&jspIdFlg=patternShikugun&sc={ward_code}"
        "&kb=1&kt=9999999&mb=0&mt=9999999&ekTjCd=&ekTjNm=&tj=0"
        "&cnb=0&cn=9999999&srch_navi=1"
    )
    return normalize_search_url(raw)


def _watches_from(areas: tuple[tuple[str, str], ...]) -> list[WardWatch]:
    return [
        WardWatch(
            name=f"{area_name}{WATCH_NAME_SUFFIX}",
            ward_code=area_code,
            search_url=build_ward_search_url(area_code),
        )
        for area_name, area_code in areas
    ]


def all_ward_watches() -> list[WardWatch]:
    return _watches_from(TOKYO_23_WARDS)


def all_city_watches() -> list[WardWatch]:
    return _watches_from(TOKYO_CITIES)


def all_tokyo_watches() -> list[WardWatch]:
    return all_ward_watches() + all_city_watches()


def area_core_name(area_label: str) -> str:
    text = (area_label or "").strip()
    if text.endswith(WATCH_NAME_SUFFIX):
        text = text[: -len(WATCH_NAME_SUFFIX)].strip()
    return text


def classify_tokyo_area(area_label: str) -> AreaKind:
    core = area_core_name(area_label)
    if not core:
        return "other"
    for ward_name, _ward_code in TOKYO_23_WARDS:
        if core == ward_name or core.startswith(ward_name):
            return "ward"
    for city_name, _city_code in TOKYO_CITIES:
        if core == city_name or core.startswith(city_name):
            return "city"
    if core.endswith("区"):
        return "ward"
    if core.endswith("市"):
        return "city"
    return "other"


def coverage_from_payload(payload: dict[str, Any]) -> list[AreaCoverage]:
    rows: list[AreaCoverage] = []
    for block in payload.get("configs") or []:
        label = area_core_name(str(block.get("name") or "")) or "-"
        count = int(block.get("listing_count") or 0)
        if count <= 0:
            count = len(block.get("listings") or [])
        rows.append(
            AreaCoverage(
                label=label,
                listing_count=count,
                kind=classify_tokyo_area(label),
            )
        )
    return rows


def region_hashtags(area_label: str) -> tuple[str, ...]:
    """Hashtags that still describe the tweet's area without crowding 280 chars."""
    text = (area_label or "").strip() or CITYWIDE_AREA_LABEL
    core = text.removesuffix(WATCH_NAME_SUFFIX).strip() or CITYWIDE_AREA_LABEL
    if core == CITYWIDE_AREA_LABEL or core == "東京都" or (
        "23区" in core and "市部" in core
    ):
        return (WARD_HASHTAG, CITY_HASHTAG)
    if core == "東京23区":
        return (WARD_HASHTAG,)
    for ward_name, _ward_code in TOKYO_23_WARDS:
        if core == ward_name or core.startswith(ward_name):
            return (WARD_HASHTAG,)
    for city_name, _city_code in TOKYO_CITIES:
        if core == city_name or core.startswith(city_name):
            return (CITY_HASHTAG,)
    return (WARD_HASHTAG, CITY_HASHTAG)
