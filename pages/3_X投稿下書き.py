from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import init_db, list_snapshots, list_watch_configs
from src.pipeline import load_diff_for_config
from src.tweet_draft import build_first_day_draft, build_tweet_draft

st.set_page_config(page_title="X投稿下書き", page_icon="𝕏", layout="centered")
init_db()

st.title("X投稿下書き")
st.caption("自動投稿はしません。下書きをコピーして X に貼り付けてください。")

configs = list_watch_configs()
if not configs:
    st.info("監視設定がありません。ダッシュボードで最新データを読み込んでください。")
    st.stop()

labels = {f"{c.id}: {c.name}": c.id for c in configs}
selected_label = st.selectbox("監視対象", list(labels.keys()))
config_id = labels[selected_label]

config, diff, current_avg, _ = load_diff_for_config(config_id)
if config is None:
    st.error("監視設定が見つかりません。")
    st.stop()

snaps = list_snapshots(config_id)
latest_count = snaps[0].listing_count if snaps else 0

if diff is not None:
    draft = build_tweet_draft(config.name, diff)
else:
    draft = build_first_day_draft(
        config.name,
        listing_count=latest_count,
        avg_price_man=current_avg,
    )
    st.info("比較用の前日データがまだないため、初回用の下書きを表示しています。")

st.subheader("投稿文")
st.code(draft, language=None)
st.write(f"文字数: {len(draft)}")
st.caption("上の枠を選択してコピーし、X の投稿欄へ貼り付けてください。")
