"""Tweet draft tests."""

from __future__ import annotations

from src.db import ListingRow
from src.diff import DiffResult, PriceChange
from src.tweet_draft import build_tweet_draft


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
    assert "目立った価格変動はありませんでした" in draft
    assert "#不動産" in draft
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
    draft = build_tweet_draft("千代田区", diff)
    assert "値下げ:1件" in draft
    assert "サンプルコート千代田" in draft
    assert "5980万円→5780万円" in draft
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
    from src.tweet_draft import build_first_day_draft

    draft = build_first_day_draft("千代田区", listing_count=550, avg_price_man=12345.6)
    assert "監視件数:550件" in draft
    assert "12346万円" in draft or "12345万円" in draft
    assert len(draft) <= 280
