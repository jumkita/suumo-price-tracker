"""Build a mobile-friendly static site from published JSON."""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import ListingRow
from src.diff import average_price, compare_listings, format_man
from src.tweet_draft import build_first_day_draft, build_tweet_draft

PUBLISH_DIR = ROOT / "data" / "published"
SITE_DIR = ROOT / "site"


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _listings(block: dict) -> list[ListingRow]:
    rows: list[ListingRow] = []
    for item in block.get("listings") or []:
        rows.append(
            ListingRow(
                property_id=str(item["property_id"]),
                name=str(item.get("name") or ""),
                address=str(item.get("address") or ""),
                price_man=item.get("price_man"),
                area_sqm=item.get("area_sqm"),
                layout=str(item.get("layout") or ""),
                built_year=str(item.get("built_year") or ""),
                station=str(item.get("station") or ""),
                url=str(item.get("url") or ""),
            )
        )
    return rows


def _escape(text: object) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def build_ward_section(current_block: dict, previous_block: dict | None) -> str:
    name = current_block.get("name") or "未命名"
    current = _listings(current_block)
    previous = _listings(previous_block) if previous_block else []
    avg = average_price(current)
    avg_text = f"{avg:.0f}万円" if avg is not None else "-"

    if previous:
        diff = compare_listings(previous, current)
        draft = build_tweet_draft(name, diff)
        drop_n = diff.drop_count
        new_n = diff.new_count
        rise_n = diff.rise_count
        drop_rows = "".join(
            (
                "<tr>"
                f"<td>{_escape(item.name)}</td>"
                f"<td>{_escape(format_man(item.old_price_man))}</td>"
                f"<td>{_escape(format_man(item.new_price_man))}</td>"
                f"<td>{_escape(format_man(item.delta_man))}</td>"
                f"<td><a href='{_escape(item.url)}' target='_blank' rel='noopener'>SUUMO</a></td>"
                "</tr>"
            )
            for item in diff.price_drops[:20]
        ) or "<tr><td colspan='5'>値下げなし</td></tr>"
    else:
        draft = build_first_day_draft(name, listing_count=len(current), avg_price_man=avg)
        drop_n = new_n = rise_n = 0
        drop_rows = "<tr><td colspan='5'>比較用の前日データ待ち</td></tr>"

    cheapest = sorted(
        [x for x in current if x.price_man is not None],
        key=lambda x: x.price_man or 10**12,
    )[:10]
    cheap_rows = "".join(
        (
            "<tr>"
            f"<td>{_escape(item.name)}</td>"
            f"<td>{_escape(format_man(item.price_man))}</td>"
            f"<td>{_escape(item.layout)}</td>"
            f"<td>{_escape(item.station)}</td>"
            f"<td><a href='{_escape(item.url)}' target='_blank' rel='noopener'>SUUMO</a></td>"
            "</tr>"
        )
        for item in cheapest
    ) or "<tr><td colspan='5'>データなし</td></tr>"

    return f"""
<section class="ward" id="{_escape(name)}">
  <h2>{_escape(name)}</h2>
  <div class="metrics">
    <div><span class="label">件数</span><strong>{len(current)}</strong></div>
    <div><span class="label">平均</span><strong>{_escape(avg_text)}</strong></div>
    <div><span class="label">値下げ</span><strong>{drop_n}</strong></div>
    <div><span class="label">新規</span><strong>{new_n}</strong></div>
    <div><span class="label">値上げ</span><strong>{rise_n}</strong></div>
  </div>

  <h3>X投稿下書き</h3>
  <pre class="draft">{_escape(draft)}</pre>

  <h3>値下げ（最大20件）</h3>
  <div class="table-wrap"><table>
    <thead><tr><th>物件</th><th>旧</th><th>新</th><th>差</th><th>リンク</th></tr></thead>
    <tbody>{drop_rows}</tbody>
  </table></div>

  <h3>最安値付近（10件）</h3>
  <div class="table-wrap"><table>
    <thead><tr><th>物件</th><th>価格</th><th>間取り</th><th>駅</th><th>リンク</th></tr></thead>
    <tbody>{cheap_rows}</tbody>
  </table></div>
</section>
"""


