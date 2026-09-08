from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import (
    citywide_average_price_by_date,
    get_latest_two_snapshots,
    get_listings_for_snapshot,
    init_db,
    list_snapshots,
    list_watch_configs,
)
from src.diff import compare_listings, format_man
from src.listing_fields import parse_station_name, parse_walk_minutes
from src.pipeline import load_diff_for_config, price_history
from src.remote_sync import resolve_remote_json_url, sync_from_remote

st.set_page_config(page_title="ダッシュボード", page_icon="📊", layout="wide")
init_db()

st.title("ダッシュボード")
st.caption(
    "データは GitHub Actions が日次更新します。"
    "値下げは行政区を分けず一覧表示します。"
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
    st.info("データがありません。「最新データを読み込み」を押してください。")
    st.stop()


def load_citywide_drops():
    drops = []
    for config in configs:
        current_meta, previous_meta = get_latest_two_snapshots(config.id)
        if current_meta is None or previous_meta is None:
            continue
        diff = compare_listings(
            get_listings_for_snapshot(previous_meta.id),
            get_listings_for_snapshot(current_meta.id),
            ward_name=config.name,
        )
        drops.extend(diff.price_drops)
    drops.sort(
        key=lambda item: (
            item.delta_man if item.delta_man is not None else 0,
            item.name,
        )
    )
    return drops


@st.fragment(run_every=timedelta(minutes=5))
def render_dashboard() -> None:
    st.caption(f"表示更新: {datetime.now():%Y-%m-%d %H:%M:%S}")
    drops = load_citywide_drops()

    col1, col2, col3 = st.columns(3)
    col1.metric("監視区数", len(configs))
    total_listings = 0
    for config in configs:
        snaps = list_snapshots(config.id)
        if snaps:
            total_listings += snaps[0].listing_count
    col2.metric("最新件数（合計）", total_listings)
    col3.metric("値下げ（全区）", len(drops))

    city_hist = citywide_average_price_by_date()
    if city_hist:
        st.subheader("平均価格の推移（全区・過去分を保持）")
        hist_df = pd.DataFrame(
            city_hist,
            columns=["日付", "平均価格_万円", "件数"],
        )
        chart_df = hist_df.set_index("日付")[["平均価格_万円"]]
        if len(chart_df) == 1:
            st.bar_chart(chart_df)
        else:
            st.line_chart(chart_df)
        st.dataframe(hist_df, use_container_width=True, hide_index=True)

    st.subheader("値下げ一覧（全区横断）")
    if drops:
        drop_df = pd.DataFrame(
            [
                {
                    "物件名": item.name,
                    "旧価格": format_man(item.old_price_man),
                    "新価格": format_man(item.new_price_man),
                    "差額": format_man(item.delta_man),
                    "最寄り駅": item.station_name
                    or parse_station_name(item.station)
                    or "-",
                    "駅徒歩": (
                        f"徒歩{item.walk_minutes}分"
                        if item.walk_minutes is not None
                        else (
                            f"徒歩{parse_walk_minutes(item.station)}分"
                            if parse_walk_minutes(item.station) is not None
                            else "-"
                        )
                    ),
                    "面積": item.area_sqm,
                    "間取り": item.layout or "-",
                    "階数": item.floor or "-",
                    "区": item.ward_name,
                    "URL": item.url,
                }
                for item in drops
            ]
        )
        st.dataframe(drop_df, use_container_width=True, hide_index=True)
    else:
        st.write("値下げはありません。")

    st.subheader("区ごとの参考指標")
    labels = {f"{c.id}: {c.name}": c.id for c in configs}
    selected_label = st.selectbox("監視対象", list(labels.keys()))
    config_id = labels[selected_label]
    _, diff, current_avg, previous_avg = load_diff_for_config(config_id)
    snaps = list_snapshots(config_id)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("最新件数", snaps[0].listing_count if snaps else 0)
    m2.metric("値下げ", diff.drop_count if diff else 0)
    m3.metric("新規", diff.new_count if diff else 0)
    avg_delta = None
    if current_avg is not None and previous_avg is not None:
        avg_delta = round(current_avg - previous_avg, 1)
    m4.metric(
        "平均価格（万円）",
        f"{current_avg:.0f}" if current_avg is not None else "-",
        f"{avg_delta:+.0f}" if avg_delta is not None else None,
    )

    history = price_history(config_id)
    if history:
        hist_df = pd.DataFrame(history, columns=["日付", "平均価格_万円"]).set_index("日付")
        if len(hist_df) == 1:
            st.bar_chart(hist_df)
        else:
            st.line_chart(hist_df)


render_dashboard()
