"""Publish thin-guard tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.publish_guard import assert_publish_not_too_thin


def test_assert_publish_not_too_thin_blocks_drop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALLOW_THIN_PUBLISH", raising=False)
    latest = tmp_path / "daily_prices.json"
    latest.write_text(json.dumps({"listing_count": 20000}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="thin publish"):
        assert_publish_not_too_thin({"listing_count": 500}, latest)


def test_assert_publish_not_too_thin_allows_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOW_THIN_PUBLISH", "1")
    latest = tmp_path / "daily_prices.json"
    latest.write_text(json.dumps({"listing_count": 20000}), encoding="utf-8")
    assert_publish_not_too_thin({"listing_count": 500}, latest)
