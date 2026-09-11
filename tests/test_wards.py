"""Tokyo ward / Tama-city watch registration tests."""

from __future__ import annotations

from pathlib import Path

from scripts.register_wards import ensure_wards
from src.db import add_watch_config, init_db, list_watch_configs
from src.wards import (
    CITYWIDE_AREA_LABEL,
    TOKYO_23_WARDS,
    TOKYO_CITIES,
    all_city_watches,
    all_tokyo_watches,
    all_ward_watches,
    build_ward_search_url,
    classify_tokyo_area,
    coverage_from_payload,
    region_hashtags,
)


NISHITAMA_CODES = ("13303", "13305", "13307", "13308")


def test_tokyo_cities_use_jis_codes_and_ward_url_shape() -> None:
    watches = {item.name: item for item in all_city_watches()}
    assert len(watches) == 26
    assert len(TOKYO_CITIES) == 26

    hachioji = watches["八王子市 中古マンション"]
    assert hachioji.ward_code == "13201"
    assert hachioji.search_url == build_ward_search_url("13201")
    assert "sc=13201" in hachioji.search_url
    assert "ar=030" in hachioji.search_url
    assert "bs=011" in hachioji.search_url
    assert "ta=13" in hachioji.search_url
    assert "jspIdFlg=patternShikugun" in hachioji.search_url

    nishitokyo = watches["西東京市 中古マンション"]
    assert nishitokyo.ward_code == "13229"
    assert "sc=13229" in nishitokyo.search_url

    names = [name for name, _code in TOKYO_CITIES]
    assert names == [
        "八王子市",
        "立川市",
        "武蔵野市",
        "三鷹市",
        "青梅市",
        "府中市",
        "昭島市",
        "調布市",
        "町田市",
        "小金井市",
        "小平市",
        "日野市",
        "東村山市",
        "国分寺市",
        "国立市",
        "福生市",
        "狛江市",
        "東大和市",
        "清瀬市",
        "東久留米市",
        "武蔵村山市",
        "多摩市",
        "稲城市",
        "羽村市",
        "あきる野市",
        "西東京市",
    ]
    for city_name, city_code in TOKYO_CITIES:
        watch = watches[f"{city_name} 中古マンション"]
        assert watch.ward_code == city_code
        assert f"sc={city_code}" in watch.search_url


def test_tokyo_watches_keep_23_wards_and_skip_nishitama() -> None:
    wards = all_ward_watches()
    cities = all_city_watches()
    combined = all_tokyo_watches()
    assert len(wards) == 23
    assert len(TOKYO_23_WARDS) == 23
    assert combined == wards + cities
    names = [item.name for item in combined]
    assert len(names) == len(set(names))
    assert names[0] == "千代田区 中古マンション"
    assert "八王子市 中古マンション" in names
    codes = [item.ward_code for item in combined]
    for nishitama_code in NISHITAMA_CODES:
        assert nishitama_code not in codes


def test_ensure_wards_adds_cities_without_duplicating(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    init_db(db)
    add_watch_config(
        "千代田区 中古マンション",
        "https://example.invalid/old",
        max_pages=1,
        db_path=db,
    )
    created = ensure_wards(max_pages=50, db_path=db)
    configs = list_watch_configs(db_path=db)
    names = [config.name for config in configs]
    assert len(configs) == 49
    assert names.count("千代田区 中古マンション") == 1
    assert names.count("八王子市 中古マンション") == 1
    assert len(created) == 48

    chiyoda = next(item for item in configs if item.name == "千代田区 中古マンション")
    assert chiyoda.max_pages == 50
    assert "sc=13101" in chiyoda.search_url

    created_again = ensure_wards(max_pages=50, db_path=db)
    assert created_again == []
    assert len(list_watch_configs(db_path=db)) == 49


def test_region_hashtags_match_area() -> None:
    assert region_hashtags(CITYWIDE_AREA_LABEL) == ("#東京23区", "#東京市部")
    assert region_hashtags("千代田区") == ("#東京23区",)
    assert region_hashtags("八王子市 中古マンション") == ("#東京市部",)
    assert region_hashtags("東京23区") == ("#東京23区",)


def test_classify_tokyo_area_distinguishes_ward_and_city() -> None:
    assert classify_tokyo_area("千代田区 中古マンション") == "ward"
    assert classify_tokyo_area("八王子市") == "city"
    assert classify_tokyo_area("西東京市 中古マンション") == "city"
    assert classify_tokyo_area("") == "other"
    assert classify_tokyo_area(CITYWIDE_AREA_LABEL) == "other"


def test_coverage_from_payload_lists_cities() -> None:
    payload = {
        "configs": [
            {"name": "千代田区 中古マンション", "listing_count": 10, "listings": []},
            {"name": "八王子市 中古マンション", "listing_count": 0, "listings": [{}, {}]},
        ]
    }
    rows = coverage_from_payload(payload)
    assert [(item.label, item.listing_count, item.kind) for item in rows] == [
        ("千代田区", 10, "ward"),
        ("八王子市", 2, "city"),
    ]
