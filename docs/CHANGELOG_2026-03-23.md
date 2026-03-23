# 作業記録 — 2026-03-23

対象: https://timebaibai.com (NewFUHI Django Booking Platform)

---

## 1. E2Eテスト実施・バグ修正

### 1.1 メインE2Eテスト (25テスト)
4ロール(Cast/Staff/Manager/Owner)のログイン、ワークフロー、ロール間連動、権限境界、公開ページをテスト。

**発見・修正したバグ:**

| # | 内容 | コミット |
|---|---|---|
| 1 | EC注文管理500エラー: `{% load static %}` 漏れ | `f1a2278` |
| 2 | i18n言語維持: ダッシュボードリンクがzh-hantプレフィックスを失う (20箇所) | `f1a2278` |
| 3 | ForceLanguageMiddleware がMIDDLEWAREに未登録 | `f1a2278` |
| 4 | 言語切替時のリダイレクト先が常にトップに戻る | `f1a2278` |
| 5 | 旧URL (`/staff/*/prebooking/*`) が404 | `0bafe08` |

結果: **25/25 PASS**

### 1.2 i18nナビゲーションテスト (21テスト)
公開ページzh-hant、言語切替ページ維持、Admin zh-hantナビ、旧URLリダイレクト、ページ間遷移をテスト。

結果: **21/21 PASS**

### 1.3 包括テスト (131テスト)
全公開ページ(11)、全管理ページ(30)、ユーザーページ(6)、ECフロー(3)、モバイルレスポンシブ(12)、CSRF検証(5)、APIスモーク(37)、QRオーダー(3)、i18n全ページ(15)、ネットワークエラー(5)、エッジケース(4)。

**発見・修正したバグ:**

| # | 内容 | コミット |
|---|---|---|
| 6 | KPIスコアカード500エラー: `Store.objects.filter(**scope)` — Storeモデルにstoreフィールドなし | `7309cb0` |
| 7 | ハードコードURL: `inventory_dashboard.html` フォームaction | `66bd59b` |
| 8 | ハードコードURL: `pos.html` JS内レシートURL | `66bd59b` |

結果: **131/131 PASS**

### テスト総合計: 177/177 PASS

テストスクリプト:
- `/tmp/e2e/run_e2e.py` — メイン25テスト
- `/tmp/e2e/test_i18n_nav.py` — i18n 21テスト
- `/tmp/e2e/test_comprehensive.py` — 包括131テスト

レポート: `docs/E2E_TEST_REPORT.md`

---

## 2. セキュリティレビュー・全19件対応

### CRITICAL (3件)

| # | 内容 | 対応 |
|---|---|---|
| CRIT-1 | EC2秘密鍵 `newfuhi-key.pem` がプロジェクトルートに存在 | `~/.ssh/` に移動、デプロイスクリプト更新 |
| CRIT-2 | `|safe` でHTMLを無サニタイズ出力 (Notice, SiteSettings, Store, HomepageCustomBlock) | bleachライブラリでsave()時にサニタイズ |
| CRIT-3 | `CHECKIN_QR_SECRET` 未設定でDjango SECRET_KEY にフォールバック | 本番.envに専用シークレット追加、フォールバック廃止 |

### HIGH (4件)

| # | 内容 | 対応 |
|---|---|---|
| HIGH-1 | CSPに `unsafe-eval` — XSS防御弱体化 | Alpine.js 3が必要なため残し、CSP設定を2ファイル間で統一、理由をコメント明記 |
| HIGH-2 | `X-Forwarded-For` IPスプーフィング | _get_client_ipにIP形式バリデーション追加 |
| HIGH-3 | 公開フィードバックAPIにレート制限なし | AnonRateThrottle(10/hour)追加 |
| HIGH-4 | SESSION_COOKIE_HTTPONLY未設定 | settings.pyに SESSION_COOKIE_HTTPONLY=True, CSRF_COOKIE_HTTPONLY=True 追加 |

### MEDIUM (5件)

| # | 内容 | 対応 |
|---|---|---|
| MED-1 | CSRF免除エンドポイントにContent-Typeチェックなし | attendance PIN/QR、chatにapplication/jsonチェック追加 |
| MED-2 | seed_mock_dataが本番で実行可能 | DEBUG=Trueガード追加 |
| MED-3 | IoT APIキーがHTTPS非強制 | Nginx強制で対応済み確認 |
| MED-4 | place_idパラメータに入力バリデーションなし | 正規表現バリデーション追加 |
| MED-5 | HSTS設定がNginxとDjango両方で重複 | Django側を削除しNginx一元管理 |

### LOW (3件)

| # | 内容 | 対応 |
|---|---|---|
| LOW-1 | CSP設定が2ファイルで異なる | production.confとsecurity-headers.confを統一 |
| LOW-2 | twitter_urlにjavascript:スキーム許可の可能性 | sanitize_url()でhttp/httpsのみ許可 |
| LOW-3 | debug.logがWebアクセス可能 | Nginxで .log/.pem/.env/.sqlite3/.pyc をブロック |

