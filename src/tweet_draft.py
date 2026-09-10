"""Generate X (Twitter) draft text from daily diffs."""

from __future__ import annotations

from src.diff import DiffResult, format_man

DEFAULT_MAX_CHARS = 280


def build_first_day_draft(
    area_label: str,
    *,
    listing_count: int,
    avg_price_man: float | None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    avg_text = f"{avg_price_man:.0f}万円" if avg_price_man is not None else "-"
    body = (
        f"{_header(area_label)}\n"
        f"監視件数:{listing_count}件 / 平均:{avg_text}\n"
        f"初回取得のため変動比較は翌日以降です。\n"
        f"{_hashtags(has_drops=False)}"
    )
    return _trim(body, max_chars)


def build_tweet_draft(
    area_label: str,
    diff: DiffResult,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    header = _header(area_label)
    summary = f"値下げ:{diff.drop_count}件 / 値上げ:{diff.rise_count}件"
    tags = _hashtags(has_drops=diff.drop_count > 0)

    if diff.drop_count == 0 and diff.new_count == 0 and diff.rise_count == 0:
        body = f"{header}\n{summary}\n目立った価格変動はありませんでした。\n{tags}"
        return _trim(body, max_chars)

    highlight_lines: list[str] = []
    for drop in diff.price_drops[:3]:
        delta = drop.delta_man
        delta_text = format_man(abs(delta)) if delta is not None else "-"
        highlight_lines.append(
            f"注目: {drop.name} {format_man(drop.old_price_man)}→{format_man(drop.new_price_man)}"
            f"（-{delta_text}）"
        )

    if not highlight_lines and diff.new_listings:
        newest = diff.new_listings[0]
        highlight_lines.append(
            f"新着掲載: {newest.name} {format_man(newest.price_man)}"
        )

    parts = [header, summary, *highlight_lines, tags]
    return _trim("\n".join(parts), max_chars)


def _header(area_label: str) -> str:
    text = (area_label or "").strip() or "東京23区"
    if "中古マンション" in text:
        return text
    return f"{text} 中古マンション"


def _hashtags(*, has_drops: bool) -> str:
    tags = ["#中古マンション", "#東京23区"]
    if has_drops:
        tags.append("#値下げ")
    else:
        tags.append("#マンション相場")
    return " ".join(tags)


def _trim(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    ellipsis = "…"
    return text[: max_chars - len(ellipsis)] + ellipsis
