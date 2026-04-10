# アーキテクチャ概要 (Architecture Overview)

最終更新: 2026-04-09

---

## システム構成図

```
                        ┌─────────────────┐
                        │   LINE Platform  │
                        │  (Messaging API) │
                        └────────┬────────┘
                                 │ Webhook / Push
                                 ▼
┌──────────┐  HTTPS   ┌─────────────────────┐     ┌──────────────┐
│ ブラウザ  │────────▶│      Nginx          │     │ Raspberry Pi │
│ (顧客/   │◀────────│  (Reverse Proxy)    │     │  Pico W      │
│  管理者)  │         │  + SSL termination  │     │ (IoTセンサー) │
└──────────┘         └─────────┬───────────┘     └──────┬───────┘
                                │                         │ HTTP POST
                                ▼                         │
                       ┌─────────────────────┐           │
                       │   Gunicorn (WSGI)   │◀──────────┘
                       │   Django 4.2 LTS    │
                       │   booking app       │
                       └──┬──────────┬───────┘
                          │          │
               ┌──────────┘          └──────────┐
               ▼                                 ▼
      ┌────────────────┐              ┌──────────────────┐
      │   SQLite3      │              │   Redis          │
      │  (Primary DB)  │              │  (Celery Broker) │
      └────────────────┘              └────────┬─────────┘
                                               │
                                      ┌────────▼─────────┐
                                      │   Celery Worker   │
                                      │   + Beat          │
                                      │   (15タスク)       │
                                      └──┬────────┬───────┘
                                         │        │
                          ┌──────────────┘        └──────────────┐
                          ▼                                       ▼
                 ┌─────────────────┐                    ┌────────────────┐
                 │   AWS S3        │                    │ SwitchBot API  │
                 │  (Backups)      │                    │ (換気扇制御)    │
                 └─────────────────┘                    └────────────────┘

                 ┌─────────────────┐                    ┌────────────────┐
                 │   X (Twitter)   │                    │ Coiney         │
                 │   API           │                    │ (決済)          │
                 └─────────────────┘                    └────────────────┘

                 ┌─────────────────┐                    ┌────────────────┐
                 │   Sentry        │                    │ LINE Notify    │
                 │  (Error Monitor)│                    │ (通知)          │
                 └─────────────────┘                    └────────────────┘
```

---

## 技術スタック

### バックエンド

| 技術 | バージョン | 用途 |
|------|-----------|------|
| Python | 3.9+ | ランタイム |
| Django | 4.2 LTS | Webフレームワーク |
| Django REST Framework | 3.14+ | REST API |
| Celery | 5.3+ | 非同期タスク・定期実行 |
| Redis | 5.0+ | Celery メッセージブローカー |
| Gunicorn | 21.2+ | WSGIサーバー |
| SQLite3 | - | プライマリデータベース |

### セキュリティ

| 技術 | 用途 |
|------|------|
| cryptography (Fernet) | 機密フィールド暗号化（LINE ID, IoTパスワード, 決済APIキー, SwitchBotトークン） |
| argon2-cffi | パスワードハッシュ |
| PyJWT | JWT トークン処理 |
| pyotp | TOTP認証（勤怠QR） |
| bleach | HTMLサニタイズ |
| Sentry SDK | エラーモニタリング |

### フロントエンド

| 技術 | 用途 |
|------|------|
| Django Templates | サーバーサイドレンダリング |
| HTMX | 部分更新・インタラクション |
| Chart.js | グラフ描画（ダッシュボード・センサー） |
| GrapesJS | ビジュアルページビルダー |
| Tailwind CSS | ユーティリティCSS（管理画面カスタム） |
| django-jazzmin | 管理画面テーマ |

### 外部連携

| サービス | 用途 |
|---------|------|
| LINE Messaging API | 予約チャットボット・リマインダー・セグメント配信 |
| LINE OAuth2 | ユーザー認証 |
| Coiney | クレジットカード決済 |
| X (Twitter) API | SNS自動投稿 |
| AWS S3 | バックアップストレージ |
| AWS EC2 | 本番ホスティング |
| SwitchBot API | IoTスマートプラグ制御 |
| Sentry | エラーモニタリング |
| LINE Notify | 管理者通知（在庫アラート等） |

### IoT

