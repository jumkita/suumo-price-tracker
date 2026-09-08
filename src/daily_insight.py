"""Rule-based daily briefing from citywide price changes."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import median
from typing import Any, Literal, Never

from src.citywide import CitywideComparison, compare_citywide
from src.diff import PriceChange, format_man
from src.listing_display import ward_label

HeadlineKind = Literal[
    "first_day",
    "no_match",
    "no_drop",
    "wide_cut",
    "deep_cut",
    "small_adjust",
    "default",
]

INSIGHT_JSON_NAME = "daily_insight.json"
INSIGHT_MD_NAME = "daily_insight.md"
WIDE_DROP_RATE_PCT = 5.0
DEEP_DROP_PCT = 8.0
SMALL_DROP_RATE_PCT = 3.0
SMALL_DROP_PCT = 5.0
INVENTORY_SHIFT_PCT = 15.0
TOP_WARD_COUNT = 10
TOP_DROP_COUNT = 7


@dataclass(frozen=True)
class CountShare:
    label: str
    count: int


@dataclass(frozen=True)
class RateShare:
    label: str
    rate_pct: float
    count: int


@dataclass(frozen=True)
class YenShare:
    label: str
    yen: int


@dataclass(frozen=True)
class DropHighlight:
    ward: str
    name: str
    old_price_man: int | None
    new_price_man: int | None
    delta_man: int | None
    drop_pct: float | None
    layout: str
    area_sqm: float | None


@dataclass(frozen=True)
class DailyInsight:
    snapshot_date: str
    previous_date: str | None
    headline_kind: HeadlineKind
    headline: str
    lead: str
    caveat: str
    can_say: str
    cannot_say: str
    drop_count: int
    rise_count: int
    matched_count: int
    unchanged_count: int
    drop_rate_pct: float | None
    median_drop_man: int | None
    median_drop_pct: float | None
    mean_drop_man: float | None
    total_drop_man: int
    inventory_prev: int
    inventory_cur: int
    removed_count: int
    new_count: int
    citywide_avg_prev: float | None
    citywide_avg_cur: float | None
    matched_avg_old: float | None
    matched_avg_new: float | None
    removed_avg_man: float | None
    drop_size_buckets: tuple[CountShare, ...]
    ward_rates: tuple[RateShare, ...]
    ward_yen: tuple[YenShare, ...]
    largest_drops: tuple[DropHighlight, ...]


def build_daily_insight(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    comparison: CitywideComparison | None = None,
) -> DailyInsight:
    snapshot_date = str(current.get("snapshot_date") or "-")
    previous_date = str(previous.get("snapshot_date") or "") if previous else None
    if comparison is None:
        comparison = compare_citywide(current, previous)
    if previous is None or comparison is None:
        return _first_day_insight(snapshot_date, current)
    return _from_comparison(snapshot_date, previous_date, comparison)


def previous_payload(publish_dir: Path, snapshot_date: str) -> dict[str, Any] | None:
    try:
        prev_day = (date.fromisoformat(snapshot_date) - timedelta(days=1)).isoformat()
    except ValueError:
        return None
    path = publish_dir / f"daily_prices_{prev_day}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_insight_files(
    publish_dir: Path,
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> tuple[Path, Path]:
    insight = build_daily_insight(current, previous)
    payload = insight_to_dict(insight)
    json_path = publish_dir / INSIGHT_JSON_NAME
    md_path = publish_dir / INSIGHT_MD_NAME
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(format_insight_markdown(insight), encoding="utf-8")
    return json_path, md_path


def insight_to_dict(insight: DailyInsight) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "snapshot_date": insight.snapshot_date,
        "previous_date": insight.previous_date,
        "headline_kind": insight.headline_kind,
        "headline": insight.headline,
        "lead": insight.lead,
        "caveat": insight.caveat,
        "can_say": insight.can_say,
        "cannot_say": insight.cannot_say,
        "drop_count": insight.drop_count,
        "rise_count": insight.rise_count,
        "matched_count": insight.matched_count,
        "unchanged_count": insight.unchanged_count,
        "drop_rate_pct": insight.drop_rate_pct,
        "median_drop_man": insight.median_drop_man,
        "median_drop_pct": insight.median_drop_pct,
        "mean_drop_man": insight.mean_drop_man,
        "total_drop_man": insight.total_drop_man,
        "inventory_prev": insight.inventory_prev,
        "inventory_cur": insight.inventory_cur,
        "removed_count": insight.removed_count,
        "new_count": insight.new_count,
        "citywide_avg_prev": insight.citywide_avg_prev,
        "citywide_avg_cur": insight.citywide_avg_cur,
        "matched_avg_old": insight.matched_avg_old,
        "matched_avg_new": insight.matched_avg_new,
        "removed_avg_man": insight.removed_avg_man,
        "drop_size_buckets": [item.__dict__ for item in insight.drop_size_buckets],
        "ward_rates": [item.__dict__ for item in insight.ward_rates],
        "ward_yen": [item.__dict__ for item in insight.ward_yen],
        "largest_drops": [item.__dict__ for item in insight.largest_drops],
        "markdown": format_insight_markdown(insight),
    }


def _first_day_insight(snapshot_date: str, current: dict[str, Any]) -> DailyInsight:
    kind: HeadlineKind = "first_day"
    return DailyInsight(
        snapshot_date=snapshot_date,
        previous_date=None,
        headline_kind=kind,
        headline=_headline_text(kind, drop_count=0, drop_rate_pct=None, median_drop_pct=None),
        lead="前日スナップショットがないため、値下げの内訳はまだ出せません。翌日の更新から読み取りが入ります。",
        caveat="比較は連続する2日分の掲載が揃ってから行います。",
        can_say="今日時点の監視件数は記録できています。",
        cannot_say="値下げ件数や相場の方向は、まだ判断できません。",
        drop_count=0,
        rise_count=0,
        matched_count=0,
        unchanged_count=0,
        drop_rate_pct=None,
        median_drop_man=None,
        median_drop_pct=None,
        mean_drop_man=None,
        total_drop_man=0,
        inventory_prev=0,
        inventory_cur=int(current.get("listing_count") or 0),
        removed_count=0,
        new_count=0,
        citywide_avg_prev=None,
        citywide_avg_cur=None,
        matched_avg_old=None,
        matched_avg_new=None,
        removed_avg_man=None,
        drop_size_buckets=(),
        ward_rates=(),
        ward_yen=(),
        largest_drops=(),
    )


def _from_comparison(
    snapshot_date: str,
    previous_date: str | None,
    comparison: CitywideComparison,
) -> DailyInsight:
    drop_abs = [-(item.delta_man or 0) for item in comparison.drops]
    drop_pcts = [
        (-(item.delta_man or 0) / item.old_price_man * 100)
        for item in comparison.drops
        if item.old_price_man
    ]
    drop_rate = (
        100.0 * len(comparison.drops) / comparison.matched_count
        if comparison.matched_count
        else None
    )
    median_drop_man = int(median(drop_abs)) if drop_abs else None
    median_drop_pct = float(median(drop_pcts)) if drop_pcts else None
    mean_drop_man = float(sum(drop_abs) / len(drop_abs)) if drop_abs else None
    kind = _headline_kind(
        matched_count=comparison.matched_count,
        drop_count=len(comparison.drops),
        drop_rate_pct=drop_rate,
        median_drop_pct=median_drop_pct,
    )
    return DailyInsight(
        snapshot_date=snapshot_date,
        previous_date=previous_date,
        headline_kind=kind,
        headline=_headline_text(
            kind,
            drop_count=len(comparison.drops),
            drop_rate_pct=drop_rate,
            median_drop_pct=median_drop_pct,
        ),
        lead=_lead_text(comparison, drop_rate, median_drop_man, median_drop_pct),
        caveat=_caveat_text(comparison, previous_date, snapshot_date),
        can_say=_can_say_text(kind, comparison, median_drop_man, median_drop_pct),
        cannot_say=_cannot_say_text(comparison),
        drop_count=len(comparison.drops),
        rise_count=len(comparison.rises),
        matched_count=comparison.matched_count,
        unchanged_count=comparison.unchanged_count,
        drop_rate_pct=drop_rate,
        median_drop_man=median_drop_man,
        median_drop_pct=median_drop_pct,
        mean_drop_man=mean_drop_man,
        total_drop_man=sum(drop_abs),
        inventory_prev=comparison.prev_listing_count,
        inventory_cur=comparison.cur_listing_count,
        removed_count=comparison.removed_count,
        new_count=comparison.new_count,
        citywide_avg_prev=comparison.prev_avg_man,
        citywide_avg_cur=comparison.cur_avg_man,
        matched_avg_old=comparison.matched_avg_old,
        matched_avg_new=comparison.matched_avg_new,
        removed_avg_man=comparison.removed_avg_man,
        drop_size_buckets=_drop_size_buckets(drop_abs),
        ward_rates=_ward_rates(comparison),
        ward_yen=_ward_yen(comparison),
        largest_drops=_largest_drops(comparison.drops),
    )


def _headline_kind(
    *,
    matched_count: int,
    drop_count: int,
    drop_rate_pct: float | None,
    median_drop_pct: float | None,
) -> HeadlineKind:
    if matched_count == 0:
        return "no_match"
    if drop_count == 0:
        return "no_drop"
    if drop_rate_pct is not None and drop_rate_pct >= WIDE_DROP_RATE_PCT:
        return "wide_cut"
    if median_drop_pct is not None and median_drop_pct >= DEEP_DROP_PCT:
        return "deep_cut"
    if (
        drop_rate_pct is not None
        and drop_rate_pct < SMALL_DROP_RATE_PCT
        and median_drop_pct is not None
        and median_drop_pct < SMALL_DROP_PCT
    ):
        return "small_adjust"
    return "default"


def _headline_text(
    kind: HeadlineKind,
    *,
    drop_count: int,
    drop_rate_pct: float | None,
    median_drop_pct: float | None,
) -> str:
    rate = f"{drop_rate_pct:.1f}%" if drop_rate_pct is not None else "-"
    median_pct = f"{median_drop_pct:.1f}%" if median_drop_pct is not None else "-"
    match kind:
        case "first_day":
            return "初回取得のため、値下げの読み取りは翌日以降です"
        case "no_match":
            return "継続掲載がなく、前日との比較ができません"
        case "no_drop":
            return "継続掲載に値下げはありません"
        case "wide_cut":
            return f"値下げが広め。継続掲載の{rate}が価格を下げた"
        case "deep_cut":
            return f"値下げ{drop_count}件。中央値の下げ率は{median_pct}"
        case "small_adjust":
            return f"値下げ{drop_count}件は、相場崩壊ではなく値付けの微修正"
        case "default":
            return f"値下げ{drop_count}件。継続掲載の{rate}が価格を調整"
        case _:
            unreachable: Never = kind
            raise ValueError(unreachable)


def _lead_text(
    comparison: CitywideComparison,
    drop_rate: float | None,
    median_drop_man: int | None,
    median_drop_pct: float | None,
) -> str:
    if comparison.matched_count == 0:
        return "同じ掲載として突合できる物件がありません。"
    if not comparison.drops:
        return (
            f"継続掲載 {comparison.matched_count}件はすべて同額でした。"
            f"値上げは{len(comparison.rises)}件です。"
        )
    unchanged_pct = 100.0 * comparison.unchanged_count / comparison.matched_count
    median_text = format_man(median_drop_man) if median_drop_man is not None else "-"
    pct_text = f"{median_drop_pct:.1f}%" if median_drop_pct is not None else "-"
    rate_text = f"{drop_rate:.2f}%" if drop_rate is not None else "-"
    parts = [
        f"前日比で売出価格を下げた物件は{len(comparison.drops)}件（継続掲載の{rate_text}）です。",
        f"継続掲載の{unchanged_pct:.0f}%は同額で、下げ幅の中央値は{median_text}（旧価格比{pct_text}）です。",
    ]
    if comparison.matched_avg_old is not None and comparison.matched_avg_new is not None:
        delta = comparison.matched_avg_new - comparison.matched_avg_old
        parts.append(
            f"継続物件の平均売出価格は{_man_number(comparison.matched_avg_old)}万円 → "
            f"{_man_number(comparison.matched_avg_new)}万円（{_signed_man(delta)}）です。"
        )
    if (
        comparison.cur_avg_man is not None
        and comparison.prev_avg_man is not None
        and comparison.cur_avg_man > comparison.prev_avg_man
        and comparison.removed_avg_man is not None
        and comparison.matched_avg_old is not None
        and comparison.removed_avg_man < comparison.matched_avg_old
    ):
        parts.append(
            "全区平均が上がっている場合でも、値上げではなく安い掲載が消えた影響のことがあります。"
        )
    return "".join(parts)


def _caveat_text(
    comparison: CitywideComparison,
    previous_date: str | None,
    snapshot_date: str,
) -> str:
    span = f"{previous_date or '-'} → {snapshot_date} の1日比較です。"
    if comparison.prev_listing_count <= 0:
        return span + " 掲載件数の変化はまだ評価できません。"
    shift = abs(comparison.cur_listing_count - comparison.prev_listing_count)
    shift_pct = 100.0 * shift / comparison.prev_listing_count
    if shift_pct >= INVENTORY_SHIFT_PCT:
        return (
            f"{span} 掲載件数は {comparison.prev_listing_count} → {comparison.cur_listing_count} "
            f"と {shift_pct:.0f}% 動いており、市況そのものより取得範囲・掲載入れ替わりの影響が大きい可能性があります。"
        )
    return span + " 数日分が揃うまで、トレンド判断には使いすぎないでください。"


def _can_say_text(
    kind: HeadlineKind,
    comparison: CitywideComparison,
    median_drop_man: int | None,
    median_drop_pct: float | None,
) -> str:
    match kind:
        case "first_day" | "no_match":
            return "比較対象が足りない、ということだけが確実です。"
        case "no_drop":
            return "少なくとも継続掲載では、売出価格は動いていません。"
        case "small_adjust":
            median_text = format_man(median_drop_man) if median_drop_man is not None else "小さめ"
            return (
                f"継続掲載の売り手は大幅な投げ売りではなく、中央値{median_text}"
                "前後の値付け直しをしています。"
            )
        case "wide_cut":
            return "継続掲載の中で値下げが広めに出ています。件数の広がりを優先して見てください。"
        case "deep_cut":
            pct = f"{median_drop_pct:.1f}%" if median_drop_pct is not None else "大きめ"
            return f"件数より下げ率の方が目立ちます。中央値は旧価格比{pct}です。"
        case "default":
            return "値下げは出ているが、継続掲載の大半は据え置きです。"
        case _:
            unreachable: Never = kind
            raise ValueError(unreachable)


def _cannot_say_text(comparison: CitywideComparison) -> str:
    return (
        "23区全体が下落局面に入ったこと、翌日も同じペースであること、"
        f"離脱{comparison.removed_count}件がすべて成約だということは、この1日だけでは言えません。"
    )


def _drop_size_buckets(drop_abs: list[int]) -> tuple[CountShare, ...]:
    if not drop_abs:
        return ()
    return (
        CountShare("100万円未満", sum(1 for value in drop_abs if value < 100)),
        CountShare("100〜299万円", sum(1 for value in drop_abs if 100 <= value < 300)),
        CountShare("300〜999万円", sum(1 for value in drop_abs if 300 <= value < 1000)),
        CountShare("1000万円以上", sum(1 for value in drop_abs if value >= 1000)),
    )


def _ward_rates(comparison: CitywideComparison) -> tuple[RateShare, ...]:
    ranked = sorted(
        comparison.wards,
        key=lambda item: (item.drop_rate_pct, item.drop_count),
        reverse=True,
    )
    return tuple(
        RateShare(item.ward, item.drop_rate_pct, item.drop_count)
        for item in ranked[:TOP_WARD_COUNT]
        if item.matched > 0
    )


def _ward_yen(comparison: CitywideComparison) -> tuple[YenShare, ...]:
    ranked = sorted(comparison.wards, key=lambda item: item.drop_yen, reverse=True)
    return tuple(
        YenShare(item.ward, item.drop_yen) for item in ranked[:6] if item.drop_yen > 0
    )


def _largest_drops(drops: list[PriceChange]) -> tuple[DropHighlight, ...]:
    highlights: list[DropHighlight] = []
    for item in drops[:TOP_DROP_COUNT]:
        pct = None
        if item.old_price_man and item.delta_man:
            pct = -item.delta_man / item.old_price_man * 100
        highlights.append(
            DropHighlight(
                ward=ward_label(item.ward_name),
                name=item.name,
                old_price_man=item.old_price_man,
                new_price_man=item.new_price_man,
                delta_man=item.delta_man,
                drop_pct=pct,
                layout=item.layout or "-",
                area_sqm=item.area_sqm,
            )
        )
    return tuple(highlights)


def _man_number(value: float) -> str:
    return f"{value:,.0f}"


def _signed_man(delta: float) -> str:
    rounded = int(round(delta))
    if rounded > 0:
        return f"+{format_man(rounded)}"
    if rounded < 0:
        return format_man(rounded)
    return "ほぼ変わらず"


def format_insight_markdown(insight: DailyInsight) -> str:
    lines = [
        f"# 今日の読み取り（{insight.snapshot_date}）",
        "",
        f"**{insight.headline}**",
        "",
        insight.lead,
        "",
        f"> {insight.caveat}",
        "",
        "## 数字",
        "",
        f"- 値下げ: {insight.drop_count}件 / 値上げ: {insight.rise_count}件 / 継続掲載: {insight.matched_count}件",
    ]
    if insight.drop_rate_pct is not None:
        lines.append(f"- 値下げ率: {insight.drop_rate_pct:.2f}%")
    if insight.median_drop_man is not None:
        pct = f"（{insight.median_drop_pct:.2f}%）" if insight.median_drop_pct is not None else ""
        lines.append(f"- 下げ幅中央値: {format_man(insight.median_drop_man)}{pct}")
    if insight.total_drop_man:
        lines.append(f"- 値下げ総額: {format_man(insight.total_drop_man)}")
    lines.append(
        f"- 掲載件数: {insight.inventory_prev} → {insight.inventory_cur}"
        f"（離脱 {insight.removed_count} / 新規 {insight.new_count}）"
    )
    if insight.drop_size_buckets:
        lines.extend(["", "## 下げ幅の分布", ""])
        for bucket in insight.drop_size_buckets:
            lines.append(f"- {bucket.label}: {bucket.count}件")
    if insight.ward_rates:
        lines.extend(["", "## 区ごとの値下げ率（上位）", ""])
        for item in insight.ward_rates:
            lines.append(f"- {item.label}: {item.rate_pct:.2f}%（{item.count}件）")
    if insight.ward_yen:
        lines.extend(["", "## 区ごとの値下げ総額（上位）", ""])
        for item in insight.ward_yen:
            lines.append(f"- {item.label}: {format_man(item.yen)}")
    if insight.largest_drops:
        lines.extend(["", "## 値下げ額が大きい物件", ""])
        for item in insight.largest_drops:
            pct = f" / {item.drop_pct:.1f}%" if item.drop_pct is not None else ""
            lines.append(
                f"- {item.ward} {item.name}: "
                f"{format_man(item.old_price_man)}→{format_man(item.new_price_man)}"
                f"（{format_man(item.delta_man)}{pct}）"
            )
    lines.extend(
        [
            "",
            "## いま言えること",
            "",
            insight.can_say,
            "",
            "## まだ言えないこと",
            "",
            insight.cannot_say,
            "",
        ]
    )
    return "\n".join(lines)


def render_insight_html(insight: DailyInsight) -> str:
    metrics = [
        ("値下げ件数", str(insight.drop_count)),
        (
            "継続掲載のうち値下げ",
            f"{insight.drop_rate_pct:.2f}%" if insight.drop_rate_pct is not None else "-",
        ),
        (
            "下げ幅の中央値",
            format_man(insight.median_drop_man) if insight.median_drop_man is not None else "-",
        ),
        ("値上げ件数", str(insight.rise_count)),
    ]
    metric_html = "".join(
        f'<div><span class="label">{html.escape(label)}</span>'
        f"<strong>{html.escape(value)}</strong></div>"
        for label, value in metrics
    )
    buckets = _html_counts("下げ幅の分布", insight.drop_size_buckets)
    rates = _html_rate_bars(insight.ward_rates)
    yen = _html_yen_list(insight.ward_yen)
    largest = _html_largest(insight.largest_drops)
    return (
        '<section class="card insight">'
        "<h2>今日の読み取り</h2>"
        f'<p class="sub">{html.escape(insight.previous_date or "-")} → '
        f"{html.escape(insight.snapshot_date)}</p>"
        f'<p class="insight-headline">{html.escape(insight.headline)}</p>'
        f"<p>{html.escape(insight.lead)}</p>"
        f'<div class="metrics">{metric_html}</div>'
        f'<p class="insight-note">{html.escape(insight.caveat)}</p>'
        f"{buckets}{rates}{yen}{largest}"
        "<h3>いま言えること</h3>"
        f"<p>{html.escape(insight.can_say)}</p>"
        "<h3>まだ言えないこと</h3>"
        f"<p>{html.escape(insight.cannot_say)}</p>"
        "</section>"
    )


def _html_counts(title: str, buckets: tuple[CountShare, ...]) -> str:
    if not buckets:
        return ""
    items = "".join(
        f"<li>{html.escape(item.label)}: {item.count}件</li>" for item in buckets
    )
    return f"<h3>{html.escape(title)}</h3><ul>{items}</ul>"


def _html_rate_bars(rates: tuple[RateShare, ...]) -> str:
    if not rates:
        return ""
    peak = max(item.rate_pct for item in rates) or 1.0
    rows = []
    for item in rates:
        width = max(4.0, 100.0 * item.rate_pct / peak)
        rows.append(
            '<div class="insight-bar">'
            f'<span class="insight-bar-label">{html.escape(item.label)} '
            f"{item.rate_pct:.2f}%（{item.count}件）</span>"
            '<span class="insight-bar-track">'
            f'<span class="insight-bar-fill" style="width:{width:.1f}%"></span>'
            "</span></div>"
        )
    return "<h3>区ごとの値下げ率（上位）</h3>" + "".join(rows)


def _html_yen_list(rows: tuple[YenShare, ...]) -> str:
    if not rows:
        return ""
    items = "".join(
        f"<li>{html.escape(item.label)}: {html.escape(format_man(item.yen))}</li>"
        for item in rows
    )
    return f"<h3>区ごとの値下げ総額（上位）</h3><ul>{items}</ul>"


def _html_largest(rows: tuple[DropHighlight, ...]) -> str:
    if not rows:
        return ""
    items = []
    for item in rows:
        pct = f" / {item.drop_pct:.1f}%" if item.drop_pct is not None else ""
        items.append(
            "<li>"
            f"{html.escape(item.ward)} {html.escape(item.name)}: "
            f"{html.escape(format_man(item.old_price_man))}→"
            f"{html.escape(format_man(item.new_price_man))}"
            f"（{html.escape(format_man(item.delta_man))}{html.escape(pct)}）"
            "</li>"
        )
    return "<h3>値下げ額が大きい物件</h3><ul>" + "".join(items) + "</ul>"
