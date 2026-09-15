"""Tweet draft tests."""

from __future__ import annotations

from src.db import ListingRow
from src.diff import DiffResult, PriceChange
from src.tweet_draft import build_first_day_draft, build_tweet_draft
from src.wards import CITYWIDE_AREA_LABEL


def _empty_diff() -> DiffResult:
    return DiffResult(
        price_drops=[],
        price_rises=[],
        new_listings=[],
        removed_listings=[],
        unchanged_count=0,
    )


def test_build_tweet_draft_no_changes() -> None:
    draft = build_tweet_draft("千代田区", _empty_diff())
    assert "【日次】" not in draft
    assert "新規:" not in draft
    assert "目立った価格変動はありませんでした" in draft
    assert "#中古マンション" in draft
    assert "#東京23区" in draft
    assert "#東京市部" not in draft
    assert "#マンション相場" in draft
    assert len(draft) <= 280


def test_build_tweet_draft_with_drop() -> None:
    diff = DiffResult(
        price_drops=[
            PriceChange(
                property_id="1",
                name="サンプルコート千代田",
                old_price_man=5980,
                new_price_man=5780,
                delta_man=-200,
                url="https://suumo.jp/x",
                address="",
                station="",
            )
        ],
        price_rises=[],
        new_listings=[],
        removed_listings=[],
        unchanged_count=0,
    )
    draft = build_tweet_draft(CITYWIDE_AREA_LABEL, diff)
    assert "【日次】" not in draft
    assert "東京23区+市部 中古マンション" in draft
    assert "値下げ:1件 / 値上げ:0件" in draft
    assert "新規:" not in draft
    assert "サンプルコート千代田" in draft
    assert "5980万円→5780万円" in draft
    assert "#中古マンション #東京23区 #東京市部 #値下げ" in draft
    assert "#不動産" not in draft
    assert "△3.3%" in draft
    assert "-200万円" in draft
    assert len(draft) <= 280


def test_build_tweet_draft_highlights_higher_rate_not_higher_amount() -> None:
    expensive_small_rate = PriceChange(
        property_id="hi",
        name="高額少額率タワー",
        old_price_man=20000,
        new_price_man=18000,
        delta_man=-2000,
        url="https://suumo.jp/x",
        address="",
        station="",
    )
    cheap_high_rate = PriceChange(
        property_id="lo",
        name="低額高率コート",
        old_price_man=3000,
        new_price_man=2400,
        delta_man=-600,
        url="https://suumo.jp/y",
        address="",
        station="",
    )
    invalid_old = PriceChange(
        property_id="zero",
        name="旧価格ゼロ",
        old_price_man=0,
        new_price_man=100,
        delta_man=100,
        url="https://suumo.jp/z",
        address="",
        station="",
    )
    diff = DiffResult(
        price_drops=[expensive_small_rate, cheap_high_rate, invalid_old],
        price_rises=[],
        new_listings=[],
        removed_listings=[],
        unchanged_count=0,
    )
    draft = build_tweet_draft(CITYWIDE_AREA_LABEL, diff)
    lines = [line for line in draft.splitlines() if line.startswith("注目:")]
    assert len(lines) == 2
    assert "低額高率コート" in lines[0]
    assert "△20.0%" in lines[0]
    assert "-600万円" in lines[0]
    assert "高額少額率タワー" in lines[1]
    assert "△10.0%" in lines[1]
    assert "2億円→1億8000万円" in lines[1]
    assert "旧価格ゼロ" not in draft
    assert len(draft) <= 280


def test_build_tweet_draft_city_uses_tama_hashtag() -> None:
    draft = build_tweet_draft("八王子市", _empty_diff())
    assert "八王子市 中古マンション" in draft
    assert "#東京市部" in draft
    assert "#東京23区" not in draft
    assert len(draft) <= 280


def test_build_tweet_draft_respects_max_chars() -> None:
    long_name = "あ" * 200
    diff = DiffResult(
        price_drops=[
            PriceChange(
                property_id="1",
                name=long_name,
                old_price_man=9000,
                new_price_man=8000,
                delta_man=-1000,
                url="https://suumo.jp/x",
                address="",
                station="",
            )
        ],
        price_rises=[],
        new_listings=[
            ListingRow(
                property_id="2",
                name="新規",
                address="",
                price_man=1000,
                area_sqm=None,
                layout="",
                built_year="",
                station="",
                url="",
            )
        ],
        removed_listings=[],
        unchanged_count=0,
    )
    draft = build_tweet_draft("エリア名がとても長い監視ラベル", diff, max_chars=120)
    assert len(draft) <= 120
    assert draft.endswith("…")


def test_build_first_day_draft() -> None:
    draft = build_first_day_draft("千代田区", listing_count=550, avg_price_man=12345.6)
    assert "【日次】" not in draft
    assert "監視件数:550件" in draft
    assert "12346万円" in draft or "12345万円" in draft
    assert "#マンション相場" in draft
    assert len(draft) <= 280