| ハードウェア | 用途 |
|-------------|------|
| Raspberry Pi Pico W | マルチセンサーノード |
| MQ-9 | CO/可燃ガスセンサー |
| PIR | 人感センサー（来客計測） |
| BH1750 | 照度センサー |
| Sound sensor | 音量センサー |
| IR LED/Receiver | 赤外線リモコン送受信 |

### ML

| 技術 | 用途 |
|------|------|
| scikit-learn (RandomForest) | スタッフ最適配置推薦 |
| joblib | モデルシリアライズ |

---

## ディレクトリ構造

```
NewFUHI/
├── project/                      # Django project settings
│   ├── settings/
│   │   ├── base.py               # 共通設定
│   │   ├── local.py              # ローカル開発用
│   │   ├── staging.py            # ステージング用
│   │   └── production.py         # 本番用
│   ├── urls.py                   # ルートURLconf
│   └── __init__.py
│
├── booking/                      # メインアプリケーション（全ビジネスロジック）
│   ├── models/                   # データモデル（14ファイル）
│   │   ├── core.py               # Store, Staff, Product, Category, etc.
│   │   ├── schedule.py           # Schedule (予約)
│   │   ├── orders.py             # Order, OrderItem, StockMovement, POSTransaction
│   │   ├── shifts.py             # ShiftPeriod, ShiftAssignment, etc. (12モデル)
│   │   ├── iot.py                # IoTDevice, IoTEvent, VentilationAutoControl, etc.
│   │   ├── hr.py                 # EmploymentContract, PayrollEntry, Attendance, etc.
│   │   ├── cms.py                # SiteSettings, Notice, HeroBanner, etc.
│   │   ├── theme.py              # StoreTheme
│   │   ├── page_layout.py        # PageLayout, SectionSchema
│   │   ├── custom_page.py        # CustomPage, PageTemplate, SavedBlock
│   │   ├── social_posting.py     # SocialAccount, DraftPost, PostHistory, etc.
│   │   ├── line_customer.py      # LineCustomer, LineMessageLog
│   │   ├── backup.py             # BackupConfig, BackupHistory
│   │   └── __init__.py           # 全モデル再エクスポート
│   │
│   ├── services/                 # ビジネスロジックサービス層（44ファイル）
│   │   ├── ai_staff_recommend.py # ML推薦
│   │   ├── backup_service.py     # バックアップ実行
│   │   ├── line_bot_service.py   # LINE Messaging API
│   │   ├── line_chatbot.py       # 会話エンジン
│   │   ├── line_reminder.py      # リマインダー送信
│   │   ├── line_segment.py       # セグメント計算・配信
│   │   ├── payroll_calculator.py # 給与計算
│   │   ├── post_dispatcher.py    # SNS投稿ディスパッチ
│   │   ├── shift_scheduler.py    # 自動シフト配置
│   │   ├── visitor_analytics.py  # 来客分析
│   │   ├── zengin_export.py      # 全銀フォーマット出力
│   │   └── ...
│   │
│   ├── views*.py                 # ビューファイル（35ファイル）
│   │   ├── views.py              # メインビュー
│   │   ├── views_pos.py          # POS
│   │   ├── views_shift_api.py    # シフトAPI
│   │   ├── views_attendance.py   # 勤怠
│   │   ├── views_restaurant_dashboard.py  # ダッシュボード
│   │   └── ...
│   │
│   ├── admin/                    # 管理画面カスタマイズ
│   ├── management/commands/      # 管理コマンド（18個）
│   ├── migrations/               # DBマイグレーション（126+）
│   ├── middleware.py              # Maintenance, ForceLanguage, SecurityAudit
│   ├── tasks.py                  # Celeryタスク（22タスク）
│   ├── api_urls.py               # API URLconf
│   ├── shift_api_urls.py         # シフトAPI URLconf
│   ├── table_urls.py             # テーブル注文URLconf
│   ├── embed_urls.py             # 埋め込みURLconf
│   ├── social_urls.py            # SNS OAuth URLconf
│   └── urls.py                   # メインURLconf
│
├── templates/                    # テンプレート
│   ├── admin/booking/            # 管理画面テンプレート
│   ├── booking/                  # ユーザー向けテンプレート
│   └── embed/                    # 埋め込みテンプレート
│
├── static/                       # 静的ファイル
│   ├── css/                      # Tailwind CSS, カスタムCSS
│   ├── js/                       # Chart.js, HTMX, カスタムJS
│   └── images/
│
├── locale/                       # 多言語翻訳ファイル
│   ├── ja/, en/, zh_Hant/, zh_Hans/, ko/, es/, pt/
│   └── (各7言語 x 1,366文字列)
│
├── MB_IoT_device_main/           # IoTデバイスファームウェア (MicroPython)
│   ├── code.py                   # Pico Wメインループ
│   └── pico_device/              # デバイス設定管理
│
├── social_browser/               # SNSブラウザ投稿アプリ (Playwright)
│
├── scripts/                      # デプロイ・運用スクリプト
│   └── deploy_to_ec2.sh          # EC2デプロイスクリプト
│
├── tests/                        # プロジェクトレベルテスト
├── celery_config.py              # Celery設定 + Beat スケジュール
├── conftest.py                   # pytest共通フィクスチャ
├── requirements.txt              # Python依存パッケージ
├── manage.py                     # Django管理コマンド
└── db.sqlite3                    # SQLiteデータベース
```

