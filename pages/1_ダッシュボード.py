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
    get_latest_two_snapshots,
    get_listings_for_snapshot,
    init_db,
    listing_price_histories,
    list_snapshots,
    list_watch_configs,
)
from src.diff import compare_listings, format_man
from src.listing_display import format_built_age, price_band, ward_label
from src.listing_fields import parse_station_name, parse_walk_minutes
from src.property_history import (
    PricePoint,
    build_property_histories,
    format_price_history,
    history_for_listing,
)
from src.remote_sync import resolve_remote_json_url, sync_from_remote

st.set_page_config(page_title="ダッシュボード", page_icon="📊", layout="wide")
init_db()

st.title("ダッシュボード")
st.caption(
    "データは GitHub Actions が日次更新します。"
    "値下げは行政区を分けず、物件ごとの過去価格をすべて表示します。"
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


def load_histories():
    publish_dir = ROOT / "data" / "published"
    dated = list(publish_dir.glob("daily_prices_????-??-??.json"))
    if dated:
        return build_property_histories(publish_dir)
    raw = listing_price_histories()
    converted = {}
    for key, points in raw.items():
        converted[key] = [
            PricePoint(day, price, name, url, "")
            for day, price, name, url in points
        ]
    return converted


@st.fragment(run_every=timedelta(minutes=5))
def render_dashboard() -> None:
    st.caption(f"表示更新: {datetime.now():%Y-%m-%d %H:%M:%S}")
    drops = load_citywide_drops()
    histories = load_histories()

    col1, col2, col3 = st.columns(3)
    col1.metric("監視区数", len(configs))
    total_listings = 0
    for config in configs:
        snaps = list_snapshots(config.id)
        if snaps:
            total_listings += snaps[0].listing_count
    col2.metric("最新件数（合計）", total_listings)
    col3.metric("値下げ（全区）", len(drops))

    st.subheader("値下げ一覧（全区横断）")
    snapshot_date = ""
    for config in configs:
        snaps = list_snapshots(config.id)
        if snaps:
            snapshot_date = snaps[0].snapshot_date
            break
    if drops:
        drop_df = pd.DataFrame(
            [
                {
                    "物件名": item.name,
                    "行政区": ward_label(item.ward_name),
                    "住所": item.address or "-",
                    "価格帯": price_band(item.new_price_man),
                    "価格履歴": format_price_history(
                        history_for_listing(histories, item.url, item.property_id)
                    ),
                    "旧価格": item.old_price_man,
                    "新価格": item.new_price_man,
                    "差額": item.delta_man,
                    "最寄り駅": item.station_name
                    or parse_station_name(item.station)
                    or "-",
                    "駅徒歩": item.walk_minutes
                    if item.walk_minutes is not None
                    else parse_walk_minutes(item.station),
                    "面積": item.area_sqm,
                    "間取り": item.layout or "-",
                    "築年数": format_built_age(item.built_year, snapshot_date),
                    "階数": item.floor or "-",
                    "URL": item.url,
                }
                for item in drops
            ]
        )
        all_label = "（すべて）"
        with st.expander("列で絞り込み", expanded=True):
            filter_cols = st.columns(4)
            filtered = drop_df
            column_names = list(drop_df.columns)
            for index, column in enumerate(column_names):
                choices = [all_label] + sorted(
                    drop_df[column].dropna().astype(str).unique().tolist()
                )
                query = filter_cols[index % 4].selectbox(
                    column, choices, key=f"drop_filter_{column}"
                )
                if query != all_label:
                    filtered = filtered[filtered[column].astype(str) == query]
        st.caption(f"表示 {len(filtered)} / {len(drop_df)}件。列名クリックでソートできます。")
        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
            column_config={
                "旧価格": st.column_config.NumberColumn(format="%d万円"),
                "新価格": st.column_config.NumberColumn(format="%d万円"),
                "差額": st.column_config.NumberColumn(format="%d万円"),
                "駅徒歩": st.column_config.NumberColumn(format="%d分"),
                "面積": st.column_config.NumberColumn(format="%.2f m2"),
                "URL": st.column_config.LinkColumn("リンク"),
            },
        )
    else:
        st.write("値下げはありません。")


render_dashboard()
