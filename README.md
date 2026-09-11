# SUUMO マンション価格トラッキング

Streamlit / GitHub Pages で SUUMO 中古マンションの価格変動を日次監視するツールです。監視対象は **東京23区と市部（多摩地域の26市）** です。

西多摩郡（瑞穂町・日の出町・檜原村・奥多摩町）は、23区・市部と同じ `sc=` 検索だと SUUMO がエラーページを返すため含めていません。

## スマホで見る（公開ページ）

- **GitHub Pages（推奨・スマホ向け）:** https://jumkita.github.io/suumo-price-tracker/
- **リポジトリ:** https://github.com/jumkita/suumo-price-tracker
- **日次JSON:** https://raw.githubusercontent.com/jumkita/suumo-price-tracker/main/data/published/daily_prices.json

Pages は公開リポジトリの Actions が毎日更新します。公開ページの **監視エリア** に23区と市部の件数が並びます。**値下げ一覧** は前日比で下がった物件だけなので、市部を足した初日は値下げ行が空でも、監視件数には入っています。

## 前提条件

- Python 3.10+
- 個人利用・低頻度での取得を前提とする
- SUUMO の利用規約・robots.txt を確認したうえで利用する

## ローカル Streamlit

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Streamlit Secrets（任意）

`.streamlit/secrets.toml`:

```toml
DAILY_PRICES_JSON_URL = "https://raw.githubusercontent.com/jumkita/suumo-price-tracker/main/data/published/daily_prices.json"
```

## 画面での確認（Streamlit）

1. ダッシュボードの **「最新データを読み込み」** でクラウドJSONを取込
2. 全エリアの値下げ一覧と、物件ごとの過去価格を確認（文字検索・1000万円/徒歩/面積の絞り込み、昇順降順）。更新のたびに「今日の読み取り」が出ます
3. X投稿下書きで投稿文をコピー

## クラウド自動更新

### GitHub Actions

- `Daily SUUMO Price Scrape`: 毎日 **06:30 JST 目安**にスクレイピング（遅延は許容）
- `Deploy GitHub Pages`: 公開サイトを更新
- 監視は23区+26市で最大49エリア。`max_pages` は区と同じ50。ジョブ制限は180分です

成果物:

- `data/published/daily_prices.json`（最新）
- `data/published/daily_prices_YYYY-MM-DD.json`（日付別。過去分は削除せず蓄積）
- `data/published/price_history.json`（件数・平均の軽量サマリ。画面では使わない）
- `data/published/daily_insight.json` / `daily_insight.md`（その日の値下げの読み取り）
- `site/index.html`（Pages用・Actionsで生成。先頭に同じ読み取りを掲載）

### ローカル手動

```bash
python scripts/register_wards.py --max-pages 50
python scripts/run_daily.py
python scripts/bootstrap_previous_day.py --export
python scripts/build_site.py
python scripts/sync_from_remote.py
```

`register_wards.py` は東京23区と市部26市を名前で冪等登録します（再実行で重複しません）。市部の URL だけ試す場合は、Streamlit の監視設定から対象市を選んで「今すぐ取得（ローカル）」を実行します。

## 同一物件の扱い

仲介違いで同一物件が複数出る場合は、名称・住所・間取り・面積で同一判定し、**最安値の1件だけ**を保存します。

## テスト

```bash
pytest
```