---

## 主要設計パターン

### 1. シングルトンモデル

`SiteSettings` と `BackupConfig` は pk=1 のシングルトンパターン。
`load()` クラスメソッドで `get_or_create(pk=1)` を実行。

```python
class SiteSettings(models.Model):
    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
```

### 2. フィーチャーフラグ

`SiteSettings` の Boolean フィールドで機能の有効/無効を制御。

| フラグ | 機能 |
|--------|------|
| `line_chatbot_enabled` | LINEチャットボット |
| `line_reminder_enabled` | LINEリマインダー |
| `line_segment_enabled` | LINEセグメント配信 |
| `demo_mode_enabled` | デモモード |
| `maintenance_mode` | メンテナンスモード |
| `free_booking_mode` | 無料予約モード |
| `show_shift`, `show_pos`, `show_ec`, ... | 管理サイドバー表示制御（20項目） |

### 3. 暗号化フィールド

機密データは `EncryptedCharField` (Fernet対称暗号) で保存。

```python
class IoTDevice(models.Model):
    wifi_password = EncryptedCharField(max_length=500, ...)
```

対象フィールド:
- Schedule.line_user_id_encrypted
- IoTDevice.wifi_password
- VentilationAutoControl.switchbot_token / switchbot_secret
- PaymentMethod.coiney_api_key
- SocialAccount.access_token / refresh_token

### 4. デモモード分離

8モデルに `is_demo` フィールドを追加。ダッシュボードビューで自動フィルタ適用。

```python
class DashboardAuthMixin:
    def build_demo_filter(self, prefix=''):
        if is_demo_mode_active():
            return {}  # デモデータも表示
        return {f'{prefix}is_demo': False}  # 実データのみ
```

### 5. ミドルウェアチェーン

```
Request → SecurityMiddleware
        → SessionMiddleware
        → LocaleMiddleware          # 言語検出
        → ForceLanguageMiddleware    # サイト言語固定
        → CommonMiddleware
        → CsrfViewMiddleware
        → AuthenticationMiddleware
        → MaintenanceMiddleware      # メンテナンスモード
        → MessageMiddleware
        → XFrameOptionsMiddleware
        → SecurityAuditMiddleware    # セキュリティ監視 + レートリミット
```

### 6. Celery タスクルーティング

```python
task_routes = {
    'booking.tasks.task_post_to_x': {'queue': 'x_api'},         # X API専用キュー
    'social_browser.tasks.task_browser_post': {'queue': 'browser_posting'},  # ブラウザ投稿専用
}
```

### 7. URL構造（i18n分離）

```python
# i18nプレフィックスなし（API、Webhook、埋め込み）
urlpatterns = [
    path("embed/", include("booking.embed_urls")),
    path("api/", include("booking.api_urls")),
    path("line/webhook/", ...),
    path("t/", include("booking.table_urls")),
    path("healthz", healthz),
]

# i18nプレフィックスあり（ユーザー向けページ）
urlpatterns += i18n_patterns(
    path("admin/...", ...),
    path("", include("booking.urls")),
    prefix_default_language=False,  # デフォルト言語はプレフィックスなし
)
```

---

## データフロー

### 予約フロー

```
顧客 → トップページ → スタッフ選択 → カレンダー → 仮予約作成
                                                    ↓
                                           ┌─ LINE予約 (OAuth2)
                                           └─ メール予約 (OTP認証)
                                                    ↓
                                           Schedule レコード作成
                                                    ↓
                                      ┌─ QRコード発行 (qrcode lib)
                                      ├─ LINE通知送信
                                      └─ メール送信
                                                    ↓
                                           当日チェックイン (QR/口頭コード)
```