### INFO (4件 — 問題なし)

- SQLインジェクション: ORM使用のみ、問題なし
- シークレット管理: env_required()で適切に管理
- 認証・認可: DashboardAuthMixin/LoginRequiredMixin 一貫使用
- json.dumps|safe: 内部データのみ、問題なし

コミット: `cf4a452`

---

## 3. 修正ファイル一覧

| ファイル | 修正内容 |
|---|---|
| `booking/services/html_sanitizer.py` | **新規** bleachサニタイズヘルパー |
| `booking/services/checkin_token.py` | SECRET_KEYフォールバック廃止 |
| `booking/models/cms.py` | Notice, SiteSettings, HomepageCustomBlockにsave()サニタイズ追加 |
| `booking/models/core.py` | Storeにgoogle_maps_embedサニタイズ追加 |
| `booking/middleware.py` | _get_client_ip IPバリデーション追加 |
| `booking/views_dashboard_operations.py` | KPIスコアカード修正、フィードバックレート制限、place_idバリデーション |
| `booking/views_attendance.py` | Content-Typeチェック追加 (PIN/QR API) |
| `booking/views_chat.py` | Content-Typeチェック追加 |
| `booking/management/commands/seed_mock_data.py` | DEBUG=Trueガード追加 |
| `project/settings.py` | COOKIE_HTTPONLY追加、HSTS重複解消 |
| `config/nginx/production.conf` | CSP統一、敏感ファイルブロック |
| `config/nginx/snippets/security-headers.conf` | CSP統一、コメント追加 |
| `requirements.txt` | bleach追加 |
| `scripts/deploy_to_ec2.sh` | SSH鍵パス変更 (~/.ssh/) |
| `scripts/deploy_dev.sh` | SSH鍵パス変更 (~/.ssh/) |
| `templates/admin/booking/restaurant_dashboard.html` | 14箇所のURL→{% url %}タグ化 |
| `templates/admin/booking/shift_calendar.html` | 5箇所のURL→{% url %}タグ化 |
| `templates/admin/booking/inventory_dashboard.html` | フォームaction URL→{% url %}タグ化 |
| `templates/admin/booking/pos.html` | JS内レシートURL→{% url %}テンプレートタグ化 |
| `templates/admin/booking/ec_dashboard.html` | {% load static %} 追加 |
| `booking/templates/booking/base.html` | 言語切替のnextフィールド修正 |
| `project/urls.py` | 旧URL 301リダイレクト追加 |
| `docs/E2E_TEST_REPORT.md` | テスト結果レポート |
| `project/holidays.py` | **新規** PUBLIC_HOLIDAYSデータ (settings.pyから外部化) |
| `project/settings.py` | Sentry設定追加、import整理、PUBLIC_HOLIDAYS外部化 |
| `requirements.txt` | 42脆弱性修正 (Django 4.2.29等)、sentry-sdk追加 |
| `booking/views_booking.py` | coiney_webhook Content-Typeチェック追加 |
| `booking/models/cms.py` | 未使用Decimal import削除 |
| `.gitignore` | *.bak, *.orig, #*, アーカイブディレクトリ追加 |

---

## 4. コミット履歴

```
9e385ca refactor: 不要ファイル削除 + Sentry導入 + セキュリティ改修
be53da8 fix: 依存パッケージ42脆弱性修正 + settings.pyリファクタ
c283c05 docs: 作業記録 CHANGELOG_2026-03-23
cf4a452 security: セキュリティレビュー全19件対応
11d4d8d docs: E2Eテストレポート最終版 — 177/177 PASS (3スイート統合)
7309cb0 fix: KPIScoreCardAPIView 500エラー修正 — Storeフィルタ修正
f6381e0 fix: KPIScoreCardAPIView 500エラー修正 — TableSeatインポート追加
66bd59b fix: 最後のハードコードURL2箇所を{% url %}タグに置換
598a6fe docs: E2Eテストレポート最終更新 — 46/46 PASS (メイン25 + i18n 21)
0bafe08 fix: 旧URLリダイレクトをi18n_patterns外に移動 (500→301)
f1a2278 fix: i18n言語維持修正 + 旧URL 404リダイレクト
```

---

## 5. 本番環境の変更

| 項目 | 内容 |
|---|---|
| `.env` に追加 | `CHECKIN_QR_SECRET` (64文字hex) |
| `.env` に追加予定 | `SENTRY_DSN` (Sentryプロジェクト作成後) |
| Nginx設定更新 | CSP統一 + 敏感ファイルブロック |
| 依存パッケージ追加 | `bleach>=6.0.0`, `sentry-sdk[django]>=2.0.0` |
| 依存パッケージ更新 | Django 4.2.29, cryptography 46.0.5, Pillow 12.1.1, PyJWT 2.12.1, lxml-html-clean 0.4.4, Jinja2 3.1.6 |

---

## 6. 追加作業: 本番リスク管理・依存更新・リファクタ

