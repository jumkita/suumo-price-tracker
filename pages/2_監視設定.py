from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import (
    add_watch_config,
    delete_watch_config,
    init_db,
    list_watch_configs,
    set_watch_enabled,
)
from src.pipeline import run_config
from src.remote_sync import resolve_remote_json_url, sync_from_remote
from src.scraper.suumo import normalize_search_url

st.set_page_config(page_title="監視設定", page_icon="⚙️", layout="wide")
init_db()

st.title("監視設定")

st.subheader("クラウド自動更新（推奨）")
st.markdown(
    """
株分析Appと同じく、**GitHub Actions** が毎朝スクレイピングし、
`data/published/daily_prices.json` を更新します。PCスリープの影響を受けません。

- Actions: `Daily SUUMO Price Scrape`
- 既定スケジュール: 毎日 06:30 JST 目安（UTC 21:30）
- 確実起動: cron-job.org などから `repository_dispatch`（`daily-price-scrape`）
"""
)

remote_url = ""
try:
    remote_url = str(st.secrets.get("DAILY_PRICES_JSON_URL", "") or "").strip()
except Exception:
    remote_url = ""
remote_url = resolve_remote_json_url(remote_url or None)
st.code(remote_url, language=None)

if st.button("最新クラウドデータを取り込む", type="primary"):
    with st.spinner("取得中..."):
        try:
            result = sync_from_remote(remote_url)
            st.success(
                f"{result.snapshot_date}: {result.config_count}区 / {result.listing_count}件"
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"失敗: {exc}")

st.divider()
st.caption(
    "以下はローカル手動用です。日常の自動更新は GitHub Actions 側で行います。"
)

with st.form("add_watch"):
    name = st.text_input("監視名", placeholder="例: 千代田区 中古マンション")
    search_url = st.text_input(
        "検索結果URL",
        placeholder="https://suumo.jp/jj/bukken/ichiran/...",
    )
    max_pages = st.number_input("最大ページ数", min_value=1, max_value=100, value=50)
    submitted = st.form_submit_button("監視を追加", type="primary")

if submitted:
    if not name.strip() or not search_url.strip():
        st.warning("監視名と検索結果URLを入力してください。")
    elif "suumo.jp" not in search_url:
        st.warning("SUUMOのURLを入力してください。")
    else:
        normalized = normalize_search_url(search_url)
        config_id = add_watch_config(name.strip(), normalized, max_pages=int(max_pages))
        st.success(f"監視を追加しました（ID={config_id}）")
        st.rerun()

st.subheader("登録済み監視")
configs = list_watch_configs()
if not configs:
    st.info("まだ監視がありません。クラウド取込、または下から追加してください。")
else:
    for config in configs:
        row = st.columns([3, 4, 1, 1, 1])
        row[0].write(f"**{config.name}**")
        row[1].caption(config.search_url)
        row[2].write(f"最大{config.max_pages}p")
        enabled = row[3].checkbox(
            "有効",
            value=config.enabled,
            key=f"enabled_{config.id}",
        )
        if enabled != config.enabled:
            set_watch_enabled(config.id, enabled)
            st.rerun()
        if row[4].button("削除", key=f"del_{config.id}"):
            delete_watch_config(config.id)
            st.rerun()

st.subheader("今すぐ取得（ローカル）")
if not configs:
    st.caption("監視を追加すると実行できます。")
else:
    options = {f"{c.id}: {c.name}": c.id for c in configs if c.enabled}
    if not options:
        st.warning("有効な監視がありません。")
    else:
        selected = st.selectbox("実行する監視", list(options.keys()))
        interval = st.slider("リクエスト間隔（秒）", min_value=1.5, max_value=5.0, value=2.0, step=0.5)
        if st.button("スクレイピングを実行"):
            config_id = options[selected]
            with st.spinner("取得中（ページ間に待機を入れます）..."):
                result = run_config(
                    config_id,
                    request_interval_sec=float(interval),
                )
            if result.error:
                st.error(f"失敗: {result.error}")
            else:
                drop = result.diff.drop_count if result.diff else "（比較なし）"
                new = result.diff.new_count if result.diff else "（比較なし）"
                st.success(
                    f"完了: 取得{result.raw_listing_count}件 → "
                    f"最安値集約後{result.listing_count}件 / 値下げ={drop} / 新規={new}"
                )
