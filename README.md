# NewFUHI — 占いサロン予約・店舗管理プラットフォーム

Django ベースの統合型店舗管理システム。予約管理、シフト管理、ECショップ、POS、IoTセンサー監視、物件管理などを搭載。

## 主な機能

- **予約管理** — LINE / メール / QR コードによる顧客予約
- **シフト管理** — カバレッジベース自動スケジューリング、不足枠再募集、交代・欠勤申請
- **ECショップ** — 商品販売、カート、チェックアウト、発送管理
- **POS / テーブルオーダー** — 店内注文・キッチンディスプレイ
- **勤怠管理** — QR打刻、TOTP認証、勤怠サマリ
- **IoTセンサー監視** — Raspberry Pi Pico W によるガス・温湿度・照度モニタリング
- **物件管理** — WiFi設定、デバイス登録、アラート
- **レストランダッシュボード** — 売上・来客分析、メニューエンジニアリング
- **多言語対応** — 日本語、英語、繁体中文、簡体中文、韓国語、スペイン語、ポルトガル語

## 動作環境

- Python 3.9+
- Django 4.x
- SQLite（開発） / PostgreSQL（本番推奨）
- Celery + Redis（バックグラウンドタスク）

## セットアップ

```bash
git clone <repo-url>
cd NewFUHI
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_mock_data   # テストデータ投入
python manage.py runserver
```

ブラウザで http://127.0.0.1:8000 へアクセス。

## テスト実行

```bash
# 全テスト
.venv/bin/python manage.py test tests booking.tests -v2

# シフト改善テストのみ
.venv/bin/python manage.py test booking.tests.test_shift_coverage -v2

# カバレッジ付き
.venv/bin/python -m coverage run manage.py test booking.tests -v0
.venv/bin/python -m coverage report --include="booking/*"
```

## 本番デプロイ

```bash
# EC2 デプロイ
./scripts/deploy_to_ec2.sh
```

本番URL: https://timebaibai.com

## ドキュメント

- `docs/MANUAL.md` — 取扱説明書
- `docs/test_results.md` — テスト結果・カバレッジレポート
- `docs/DEPLOY_PRODUCTION.md` — 本番デプロイ手順
- `ROADMAP.md` — 開発ロードマップ
- `HANDTEST.md` — 手動テストガイド

## ライセンス

Private
