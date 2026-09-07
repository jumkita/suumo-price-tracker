"""Tokyo 23 wards SUUMO search URL helpers."""

from __future__ import annotations

from dataclasses import dataclass

from src.scraper.suumo import normalize_search_url

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


@dataclass(frozen=True)
class WardWatch:
    name: str
    ward_code: str
    search_url: str


def build_ward_search_url(ward_code: str) -> str:
    raw = (
        "https://suumo.jp/jj/bukken/ichiran/JJ010FJ001/"
        f"?ar=030&bs=011&ta=13&jspIdFlg=patternShikugun&sc={ward_code}"
        "&kb=1&kt=9999999&mb=0&mt=9999999&ekTjCd=&ekTjNm=&tj=0"
        "&cnb=0&cn=9999999&srch_navi=1"
    )
    return normalize_search_url(raw)


def all_ward_watches() -> list[WardWatch]:
    return [
        WardWatch(
            name=f"{ward_name} 中古マンション",
            ward_code=ward_code,
            search_url=build_ward_search_url(ward_code),
        )
        for ward_name, ward_code in TOKYO_23_WARDS
    ]
