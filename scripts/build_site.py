"""Build a mobile-friendly static site from published JSON."""

from __future__ import annotations

import argparse
import html
import json
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.citywide import CitywideComparison, compare_citywide
from src.daily_insight import build_daily_insight, render_insight_html
from src.diff import DiffResult, PriceChange, format_man
from src.listing_display import (
    WALK_FILTERS,
    area_unit_band,
    built_age_years,
    format_built_age,
    price_band,
    price_band_start,
    ward_label,
)
from src.listing_fields import parse_floor_from_detail_html
from src.property_history import (
    PricePoint,
    build_property_histories,
    format_price_history,
    history_for_listing,
)
from src.scraper.suumo import default_fetch
from src.tweet_draft import build_tweet_draft

PUBLISH_DIR = ROOT / "data" / "published"
SITE_DIR = ROOT / "site"
TABLE_SCRIPT = Path(__file__).with_name("drops_table.js")
logger = logging.getLogger(__name__)

DROP_COLUMNS: tuple[tuple[str, str, str, str], ...] = (
    ("name", "物件名", "text", "text"),
    ("ward", "行政区", "text", "exact"),
    ("address", "住所", "text", "text"),
    ("band", "価格帯", "number", "exact"),
    ("history", "価格履歴", "text", "text"),
    ("old", "旧価格", "number", "price"),
    ("new", "新価格", "number", "price"),
    ("delta", "差額", "number", "exact"),
    ("station", "最寄り駅", "text", "text"),
    ("walk", "駅徒歩", "number", "walk"),
    ("area", "面積", "number", "area"),
    ("layout", "間取り", "text", "exact"),
    ("built", "築年数", "number", "exact"),
    ("floor", "階数", "text", "exact"),
    ("url", "リンク", "text", "exact"),
)


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _escape(text: object) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def _walk_text(minutes: int | None) -> str:
    return f"徒歩{minutes}分" if minutes is not None else "-"


def _area_text(area: float | None) -> str:
    return f"{area:.2f}m2" if area is not None else "-"


def enrich_floors(
    drops: list[PriceChange],
    *,
    max_fetch: int = 40,
    interval_sec: float = 1.5,
) -> list[PriceChange]:
    enriched: list[PriceChange] = []
    fetched = 0
    for item in drops:
        floor = item.floor
        if not floor and fetched < max_fetch and item.url:
            try:
                html_text = default_fetch(item.url)
                floor = parse_floor_from_detail_html(html_text) or floor
                fetched += 1
                time.sleep(interval_sec)
            except Exception as exc:  # noqa: BLE001
                logger.warning("floor enrich failed url=%s err=%s", item.url, exc)
        enriched.append(
            PriceChange(
                property_id=item.property_id,
                name=item.name,
                old_price_man=item.old_price_man,
                new_price_man=item.new_price_man,
                delta_man=item.delta_man,
                url=item.url,
                address=item.address,
                station=item.station,
                station_name=item.station_name,
                walk_minutes=item.walk_minutes,
                area_sqm=item.area_sqm,
                layout=item.layout,
                floor=floor,
                ward_name=item.ward_name,
                built_year=item.built_year,
            )
        )
    return enriched


def _attr(value: object) -> str:
    return _escape(value)


def _header_row() -> str:
    cells = []
    for key, label, col_type, _mode in DROP_COLUMNS:
        cells.append(
            f'<th data-key="{key}" data-type="{col_type}">'
            f'<button type="button" class="sort-label" data-sort-key="{key}" data-sort-dir="toggle">'
            f"{_escape(label)}</button>"
            '<span class="sort-btns">'
            f'<button type="button" data-sort-key="{key}" data-sort-dir="asc" aria-label="{_escape(label)} 昇順">▲</button>'
            f'<button type="button" data-sort-key="{key}" data-sort-dir="desc" aria-label="{_escape(label)} 降順">▼</button>'
            "</span></th>"
        )
    return "<tr>" + "".join(cells) + "</tr>"