### 6.1 依存パッケージ脆弱性修正 (pip-audit: 42件)

| パッケージ | 旧バージョン | 新バージョン | CVE数 |
|---|---|---|---|
| Django | 4.2.25 | 4.2.29 | 12 |
| cryptography | 43.0.3 | 46.0.5 | 1 |
| Pillow | 10.4.0 | 12.1.1 | 1 |
| PyJWT | 2.10.1 | 2.12.1 | 1 |
| lxml-html-clean | 0.4.3 | 0.4.4 | 2 |
| Jinja2 | (未ピン) | 3.1.6 | 5 |
| filelock | 3.19.1 | 3.25.2 | 2 |
| social-auth-app-django | 5.4.3 | 5.4.3維持 | 1(Django 4.2互換なし) |

### 6.2 settings.py リファクタ

- `import sys` をファイル先頭に移動
- `PUBLIC_HOLIDAYS` を `project/holidays.py` に外部化 (settings.py -40行)
- CHECKIN_QR_SECRET のコメント修正

### 6.3 Sentry エラー監視導入

- `sentry-sdk[django]>=2.0.0` 追加
- settings.py: `SENTRY_DSN` 環境変数で制御 (DEBUG=False時のみ初期化)
- `send_default_pii=False` でPII送信無効化

### 6.4 不要ファイル削除 (17,805行削減)

| 対象 | ファイル数 | 説明 |
|---|---|---|
| pico_backups/ | 22 | IoTデバイス旧バックアップ |
| pico_device__ARCHIVE_*/ | 9 | IoTデバイス旧アーカイブ |
| project/settings/ | 5 | 未使用の分割設定パターン |
| project/#settings.py, *.orig | 2 | 旧設定バックアップ |
| *.bak | 2 | テンプレートバックアップ |
| staticfiles/css/#style.css | 1 | 旧CSSバックアップ |

### 6.5 追加セキュリティ改修

- `coiney_webhook`: Content-Type チェック追加 (全CSRF exemptビュー完了)
- `booking/models/cms.py`: 未使用 `Decimal` import 削除
- `.gitignore`: `*.bak`, `*.orig`, `#*` パターン追加

### 6.6 インフラ確認結果

| 項目 | 状態 | 詳細 |
|---|---|---|
| バックアップ | 正常 | cron 3本 (02:00/03:00/18:00), S3同期含む |
| SSL証明書 | 正常 | certbot.timer 1日2回、残33日 (2026-04-26) |
| Celery | 正常 | newfuhi-celery, newfuhi-celerybeat 共にactive |
| DB | SQLite 34MB | 82テーブル, ~90,000行。現規模では問題なし |

---

## 7. 本番ハードニング (追加作業)

### 7.1 クリティカル修正

| 発見 | 修正内容 |
|---|---|
| **本番DEBUG=True** | `.env` DEBUG=False に修正、systemd に `ENV=production` 追加 |
| **project/settings/ 残存** | サーバーから旧ディレクトリ削除 (Python がパッケージ優先で誤ったsettings読込) |
| **デプロイスクリプト旧参照** | `DJANGO_SETTINGS_MODULE=project.settings.production` → 削除 |

### 7.2 インフラ改善

| 項目 | 修正内容 |
|---|---|
| ログローテーション | `/etc/logrotate.d/newfuhi` 作成 (14日保持、日次圧縮) |
| ディスク空き | 89%→79% (旧バックアップ・journal削除) |
| バックアップ保持 | deploy_to_ec2.sh にpre_deploy直近3件保持ポリシー追加 |
| pip | 25.3→26.0.1 |
| systemd | `ENV=production` 追加、リポジトリ版も更新 |

### 7.3 E2Eテスト移行

`/tmp/e2e/` → `tests/e2e/` (177テスト3ファイル + README)

### 7.4 追加コミット

```
c3ee002 chore: 本番ハードニング + E2Eテストリポジトリ化
```

---

## 8. 残タスク・今後の検討事項

| 項目 | 優先度 | 説明 |
|---|---|---|
| Sentry DSN設定 | 高 | sentry.io でプロジェクト作成→DSN取得→.envに `SENTRY_DSN` 追加 |
| メモリ監視 | 高 | 911MBは限界的。負荷増加時にインスタンス拡張検討 |
| Django 5.x 移行計画 | 中 | Django 4.2 LTS サポートは2026-04終了 |
| social-auth-app-django更新 | 中 | Django 5.x移行時に5.6.0+に更新 |
| E2Eテスト CI/CD化 | 中 | CI/CDパイプラインに組み込み |
| Alpine.js CSPビルド移行 | 低 | `@alpinejs/csp` に移行すれば `unsafe-eval` 削除可能 |
| CSP nonce化 | 低 | `unsafe-inline` を nonce ベースに移行 |
| 大規模ファイルリファクタ | 低 | 12ファイルが800行超 |
| PostgreSQL 移行 | 低 | 同時書き込み負荷増加時に検討 |
