from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import init_db
from src.remote_sync import resolve_remote_json_url

st.set_page_config(
    page_title="SUUMO価格トラッキング",
    page_icon="📈",
    layout="wide",
)

init_db()

st.title("SUUMO マンション価格トラッキング")
st.write(
    "中古マンションの検索結果を日次で取得し、価格変動をモニタリングします。"
    "左サイドバーから各画面へ移動してください。"
)

remote_url = ""
try:
    remote_url = str(st.secrets.get("DAILY_PRICES_JSON_URL", "") or "").strip()
except Exception:
    remote_url = ""
remote_url = resolve_remote_json_url(remote_url or None)

st.markdown(
    f"""
### 使い方
1. **ダッシュボード** の「最新データを読み込み」でクラウドJSONを取り込む
2. 全エリアの値下げと、物件ごとの過去価格を確認する
3. **X投稿下書き** で投稿文をコピーする（2日分のデータが必要）

### 自動更新
- GitHub Actions が毎朝スクレイピングして JSON を更新します（PC不要）
- 公開JSON: `{remote_url}`

### 注意
- 個人利用・低頻度を前提としてください
- SUUMO の利用規約・robots.txt を確認したうえでご利用ください
"""
)
