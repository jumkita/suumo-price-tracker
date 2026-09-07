from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import init_db, list_watch_configs
from src.pipeline import load_diff_for_config
from src.tweet_draft import build_tweet_draft

st.set_page_config(page_title="X投稿下書き", page_icon="𝕏", layout="centered")
init_db()

st.title("X投稿下書き")
st.caption("自動投稿はしません。下書きをコピーして X に貼り付けてください。")

configs = list_watch_configs()
if not configs:
    st.info("監視設定がありません。")
    st.stop()

labels = {f"{c.id}: {c.name}": c.id for c in configs}
selected_label = st.selectbox("監視対象", list(labels.keys()))
config_id = labels[selected_label]

config, diff, _, _ = load_diff_for_config(config_id)
if config is None:
    st.error("監視設定が見つかりません。")
    st.stop()

if diff is None:
    st.warning("比較できるスナップショットが不足しています。2日分取得してから下書きを生成できます。")
    st.stop()

draft = build_tweet_draft(config.name, diff)
st.subheader("投稿文")
st.code(draft, language=None)
st.write(f"文字数: {len(draft)}")
st.info("上の枠を選択してコピーし、X の投稿欄へ貼り付けてください。")