def _sort_bar() -> str:
    options = [
        f'<option value="{key}" data-type="{col_type}">{_escape(label)}</option>'
        for key, label, col_type, _mode in DROP_COLUMNS
    ]
    return (
        '<div class="sort-bar">'
        "<label for='sort-key'>並び替え</label>"
        f'<select id="sort-key">{"".join(options)}</select>'
        '<button type="button" id="sort-asc">昇順</button>'
        '<button type="button" id="sort-desc">降順</button>'
        "</div>"
    )


def _row_values(
    item: PriceChange,
    histories: dict[str, list[PricePoint]],
    snapshot_date: str,
) -> dict[str, tuple[str, str, str]]:
    points = history_for_listing(histories, item.url, item.property_id)
    history_text = format_price_history(points)
    age = built_age_years(item.built_year, snapshot_date)
    built_text = format_built_age(item.built_year, snapshot_date)
    ward = ward_label(item.ward_name)
    band = price_band(item.new_price_man)
    band_start = price_band_start(item.new_price_man)
    old_text = format_man(item.old_price_man)
    new_text = format_man(item.new_price_man)
    area_text = _area_text(item.area_sqm)
    return {
        "name": (item.name, item.name, item.name),
        "ward": (ward, ward, ward),
        "address": (item.address or "-", item.address or "-", item.address or "-"),
        "band": (band, "" if band_start is None else str(band_start), band),
        "history": (history_text, history_text, history_text),
        "old": (
            old_text,
            str(item.old_price_man or ""),
            price_band(item.old_price_man),
        ),
        "new": (
            new_text,
            str(item.new_price_man or ""),
            price_band(item.new_price_man),
        ),
        "delta": (
            format_man(item.delta_man),
            str(item.delta_man or ""),
            format_man(item.delta_man),
        ),
        "station": (
            item.station_name or "-",
            item.station_name or "-",
            item.station_name or "-",
        ),
        "walk": (
            _walk_text(item.walk_minutes),
            str(item.walk_minutes if item.walk_minutes is not None else ""),
            str(item.walk_minutes if item.walk_minutes is not None else ""),
        ),
        "area": (
            area_text,
            str(item.area_sqm if item.area_sqm is not None else ""),
            area_unit_band(item.area_sqm),
        ),
        "layout": (item.layout or "-", item.layout or "-", item.layout or "-"),
        "built": (built_text, str(age if age is not None else ""), built_text),
        "floor": (item.floor or "-", item.floor or "-", item.floor or "-"),
        "url": ("SUUMO", item.url, "SUUMO"),
    }


def _as_float(raw: str) -> float | None:
    try:
        return float(raw)
    except ValueError:
        return None


def _filter_options(
    drops: list[PriceChange],
    histories: dict[str, list[PricePoint]],
    snapshot_date: str,
) -> dict[str, list[str]]:
    collected: dict[str, dict[str, float | None]] = {
        key: {} for key, _label, _typ, _mode in DROP_COLUMNS
    }
    for item in drops:
        values = _row_values(item, histories, snapshot_date)
        for key, (_text, sort_value, filter_value) in values.items():
            if not filter_value:
                continue
            numeric = _as_float(sort_value)
            if filter_value not in collected[key]:
                collected[key][filter_value] = numeric
                continue
            previous = collected[key][filter_value]
            if numeric is not None and (previous is None or numeric < previous):
                collected[key][filter_value] = numeric

    options: dict[str, list[str]] = {}
    type_by_key = {key: col_type for key, _label, col_type, _mode in DROP_COLUMNS}
    mode_by_key = {key: mode for key, _label, _typ, mode in DROP_COLUMNS}
    for key, pairs in collected.items():
        use_numeric = mode_by_key[key] in {"price", "area", "walk"} or type_by_key[key] == "number"

        def sort_key(
            text: str,
            current_pairs: dict[str, float | None] = pairs,
            numeric: bool = use_numeric,
        ) -> tuple:
            if numeric:
                raw = current_pairs[text]
                if raw is None:
                    return (1, 0.0, text)
                return (0, raw, text)
            return (0, 0.0, text)

        options[key] = sorted(pairs, key=sort_key)
    return options


