"""Generate X (Twitter) draft text from daily diffs."""

from __future__ import annotations

from src.diff import DiffResult, format_man

DEFAULT_MAX_CHARS = 280


def build_tweet_draft(
    area_label: str,
    diff: DiffResult,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    header = f"【日次】{area_label} 中古マンション動向"
    summary = f"値下げ:{diff.drop_count}件 / 新規:{diff.new_count}件 / 値上げ:{diff.rise_count}件"

    if diff.drop_count == 0 and diff.new_count == 0 and diff.rise_count == 0:
        body = f"{header}\n{summary}\n目立った価格変動はありませんでした。\n#不動産 #マンション価格"
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
            f"新規: {newest.name} {format_man(newest.price_man)}"
        )

    parts = [header, summary, *highlight_lines, "#不動産 #マンション価格"]
    draft = "\n".join(parts)
    return _trim(draft, max_chars)


def _trim(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    ellipsis = "…"
    return text[: max_chars - len(ellipsis)] + ellipsis