def render_html(current: dict, previous: dict | None) -> str:
    snapshot_date = current.get("snapshot_date", "-")
    generated_at = current.get("generated_at", "-")
    listing_count = current.get("listing_count", 0)
    config_count = current.get("config_count", 0)

    prev_map = {
        block.get("name"): block for block in (previous or {}).get("configs") or []
    }
    nav = "".join(
        f"<a href='#{_escape(block.get('name'))}'>{_escape(block.get('name'))}</a>"
        for block in current.get("configs") or []
    )
    sections = "".join(
        build_ward_section(block, prev_map.get(block.get("name")))
        for block in current.get("configs") or []
    )

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
    h1 {{
      margin: 0;
      font-size: 1.35rem;
      letter-spacing: 0.02em;
    }}
    .sub {{
      margin: 0.35rem 0 0;
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .nav {{
      display: flex;
      gap: 0.5rem;
      overflow-x: auto;
      padding: 0.75rem 0 0.25rem;
      -webkit-overflow-scrolling: touch;
    }}
    .nav a {{
      flex: 0 0 auto;
      text-decoration: none;
      color: var(--accent);
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 0.35rem 0.7rem;
      font-size: 0.82rem;
      white-space: nowrap;
    }}
    main {{ padding: 1rem; max-width: 920px; margin: 0 auto; }}
    .ward {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 1rem;
      margin: 0 0 1rem;
    }}
    .ward h2 {{ margin: 0 0 0.75rem; font-size: 1.1rem; }}
    .ward h3 {{ margin: 1rem 0 0.5rem; font-size: 0.95rem; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 0.5rem;
    }}
    .metrics div {{
      background: #f3eee5;
      border-radius: 12px;
      padding: 0.55rem 0.6rem;
    }}
    .metrics .label {{
      display: block;
      color: var(--muted);
      font-size: 0.72rem;
    }}
    .metrics strong {{ font-size: 1rem; }}
    .draft {{
      white-space: pre-wrap;
      background: #1c1a17;
      color: #f6f3ee;
      border-radius: 12px;
      padding: 0.85rem;
      font-size: 0.86rem;
      overflow-x: auto;
    }}
    .table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.82rem;
      min-width: 520px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      text-align: left;
      padding: 0.45rem 0.35rem;
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-weight: 600; }}
    a {{ color: var(--accent); }}
    footer {{
      text-align: center;
      color: var(--muted);
      font-size: 0.8rem;
      padding: 1rem;
    }}
    @media (min-width: 720px) {{
      .metrics {{ grid-template-columns: repeat(5, minmax(0, 1fr)); }}
      h1 {{ font-size: 1.7rem; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>SUUMO価格トラッキング</h1>
    <p class="sub">更新日 { _escape(snapshot_date) } / {config_count}区 / {listing_count}件<br/>生成 { _escape(generated_at) }</p>
    <nav class="nav">{nav}</nav>
  </header>
  <main>
    {sections}
  </main>
  <footer>
    データは GitHub Actions が日次更新します。<br/>
    <a href="https://github.com/jumkita/suumo-price-tracker">GitHubリポジトリ</a>
  </footer>
</body>
</html>
"""


def build_site(publish_dir: Path = PUBLISH_DIR, site_dir: Path = SITE_DIR) -> Path:
    latest = _load(publish_dir / "daily_prices.json")
    if latest is None:
        raise RuntimeError("daily_prices.json not found; export first")

    snapshot_date = latest.get("snapshot_date")
    previous = None
    if snapshot_date:
        prev_day = (date.fromisoformat(snapshot_date) - timedelta(days=1)).isoformat()
        previous = _load(publish_dir / f"daily_prices_{prev_day}.json")

    site_dir.mkdir(parents=True, exist_ok=True)
    index = site_dir / "index.html"
    index.write_text(render_html(latest, previous), encoding="utf-8")

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
    args = parser.parse_args()
    path = build_site(args.publish_dir, args.site_dir)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
