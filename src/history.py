"""Compact daily price-history series from archived snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HISTORY_FILENAME = "price_history.json"


def summarize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    prices: list[int] = []
    wards: dict[str, dict[str, float | int | None]] = {}
    for block in payload.get("configs") or []:
        name = str(block.get("name") or "").strip()
        ward_prices = [
            int(item["price_man"])
            for item in (block.get("listings") or [])
            if item.get("price_man") is not None
        ]
        prices.extend(ward_prices)
        wards[name] = {
            "listing_count": len(block.get("listings") or []),
            "avg_price_man": (
                round(sum(ward_prices) / len(ward_prices), 1) if ward_prices else None
            ),
        }
    return {
        "snapshot_date": str(payload.get("snapshot_date") or ""),
        "listing_count": int(payload.get("listing_count") or len(prices)),
        "avg_price_man": (
            round(sum(prices) / len(prices), 1) if prices else None
        ),
        "wards": wards,
    }


def load_dated_payloads(publish_dir: Path) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in sorted(publish_dir.glob("daily_prices_????-??-??.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("snapshot_date"):
            payloads.append(payload)
    payloads.sort(key=lambda item: str(item.get("snapshot_date")))
    return payloads


def build_history(publish_dir: Path) -> dict[str, Any]:
    points = [summarize_payload(payload) for payload in load_dated_payloads(publish_dir)]
    return {
        "schema_version": 1,
        "point_count": len(points),
        "points": points,
    }


def write_history(publish_dir: Path) -> Path:
    history = build_history(publish_dir)
    path = publish_dir / HISTORY_FILENAME
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def svg_avg_price_chart(
    points: list[dict[str, Any]],
    *,
    width: int = 640,
    height: int = 180,
) -> str:
    series = [
        (str(p.get("snapshot_date") or ""), float(p["avg_price_man"]))
        for p in points
        if p.get("avg_price_man") is not None
    ]
    if not series:
        return ""
    pad_left, pad_right, pad_top, pad_bottom = 52, 12, 12, 28
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom
    values = [value for _, value in series]
    vmin = min(values)
    vmax = max(values)
    if vmin == vmax:
        vmin -= 1
        vmax += 1

    def x_at(index: int) -> float:
        if len(series) == 1:
            return pad_left + chart_w / 2
        return pad_left + chart_w * index / (len(series) - 1)

    def y_at(value: float) -> float:
        return pad_top + chart_h * (1 - (value - vmin) / (vmax - vmin))

    dots = []
    coords = []
    for index, (day, value) in enumerate(series):
        x = x_at(index)
        y = y_at(value)
        coords.append(f"{x:.1f},{y:.1f}")
        dots.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="#0f5c4c">'
            f"<title>{day}: {value:.0f}万円</title></circle>"
        )
    first_label = series[0][0][5:] if len(series[0][0]) >= 10 else series[0][0]
    last_label = series[-1][0][5:] if len(series[-1][0]) >= 10 else series[-1][0]
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="平均価格の推移" style="width:100%;height:auto">'
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fffdf8" rx="12"/>'
        f'<text x="{pad_left}" y="14" font-size="11" fill="#5f574e">{vmax:.0f}</text>'
        f'<text x="{pad_left}" y="{height - 8}" font-size="11" fill="#5f574e">{first_label}</text>'
        f'<text x="{width - pad_right}" y="{height - 8}" font-size="11" fill="#5f574e" text-anchor="end">{last_label}</text>'
        f'<polyline fill="none" stroke="#0f5c4c" stroke-width="2.5" points="{" ".join(coords)}"/>'
        f"{''.join(dots)}"
        f"</svg>"
    )
