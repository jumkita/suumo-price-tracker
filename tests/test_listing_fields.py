"""Listing field parsing tests."""

from __future__ import annotations

from src.listing_fields import parse_floor_text, parse_station_name, parse_walk_minutes
from src.scraper.suumo import clean_property_name


def test_parse_station_and_walk() -> None:
    text = "東京メトロ丸ノ内線「大手町」徒歩6分"
    assert parse_station_name(text) == "大手町"
    assert parse_walk_minutes(text) == 6


def test_clean_property_name_prefers_bare_name() -> None:
    assert clean_property_name("ダイアパレス水道橋◆水道橋駅3分◆南向き") == "ダイアパレス水道橋"
    assert clean_property_name("■■■ 即！見学 ■■■") == ""


def test_parse_floor_text() -> None:
    assert parse_floor_text("10階/RC13階建") == "10階"
    assert parse_floor_text("所在階 ヒント", "B1階") == "B1階"