def _filter_control(key: str, label: str, mode: str, options: list[str]) -> str:
    if mode == "text":
        return (
            f'<input type="search" data-filter="{key}" data-filter-mode="text" '
            f'placeholder="{_escape(label)}" aria-label="{_escape(label)}で検索" />'
        )
    if mode == "walk":
        choices = ['<option value="">すべて</option>']
        for token, walk_label in WALK_FILTERS:
            choices.append(f'<option value="{token}">{_escape(walk_label)}</option>')
        return (
            f'<select data-filter="{key}" data-filter-mode="walk" '
            f'aria-label="{_escape(label)}で絞り込み">{"".join(choices)}</select>'
        )
    choices = ['<option value="">すべて</option>']
    for value in options:
        choices.append(f'<option value="{_attr(value)}">{_escape(value)}</option>')
    return (
        f'<select data-filter="{key}" data-filter-mode="{mode}" '
        f'aria-label="{_escape(label)}で絞り込み">{"".join(choices)}</select>'
    )


def _filter_row(options: dict[str, list[str]]) -> str:
    cells = []
    for key, label, _col_type, mode in DROP_COLUMNS:
        cells.append(f"<th>{_filter_control(key, label, mode, options.get(key, []))}</th>")
    return '<tr class="filters">' + "".join(cells) + "</tr>"


def _drop_rows(
    drops: list[PriceChange],
    histories: dict[str, list[PricePoint]],
    snapshot_date: str,
) -> str:
    if not drops:
        return f"<tr><td colspan='{len(DROP_COLUMNS)}'>値下げはありません</td></tr>"
    rows = []
    for item in drops:
        values = _row_values(item, histories, snapshot_date)
        attrs = []
        cells = []
        for key, _label, _col_type, _mode in DROP_COLUMNS:
            text, sort_value, filter_value = values[key]
            attrs.append(f'data-{key}="{_attr(text)}"')
            if sort_value != text:
                attrs.append(f'data-{key}-sort="{_attr(sort_value)}"')
            if filter_value != text:
                attrs.append(f'data-{key}-filter="{_attr(filter_value)}"')
            if key == "url":
                cells.append(
                    f"<td><a href='{_escape(item.url)}' target='_blank' rel='noopener'>"
                    f"{_escape(text)}</a></td>"
                )
            else:
                cells.append(f"<td>{_escape(text)}</td>")
        rows.append("<tr " + " ".join(attrs) + ">" + "".join(cells) + "</tr>")
    return "".join(rows)


