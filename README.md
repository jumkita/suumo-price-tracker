# SUUMO マンション価格トラッキング

Streamlit で SUUMO 中古マンションの検索結果を日次監視し、価格変動を確認・X投稿下書きを作成するツールです。

株分析App（`stock-daytrade`）と同じく、**GitHub Actions がクラウドで日次更新**し、Streamlit は公開 JSON を読み込みます。PCのスリープに依存しません。

## 前提条件

- Python 3.10+
- 個人利用・低頻度での取得を前提とする
- SUUMO の利用規約・robots.txt を確認したうえで利用する

## セットアップ

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Streamlit Secrets（任意）

`.streamlit/secrets.toml`:

```toml
DAILY_PRICES_JSON_URL = "https://raw.githubusercontent.com/jumkita/suumo-price-tracker/main/data/published/daily_prices.json"
```

未設定時も上記 URL を既定値として使います。

## 画面での確認

1. ダッシュボードの **「最新データを読み込み」** でクラウドJSONを取込
2. 区を選んで件数・差分・推移を確認
3. X投稿下書きは2日分のスナップショットがあるとき生成可能

## クラウド自動更新（本命）

### GitHub Actions

ワークフロー: `Daily SUUMO Price Scrape`

- `schedule`: 毎日 **06:30 JST 目安**（`30 21 * * *` UTC）
- `workflow_dispatch`: Actions 画面から手動実行
- `repository_dispatch`: 外部cronから確実に起動（イベント名 `daily-price-scrape`）

成果物:

- `data/published/daily_prices.json`（最新）
- `data/published/daily_prices_YYYY-MM-DD.json`（日付別）

### 確実起動（cron-job.org など）

GitHub の `schedule` は遅延し得るため、株分析Appと同様に外部から dispatch できます。

| 項目 | 値 |
|------|-----|
| スケジュール | 毎日 **06:30**（タイムゾーン **Asia/Tokyo**） |
| メソッド | `POST` |
| URL | `https://api.github.com/repos/jumkita/suumo-price-tracker/dispatches` |
| ヘッダ | `Accept: application/vnd.github+json`、`Authorization: Bearer <PAT>`、`X-GitHub-Api-Version: 2022-11-28` |
| ボディ | `{"event_type":"daily-price-scrape"}` |

```bash
curl -sS -L -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_PAT_DISPATCH}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/jumkita/suumo-price-tracker/dispatches \
  -d '{"event_type":"daily-price-scrape"}'
```

### ローカル手動

```bash
python scripts/register_wards.py --max-pages 50
python scripts/run_daily.py
python scripts/export_published.py
python scripts/sync_from_remote.py
```

## 同一物件の扱い

仲介違いで同一物件が複数出る場合は、名称・住所・間取り・面積で同一判定し、**最安値の1件だけ**を保存します。

## テスト

```bash
pytest
```

## 補足（非推奨）

Windows タスクスケジューラ（`scripts/manage_scheduler.py`）はPC起動依存のため補助用途です。日常運用は GitHub Actions を使ってください。
