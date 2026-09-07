from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import init_db, list_snapshots, list_watch_configs
from src.diff import format_man
from src.pipeline import load_diff_for_config, price_history
from src.remote_sync import resolve_remote_json_url, sync_from_remote

st.set_page_config(page_title="ダッシュボード", page_icon="📊", layout="wide")
init_db()

st.title("ダッシュボード")
st.caption(
    "データは GitHub Actions が日次更新します。"
    "下のボタンで最新 JSON を取り込み、表示は5分ごとに自動再読込します。"
)


def _secret_url() -> str:
    try:
        return str(st.secrets.get("DAILY_PRICES_JSON_URL", "") or "").strip()
    except Exception:
        return ""


remote_url = resolve_remote_json_url(_secret_url() or None)

sync_cols = st.columns([2, 1])
sync_cols[0].caption(f"JSON: `{remote_url}`")
if sync_cols[1].button("最新データを読み込み", type="primary"):
    with st.spinner("GitHub raw JSON を取得中..."):
        try:
            result = sync_from_remote(remote_url)
            st.success(
                f"取込完了: {result.snapshot_date} / "
                f"{result.config_count}区 / {result.listing_count}件"
            )
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(f"取込失敗: {exc}")

configs = list_watch_configs()
if not configs:
    st.info("データがありません。「最新データを読み込み」を押すか、監視設定から取得してください。")
    st.stop()

labels = {f"{c.id}: {c.name}": c.id for c in configs}
selected_label = st.selectbox("監視対象", list(labels.keys()))
config_id = labels[selected_label]


@st.fragment(run_every=timedelta(minutes=5))
def render_dashboard(selected_config_id: int) -> None:
    st.caption(f"表示更新: {datetime.now():%Y-%m-%d %H:%M:%S}")
    _, diff, current_avg, previous_avg = load_diff_for_config(selected_config_id)
    snaps = list_snapshots(selected_config_id)

    col1, col2, col3, col4 = st.columns(4)
    latest_count = snaps[0].listing_count if snaps else 0
    col1.metric("最新件数", latest_count)
    col2.metric("値下げ", diff.drop_count if diff else 0)
    col3.metric("新規", diff.new_count if diff else 0)

    avg_delta = None
    if current_avg is not None and previous_avg is not None:
        avg_delta = round(current_avg - previous_avg, 1)
    col4.metric(
        "平均価格（万円）",
        f"{current_avg:.0f}" if current_avg is not None else "-",
        f"{avg_delta:+.0f}" if avg_delta is not None else None,
    )

    history = price_history(selected_config_id)
    if history:
        st.subheader("平均価格の推移")
        hist_df = pd.DataFrame(history, columns=["日付", "平均価格_万円"]).set_index("日付")
        if len(hist_df) == 1:
            st.bar_chart(hist_df)
        else:
            st.line_chart(hist_df)
    else:
        st.caption("スナップショットがまだありません。")

    if diff is None:
        st.info("変動比較はスナップショットが2日分そろってから表示されます。")
    else:
        st.subheader("値下げ一覧")
        if diff.price_drops:
            drop_df = pd.DataFrame(
                [
                    {
                        "物件名": item.name,
                        "旧価格": format_man(item.old_price_man),
                        "新価格": format_man(item.new_price_man),
                        "差額": format_man(item.delta_man),
                        "駅": item.station,
                        "URL": item.url,
                    }
                    for item in diff.price_drops
                ]
            )
            st.dataframe(drop_df, use_container_width=True, hide_index=True)
        else:
            st.write("値下げはありません。")

        st.subheader("新規掲載")
        if diff.new_listings:
            new_df = pd.DataFrame(
                [
                    {
                        "物件名": item.name,
                        "価格": format_man(item.price_man),
                        "面積": item.area_sqm,
                        "間取り": item.layout,
                        "駅": item.station,
                        "URL": item.url,
                    }
                    for item in diff.new_listings
                ]
            )
            st.dataframe(new_df, use_container_width=True, hide_index=True)
        else:
            st.write("新規はありません。")

        with st.expander("値上げ・削除"):
            if diff.price_rises:
                rise_df = pd.DataFrame(
                    [
                        {
                            "物件名": item.name,
                            "旧価格": format_man(item.old_price_man),
                            "新価格": format_man(item.new_price_man),
                            "差額": format_man(item.delta_man),
                            "URL": item.url,
                        }
                        for item in diff.price_rises
                    ]
                )
                st.dataframe(rise_df, use_container_width=True, hide_index=True)
            else:
                st.write("値上げはありません。")

            if diff.removed_listings:
                removed_df = pd.DataFrame(
                    [
                        {
                            "物件名": item.name,
                            "価格": format_man(item.price_man),
                            "URL": item.url,
                        }
                        for item in diff.removed_listings
                    ]
                )
                st.dataframe(removed_df, use_container_width=True, hide_index=True)
            else:
                st.write("削除（掲載終了）はありません。")

    if snaps:
        st.subheader("取得履歴")
        snap_df = pd.DataFrame(
            [
                {
                    "日付": s.snapshot_date,
                    "件数": s.listing_count,
                    "取得時刻": s.fetched_at,
                }
                for s in snaps
            ]
        )
        st.dataframe(snap_df, use_container_width=True, hide_index=True)


render_dashboard(config_id)