def render_html(
    current: dict,
    previous: dict | None,
    drops: list[PriceChange],
    histories: dict[str, list[PricePoint]],
    comparison: CitywideComparison | None = None,
) -> str:
    snapshot_date = current.get("snapshot_date", "-")
    generated_at = current.get("generated_at", "-")
    listing_count = current.get("listing_count", 0)
    config_count = current.get("config_count", 0)
    day = str(snapshot_date)
    filter_row = _filter_row(_filter_options(drops, histories, day))
    drop_rows = _drop_rows(drops, histories, day)
    insight = build_daily_insight(current, previous, comparison)
    insight_html = render_insight_html(insight)

    summary_diff = DiffResult(
        price_drops=drops,
        price_rises=[],
        new_listings=[],
        removed_listings=[],
        unchanged_count=0,
    )
    draft = build_tweet_draft("東京23区", summary_diff)
    table_js = TABLE_SCRIPT.read_text(encoding="utf-8")

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SUUMO価格トラッキング</title>
  <style>
    :root {{
      --bg: #f6f3ee;
      --ink: #1c1a17;
      --muted: #5f574e;
      --card: #fffdf8;
      --line: #ddd4c8;
      --accent: #0f5c4c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Hiragino Sans", "Noto Sans JP", sans-serif;
      background: linear-gradient(180deg, #efe8dc 0%, var(--bg) 240px);
      color: var(--ink);
      line-height: 1.5;
    }}
    header {{
      padding: 1.25rem 1rem 0.75rem;
      position: sticky;
      top: 0;
      backdrop-filter: blur(8px);
      background: rgba(246, 243, 238, 0.92);
      border-bottom: 1px solid var(--line);
      z-index: 10;
    }}
    h1 {{ margin: 0; font-size: 1.35rem; }}
    .sub {{ margin: 0.35rem 0 0; color: var(--muted); font-size: 0.9rem; }}
    main {{ padding: 1rem; max-width: 1100px; margin: 0 auto; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 1rem;
      margin: 0 0 1rem;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.5rem;
    }}
    .metrics div {{
      background: #f3eee5;
      border-radius: 12px;
      padding: 0.55rem 0.6rem;
    }}
    .metrics .label {{ display: block; color: var(--muted); font-size: 0.72rem; }}
    .draft {{
      white-space: pre-wrap;
      background: #1c1a17;
      color: #f6f3ee;
      border-radius: 12px;
      padding: 0.85rem;
      font-size: 0.86rem;
    }}
    .table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.8rem;
      min-width: 1180px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      text-align: left;
      padding: 0.45rem 0.35rem;
      vertical-align: top;
    }}
    th[data-key] {{
      color: var(--muted);
      font-weight: 600;
      white-space: nowrap;
      user-select: none;
    }}
    th[data-key] .sort-label {{
      display: block;
      padding: 0;
      border: 0;
      background: none;
      color: inherit;
      font: inherit;
      cursor: pointer;
      text-align: left;
    }}
    th[data-key] .sort-label:hover {{ color: var(--accent); }}
    .sort-btns {{
      display: inline-flex;
      gap: 0.15rem;
      margin-left: 0.2rem;
    }}
    .sort-btns button,
    .sort-bar button {{
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 6px;
      padding: 0.05rem 0.3rem;
      font-size: 0.68rem;
      cursor: pointer;
      color: var(--muted);
    }}
    th[aria-sort="ascending"] .sort-btns button[data-sort-dir="asc"],
    th[aria-sort="descending"] .sort-btns button[data-sort-dir="desc"] {{
      color: var(--accent);
      border-color: var(--accent);
    }}
    .sort-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      align-items: center;
      margin: 0.55rem 0 0.75rem;
    }}
    .sort-bar select {{
      min-width: 8rem;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0.28rem 0.35rem;
      background: #fff;
    }}
    tr.filters th {{
      padding: 0.2rem 0.2rem 0.45rem;
      font-weight: 400;
    }}
    tr.filters select,
    tr.filters input {{
      width: 100%;
      min-width: 5.5rem;
      max-width: 11rem;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0.28rem 0.2rem;
      font-size: 0.72rem;
      background: #fff;
    }}
    a {{ color: var(--accent); }}
    .insight-headline {{
      font-size: 1.05rem;
      font-weight: 700;
      margin: 0.35rem 0 0.6rem;
    }}
    .insight h3 {{
      font-size: 0.92rem;
      margin: 1rem 0 0.4rem;
    }}
    .insight ul {{
      margin: 0;
      padding-left: 1.15rem;
    }}
    .insight-note {{
      color: var(--muted);
      font-size: 0.86rem;
      margin: 0.75rem 0 0;
    }}
    .insight-bar {{
      margin: 0.35rem 0 0.55rem;
    }}
    .insight-bar-label {{
      display: block;
      font-size: 0.78rem;
      color: var(--muted);
      margin-bottom: 0.15rem;
    }}
    .insight-bar-track {{
      display: block;
      height: 8px;
      background: #f3eee5;
      border-radius: 999px;
      overflow: hidden;
    }}
    .insight-bar-fill {{
      display: block;
      height: 100%;
      background: var(--accent);
    }}
    footer {{
      text-align: center;
      color: var(--muted);
      font-size: 0.8rem;
      padding: 1rem;
    }}
    @media (min-width: 720px) {{
      .metrics {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
      h1 {{ font-size: 1.7rem; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>SUUMO価格トラッキング</h1>
    <p class="sub">更新日 {_escape(snapshot_date)} / {config_count}区 / {listing_count}件<br/>生成 {_escape(generated_at)}</p>
  </header>
  <main>
    <section class="card">
      <div class="metrics">
        <div><span class="label">値下げ件数</span><strong>{len(drops)}</strong></div>
        <div><span class="label">監視区数</span><strong>{config_count}</strong></div>
        <div><span class="label">監視物件数</span><strong>{listing_count}</strong></div>
        <div><span class="label">更新日</span><strong>{_escape(snapshot_date)}</strong></div>
      </div>
    </section>

    {insight_html}

    <section class="card">
      <h2>X投稿下書き（23区まとめて）</h2>
      <pre class="draft">{_escape(draft)}</pre>
    </section>

    <section class="card">
      <h2>値下げ一覧（全区横断）</h2>
      <p class="sub">物件名・住所・価格履歴・最寄り駅は文字検索。価格は1000万円単位、駅徒歩は分数、面積は10m2単位で絞り込めます。表示 <span id="drops-visible-count">{len(drops)}</span> / {len(drops)}件</p>
      {_sort_bar()}
      <div class="table-wrap"><table id="drops-table">
        <thead>
          {_header_row()}
          {filter_row}
        </thead>
        <tbody>
          {drop_rows}
        </tbody>
      </table></div>
    </section>
  </main>
  <footer>
    データは GitHub Actions が日次更新します。<br/>
    <a href="https://github.com/jumkita/suumo-price-tracker">GitHubリポジトリ</a>
  </footer>
  <script>
{table_js}
  </script>
</body>
</html>
"""


def build_site(
    publish_dir: Path = PUBLISH_DIR,
    site_dir: Path = SITE_DIR,
    *,
    enrich_floor: bool = True,
) -> Path:
    latest = _load(publish_dir / "daily_prices.json")
    if latest is None:
        raise RuntimeError("daily_prices.json not found; export first")

    snapshot_date = latest.get("snapshot_date")
    previous = None
    if snapshot_date:
        prev_day = (date.fromisoformat(snapshot_date) - timedelta(days=1)).isoformat()
        previous = _load(publish_dir / f"daily_prices_{prev_day}.json")

    histories = build_property_histories(publish_dir)
    comparison = compare_citywide(latest, previous)
    drops = comparison.drops if comparison is not None else []
    if enrich_floor:
        drops = enrich_floors(drops)

    site_dir.mkdir(parents=True, exist_ok=True)
    index = site_dir / "index.html"
    index.write_text(
        render_html(latest, previous, drops, histories, comparison),
        encoding="utf-8",
    )

    data_dir = site_dir / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "daily_prices.json").write_text(
        json.dumps(latest, ensure_ascii=False),
        encoding="utf-8",
    )
    if previous is not None:
        (data_dir / f"daily_prices_{previous['snapshot_date']}.json").write_text(
            json.dumps(previous, ensure_ascii=False),
            encoding="utf-8",
        )
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description="Build GitHub Pages site")
    parser.add_argument("--publish-dir", type=Path, default=PUBLISH_DIR)
    parser.add_argument("--site-dir", type=Path, default=SITE_DIR)
    parser.add_argument("--no-enrich-floor", action="store_true")
    args = parser.parse_args()
    path = build_site(
        args.publish_dir,
        args.site_dir,
        enrich_floor=not args.no_enrich_floor,
    )
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