### IoTセンサーフロー

```
Pico W → HTTP POST /api/iot/events/ (APIキー認証)
                    ↓
           IoTEvent レコード作成
                    ↓
         ┌─ MQ-9閾値超過?
         │   ├─ trigger_gas_alert タスク (メール + LINE)
         │   └─ VentilationAutoControl (SwitchBot ON)
         │
         ├─ PIRイベント?
         │   └─ aggregate_visitor_data タスク → VisitorCount
         │
         └─ pending_ir_commands?
             └─ /api/iot/config/ で次回ポーリング時に返却
```

### シフト管理フロー

```
マネージャー → ShiftPeriod 作成 (募集期間)
                    ↓
スタッフ → ShiftRequest 提出 (available/preferred/unavailable)
                    ↓
マネージャー → 自動配置 (shift_scheduler.py)
             or 手動割当 (ShiftAssignment)
                    ↓
           シフト公開 (ShiftPublishHistory)
                    ↓
           LINE/メール通知 → スタッフ確認
                    ↓
           ┌─ ShiftSwapRequest (交代・欠勤申請)
           └─ ShiftVacancy (不足枠応募)
```

---

## 外部連携詳細

### LINE Messaging API

| 機能 | 実装ファイル | 説明 |
|------|-------------|------|
| Webhook受信 | `views_line_webhook.py` | Follow/Unfollow/Message/Postback |
| メッセージ送信 | `services/line_bot_service.py` | push_text, reply_text, push_flex |
| チャットボット | `services/line_chatbot.py` | 状態機械ベースの会話型予約 |
| リマインダー | `services/line_reminder.py` | 前日/当日自動リマインダー |
| セグメント配信 | `services/line_segment.py` | new/regular/vip/dormant 分類 |

### Coiney 決済

- EC注文: `views_ec_payment.py` → Coiney API → Webhook確認
- POS注文: `views_pos.py` → POSCheckoutAPIView

### X (Twitter) API

- OAuth2認証: `views_social_oauth.py`
- API投稿: `services/x_posting_service.py`
- ブラウザ投稿: `social_browser/` (Playwright)
- AI下書き: `services/sns_draft_service.py` + LLM Judge評価
- レートリミット: `services/x_rate_limiter.py`

### AWS

- S3バックアップ: `services/backup_service.py` (boto3)
- コスト監視: `management/commands/check_aws_costs.py` (EC2/S3/EBS/EIP)

---

## デプロイメント

### 本番環境

| 項目 | 値 |
|------|-----|
| ホスト | AWS EC2 (57.181.0.55) |
| OS | Ubuntu |
| Webサーバー | Nginx + Gunicorn |
| ドメイン | https://timebaibai.com |
| SSL | Let's Encrypt (auto-renew) |
| プロセス管理 | systemd (newfuhi, newfuhi-celery, newfuhi-celerybeat) |
| Python | .venv (仮想環境) |
| デプロイ | `scripts/deploy_to_ec2.sh` (git pull + migrate + collectstatic + restart) |

### デプロイフロー

```
ローカル → git push → SSH → EC2
                              ↓
                    メンテナンスモード ON
                              ↓
                    git pull origin main
                              ↓
                    pip install -r requirements.txt
                              ↓
                    python manage.py migrate
                              ↓
                    python manage.py collectstatic --noinput
                              ↓
                    python manage.py compilemessages
                              ↓
                    systemctl restart newfuhi newfuhi-celery newfuhi-celerybeat
                              ↓
                    メンテナンスモード OFF
                              ↓
                    スモークテスト自動実行
```

---

## セキュリティアーキテクチャ

### 多層防御

1. **ネットワーク層**: Nginx SSL termination, X-Forwarded-For 制御
2. **アプリケーション層**: SecurityAuditMiddleware (レートリミット 100req/60s)
3. **認証層**: Django session + LINE OAuth2 + IoT API key + TOTP
4. **データ層**: Fernet暗号化, Argon2パスワードハッシュ
5. **監視層**: SecurityLog, Sentry, LINE Notify アラート

### 定期セキュリティタスク

| タスク | スケジュール |
|--------|-------------|
| セキュリティ監査 | 毎日 03:00 |
| セキュリティログクリーンアップ | 毎週日曜 04:00 |
| AWSコスト監視 | 毎日 06:00 |
| OAuthトークンリフレッシュ | 毎日 03:30 |
