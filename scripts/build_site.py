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

from src.citywide import citywide_price_drops
from src.diff import DiffResult, PriceChange, format_man
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
logger = logging.getLogger(__name__)


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
            )
        )
    return enriched


def _drop_rows(
    drops: list[PriceChange],
    histories: dict[str, list[PricePoint]],
) -> str:
    if not drops:
        return "<tr><td colspan='11'>値下げはありません</td></tr>"
    rows = []
    for item in drops:
        points = history_for_listing(histories, item.url, item.property_id)
        rows.append(
            "<tr>"
            f"<td>{_escape(item.name)}</td>"
            f"<td>{_escape(format_price_history(points))}</td>"
            f"<td>{_escape(format_man(item.old_price_man))}</td>"
            f"<td>{_escape(format_man(item.new_price_man))}</td>"
            f"<td>{_escape(format_man(item.delta_man))}</td>"
            f"<td>{_escape(item.station_name or '-')}</td>"
            f"<td>{_escape(_walk_text(item.walk_minutes))}</td>"
            f"<td>{_escape(_area_text(item.area_sqm))}</td>"
            f"<td>{_escape(item.layout or '-')}</td>"
            f"<td>{_escape(item.floor or '-')}</td>"
            f"<td><a href='{_escape(item.url)}' target='_blank' rel='noopener'>SUUMO</a></td>"
            "</tr>"
        )
    return "".join(rows)


def render_html(
    current: dict,
    previous: dict | None,
    drops: list[PriceChange],
    histories: dict[str, list[PricePoint]],
) -> str:
    snapshot_date = current.get("snapshot_date", "-")
    generated_at = current.get("generated_at", "-")
    listing_count = current.get("listing_count", 0)
    config_count = current.get("config_count", 0)

    summary_diff = DiffResult(
        price_drops=drops,
        price_rises=[],
        new_listings=[],
        removed_listings=[],
        unchanged_count=0,
    )
    draft = build_tweet_draft("東京23区", summary_diff)

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
      min-width: 860px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      text-align: left;
      padding: 0.45rem 0.35rem;
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-weight: 600; white-space: nowrap; }}
    a {{ color: var(--accent); }}
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

    <section class="card">
      <h2>X投稿下書き（23区まとめて）</h2>
      <pre class="draft">{_escape(draft)}</pre>
    </section>

    <section class="card">
      <h2>値下げ一覧（全区横断）</h2>
      <p class="sub">行政区を分けず、値下げ額が大きい順です。価格履歴は保存済みの日付をすべて出します（平均は使いません）。</p>
      <div class="table-wrap"><table>
        <thead>
          <tr>
            <th>物件名</th><th>価格履歴</th><th>旧価格</th><th>新価格</th><th>差額</th>
            <th>最寄り駅</th><th>駅徒歩</th><th>面積</th><th>間取り</th><th>階数</th><th>リンク</th>
          </tr>
        </thead>
        <tbody>
          {_drop_rows(drops, histories)}
        </tbody>
      </table></div>
    </section>
  </main>
  <footer>
    データは GitHub Actions が日次更新します。<br/>
    <a href="https://github.com/jumkita/suumo-price-tracker">GitHubリポジトリ</a>
  </footer>
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
    drops = citywide_price_drops(latest, previous)
    if enrich_floor:
        drops = enrich_floors(drops)

    site_dir.mkdir(parents=True, exist_ok=True)
    index = site_dir / "index.html"
    index.write_text(
        render_html(latest, previous, drops, histories),
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
