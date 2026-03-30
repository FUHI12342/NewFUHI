# SNS自動投稿機能 実装プラン v2

**更新日:** 2026-03-28
**リサーチ結果反映:** X API v2 Free tier制約、GBP API不安定性、トークン管理、レート制限

## Context

店舗オーナーがTimebaibaiで作成したシフト・スタッフ情報をX (Twitter) に自動投稿し集客と業務効率化を実現。
サロンボード等の競合にはSNS自動投稿機能が無く、**Timebaibaiの差別化ポイント**となる。

## Scope決定（リサーチに基づく）

| 項目 | v1プラン | v2プラン | 理由 |
|------|---------|---------|------|
| X API | 含む | **含む** | OAuth経由の自動投稿は規約上OK |
| GBP API | 含む | **除外** | レガシーAPI、403報告多数、後継無し |
| REST API | Phase 4 | **後回し** | Django Adminで代替可能 |
| レート制限 | 月間のみ | **日次+月間** | 17件/日がアプリ全体で共有（致命的制約） |
| トークンリフレッシュ | 記載なし | **排他制御追加** | ワンタイムrefresh_token→レースコンディション対策必須 |

## X API Free tier 制約まとめ

```
X API v2 FREE TIER CONSTRAINTS
═══════════════════════════════════════
POST /2/tweets:
  Per-App:  17 requests / 24 hours     ← 全ユーザー共有！
  Monthly:  500 posts / month           ← enrollment day基準
  Read:     100 requests / month        ← ほぼ使えない

Token lifecycle:
  Access token:   2時間 (7200秒)
  Refresh token:  6ヶ月 (ワンタイム使用)

重要:
  - 失敗リクエスト(429/503/timeout)もカウント消費
  - 月間リセットはenrollment day (カレンダー月ではない)
  - Pay-per-use: ~$0.01/投稿 (代替オプション)
═══════════════════════════════════════
```

---

## Phase 1: モデル + サービス層

### 1.1 新規モデル
**新規ファイル:** `booking/models/social_posting.py` (~120行)

```python
# SocialAccount — 店舗ごとのX OAuth認証情報
class SocialAccount(models.Model):
    PLATFORM_CHOICES = [('x', 'X (Twitter)')]

    store           = ForeignKey(Store)
    platform        = CharField(choices=PLATFORM_CHOICES, default='x')
    account_name    = CharField(max_length=100)           # @username
    access_token    = EncryptedCharField(max_length=500)  # 既存fields.py再利用
    refresh_token   = EncryptedCharField(max_length=500)
    token_expires_at = DateTimeField(null=True)
    is_active       = BooleanField(default=True)
    created_at      = DateTimeField(auto_now_add=True)
    updated_at      = DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('store', 'platform')


# PostTemplate — トリガー種別ごとのテンプレート
class PostTemplate(models.Model):
    TRIGGER_CHOICES = [
        ('shift_publish', 'シフト公開時'),
        ('daily_staff', '本日のスタッフ'),
        ('weekly_schedule', '週間スケジュール'),
        ('manual', '手動投稿'),
    ]

    store           = ForeignKey(Store)
    platform        = CharField(choices=PLATFORM_CHOICES, default='x')
    trigger_type    = CharField(choices=TRIGGER_CHOICES)
    body_template   = TextField()  # {store_name}, {date}, {staff_list} 等
    is_active       = BooleanField(default=True)

    class Meta:
        unique_together = ('store', 'platform', 'trigger_type')


# PostHistory — 不変監査ログ
class PostHistory(models.Model):
    STATUS_CHOICES = [
        ('pending', '投稿待ち'),
        ('posted', '投稿済み'),
        ('failed', '失敗'),
        ('skipped', 'スキップ（制限超過等）'),
    ]

    store            = ForeignKey(Store)
    platform         = CharField(max_length=10)
    trigger_type     = CharField(max_length=20)
    content          = TextField()
    status           = CharField(choices=STATUS_CHOICES, default='pending')
    external_post_id = CharField(max_length=100, blank=True)  # 冪等性チェック用
    error_message    = TextField(blank=True)
    retry_count      = IntegerField(default=0)
    created_at       = DateTimeField(auto_now_add=True)
    posted_at        = DateTimeField(null=True)
```

**変更ファイル:** `booking/models/__init__.py` (+5行)

```python
# Social posting
from .social_posting import (  # noqa: F401
    SocialAccount,
    PostTemplate,
    PostHistory,
)
```

### 1.2 コンテンツ生成サービス
**新規ファイル:** `booking/services/post_generator.py` (~150行)

```
CONTENT GENERATION FLOW
═══════════════════════════════════════
  trigger_type + store + context
        │
        ▼
  PostTemplate.objects.get(store, trigger_type)
        │
        ▼
  render_template(body_template, context)
        │  変数展開: {store_name}, {date}, {staff_list}, etc.
        ▼
  validate_tweet_length(content)
        │  twitter-text-parser で weighted length チェック
        │  日本語=重み2 → 実質140文字
        ▼
  truncate_if_needed(content, max_weighted=280)
        │
        ▼
  return content (str)
═══════════════════════════════════════
```

関数:
- `build_shift_publish_content(store, period, template)` — シフト公開時
- `build_daily_staff_content(store, target_date, template)` — 本日のスタッフ
- `build_weekly_schedule_content(store, week_start, template)` — 週間スケジュール
- `render_template(body_template, context)` — 安全な変数展開
- `validate_tweet_length(content) -> (bool, int)` — twitter-text-parser使用

テンプレート変数: `{store_name}`, `{date}`, `{staff_list}`, `{business_hours}`, `{month}`

### 1.3 X API 投稿サービス
**新規ファイル:** `booking/services/x_posting_service.py` (~180行)

```
X API POST FLOW (with rate limit + token refresh)
═══════════════════════════════════════════════════
  post_tweet(social_account, content)
        │
        ├─ 1. check token expiry (5min buffer)
        │     └─ expired? → refresh_x_token(account)
        │                    └─ Redis lock で排他制御
        │
        ├─ 2. POST https://api.x.com/2/tweets
        │     Headers: Authorization: Bearer {access_token}
        │     Body: {"text": content}
        │
        ├─ 3. Parse response
        │     ├─ 201: success → return external_post_id
        │     ├─ 429: rate limited → raise RateLimitError(reset_at)
        │     ├─ 401: token expired → refresh + retry once
        │     └─ 5xx: server error → raise RetryableError
        │
        └─ 4. Parse rate limit headers (supplementary, not primary)
              x-rate-limit-remaining, x-rate-limit-reset
═══════════════════════════════════════════════════
```

関数:
- `post_tweet(social_account, content) -> PostResult` — X API v2 投稿
- `refresh_x_token(social_account)` — Redis分散ロック付きリフレッシュ
- `validate_x_credentials(social_account) -> bool` — 接続確認 (`GET /2/users/me`)

**依存:** `requests` (既存), `redis` (既存: CELERY_BROKER_URL)

### 1.4 レート制限サービス
**新規ファイル:** `booking/services/x_rate_limiter.py` (~120行)

```
RATE LIMIT ARCHITECTURE
═══════════════════════════════════════════════════
  Redis Keys:
    x_api:app_posts:{month_key}        ← 月間カウンター (INCR, EXPIRE 35d)
    x_api:store_posts:{id}:{month_key} ← 店舗別カウンター
    x_api:daily_posts                  ← Sorted Set (sliding window 24h)
    x_api:token_refresh:{account_id}   ← 分散ロック (EXPIRE 60s)

  Check flow:
    can_post(store_id)
      ├─ check monthly app limit (< 480, 20件のsafety margin)
      ├─ check monthly store quota (< 50/store default)
      └─ check daily sliding window (< 16, 1件のbuffer)

  Alert levels:
    GREEN:   < 70% used
    YELLOW:  70-90% → medium priority only
    RED:     > 90% → critical only
    BLOCKED: 100% → no posting
═══════════════════════════════════════════════════
```

### 1.5 ディスパッチャーサービス
**新規ファイル:** `booking/services/post_dispatcher.py` (~180行)

パターン参考: `booking/services/shift_notifications.py`

```
DISPATCH FLOW
═══════════════════════════════════════════════════
  dispatch_post(store, trigger_type, context)
        │
        ├─ 1. SocialAccount.objects.get(store, platform='x', is_active=True)
        │     └─ not found? → log + return
        │
        ├─ 2. PostTemplate.objects.get(store, trigger_type, is_active=True)
        │     └─ not found? → log + return
        │
        ├─ 3. build_content(trigger_type, store, context, template)
        │
        ├─ 4. PostHistory.objects.create(status='pending', content=content)
        │
        ├─ 5. can_post(store_id)?
        │     ├─ YES → post_tweet(account, content)
        │     │        └─ success → PostHistory.status='posted'
        │     │        └─ failure → PostHistory.status='failed' + retry logic
        │     └─ NO  → PostHistory.status='skipped' + log reason
        │
        └─ 6. increment counters (app + store + daily)
═══════════════════════════════════════════════════
```

関数:
- `dispatch_shift_publish_post(period)` — シフト公開時
- `dispatch_daily_staff_post(store)` — 毎日定時
- `dispatch_manual_post(store, content)` — 手動投稿
- `retry_failed_post(post_history_id)` — リトライ (最大3回)

---

## Phase 2: OAuth認証 + 管理画面

### 2.1 OAuth フロー
**新規ファイル:** `booking/views_social_oauth.py` (~200行)

**X OAuth 2.0 PKCE (Confidential Client):**

```
OAUTH FLOW
═══════════════════════════════════════════════════
  1. Admin clicks "X連携" button
     GET /admin/social/connect/x/?store_id=N
        │
        ├─ Generate code_verifier + code_challenge (S256)
        ├─ Store state + code_verifier in session
        └─ Redirect → https://x.com/i/oauth2/authorize
              ?response_type=code
              &client_id={X_CLIENT_ID}
              &redirect_uri={X_REDIRECT_URI}
              &scope=tweet.read+tweet.write+users.read+offline.access
              &state={state}
              &code_challenge={code_challenge}
              &code_challenge_method=S256

  2. User authorizes on X
     Callback: GET /admin/social/callback/x/?code=XXX&state=YYY
        │
        ├─ Verify state matches session
        ├─ POST https://api.x.com/2/oauth2/token
        │    (code, code_verifier, client_id, client_secret)
        ├─ GET /2/users/me → get @username
        ├─ Create/update SocialAccount
        │    (access_token, refresh_token, token_expires_at)
        └─ Redirect → Admin with success message
═══════════════════════════════════════════════════
```

Scopes: `tweet.read tweet.write users.read offline.access`

**新規ファイル:** `booking/social_urls.py` (~15行)

### 2.2 Django Admin 登録
**新規ファイル:** `booking/admin/social_posting.py` (~100行)

- `SocialAccountAdmin`: 接続状態表示、有効/無効、「X連携」カスタムリンク
- `PostTemplateAdmin`: テンプレート編集、trigger_type別フィルタ
- `PostHistoryAdmin`: 履歴閲覧(読み取り専用)、「リトライ」アクション

**変更ファイル:**
- `booking/admin/__init__.py` — import追加 (+4行)
- `booking/admin_site.py` — GROUPSに「SNS自動投稿」追加 (+8行)

### 2.3 環境変数
**変更ファイル:** `project/settings.py` (+6行)

```python
# X (Twitter) API
X_CLIENT_ID = os.getenv("X_CLIENT_ID", "")
X_CLIENT_SECRET = os.getenv("X_CLIENT_SECRET", "")
X_REDIRECT_URI = os.getenv("X_REDIRECT_URI", "")
```

### 2.4 依存追加
**変更ファイル:** `requirements.txt` (+1行)

```
twitter-text-parser>=3.0.0,<4.0
```

(`requests`, `cryptography`, `redis` は既存)

---

## Phase 3: Celery タスク + トリガー連携

### 3.1 Celery タスク
**変更ファイル:** `booking/tasks.py` (+70行)

```python
# --- SNS自動投稿タスク ---

@shared_task(
    bind=True,
    max_retries=2,  # 失敗もカウント消費のため少なめ
    autoretry_for=(ConnectionError, Timeout),
    retry_backoff=120,
    retry_backoff_max=900,
    retry_jitter=True,
)
def task_post_to_x(self, store_id, trigger_type, context_json):
    """X API投稿タスク。専用キュー x_api で単一ワーカー実行。"""
    from booking.services.post_dispatcher import dispatch_post
    dispatch_post(store_id, trigger_type, context_json)


@shared_task
def task_post_shift_published(period_id):
    """シフト公開時のSNS投稿をキューイング"""
    from booking.models import ShiftPeriod
    period = ShiftPeriod.objects.select_related('store').get(id=period_id)
    task_post_to_x.apply_async(
        args=[period.store_id, 'shift_publish', {'period_id': period_id}],
        queue='x_api',
    )


@shared_task
def task_post_daily_staff():
    """毎日09:30: 各店舗の本日スタッフを投稿"""
    from booking.models import SocialAccount
    for account in SocialAccount.objects.filter(is_active=True, platform='x'):
        task_post_to_x.apply_async(
            args=[account.store_id, 'daily_staff', {}],
            queue='x_api',
        )


@shared_task
def task_post_weekly_schedule():
    """毎週月曜10:00: 週間スケジュールを投稿"""
    from booking.models import SocialAccount
    for account in SocialAccount.objects.filter(is_active=True, platform='x'):
        task_post_to_x.apply_async(
            args=[account.store_id, 'weekly_schedule', {}],
            queue='x_api',
        )


@shared_task
def task_refresh_social_tokens():
    """毎日03:30: 期限が近いトークンをリフレッシュ"""
    from booking.models import SocialAccount
    from booking.services.x_posting_service import refresh_x_token
    threshold = timezone.now() + timezone.timedelta(hours=6)
    for account in SocialAccount.objects.filter(
        is_active=True, token_expires_at__lte=threshold,
    ):
        try:
            refresh_x_token(account)
        except Exception as e:
            logger.warning("Token refresh failed for store %s: %s", account.store_id, e)
```

### 3.2 Beat スケジュール追加
**変更ファイル:** `celery_config.py` (+15行)

```python
# SNS自動投稿
"post-daily-staff": {
    "task": "booking.tasks.task_post_daily_staff",
    "schedule": crontab(hour=9, minute=30),
},
"post-weekly-schedule": {
    "task": "booking.tasks.task_post_weekly_schedule",
    "schedule": crontab(hour=10, minute=0, day_of_week=1),
},
"refresh-social-tokens": {
    "task": "booking.tasks.task_refresh_social_tokens",
    "schedule": crontab(hour=3, minute=30),
},
```

### 3.3 Celeryワーカー設定
**変更ファイル:** `celery_config.py` (+3行)

```python
app.conf.task_routes = {
    'booking.tasks.task_post_to_x': {'queue': 'x_api'},
}
```

**デプロイ時:** X API専用ワーカーを追加起動
```bash
celery -A project worker -Q x_api --concurrency=1 -n x_api_worker
```

### 3.4 シフト公開トリガー接続
**変更ファイル:** `booking/views_shift_api.py` L566付近 (+5行)

```python
# 既存: notify_shift_approved(period) の直後に追加
try:
    from booking.tasks import task_post_shift_published
    transaction.on_commit(lambda: task_post_shift_published.delay(period.id))
except Exception as e:
    logger.warning("Failed to queue social posting task: %s", e)
```

**変更ファイル:** `booking/admin/shifts.py` approve_and_sync (+5行)

```python
# notify_shift_approved(period) の直後に追加
try:
    from booking.tasks import task_post_shift_published
    task_post_shift_published.delay(period.id)
except Exception as e:
    logger.warning("Failed to queue social posting: %s", e)
```

---

## ファイルサマリー (v2)

| 種別 | ファイル | 推定行数 |
|------|---------|---------|
| **新規** | `booking/models/social_posting.py` | ~120 |
| **新規** | `booking/services/post_generator.py` | ~150 |
| **新規** | `booking/services/x_posting_service.py` | ~180 |
| **新規** | `booking/services/x_rate_limiter.py` | ~120 |
| **新規** | `booking/services/post_dispatcher.py` | ~180 |
| **新規** | `booking/views_social_oauth.py` | ~200 |
| **新規** | `booking/social_urls.py` | ~15 |
| **新規** | `booking/admin/social_posting.py` | ~100 |
| 新規小計 | 8ファイル | ~1,065行 |
| **変更** | `booking/models/__init__.py` | +5 |
| **変更** | `booking/admin/__init__.py` | +4 |
| **変更** | `booking/admin_site.py` | +8 |
| **変更** | `project/settings.py` | +6 |
| **変更** | `booking/tasks.py` | +70 |
| **変更** | `celery_config.py` | +18 |
| **変更** | `booking/views_shift_api.py` | +5 |
| **変更** | `booking/admin/shifts.py` | +5 |
| **変更** | `requirements.txt` | +1 |
| 変更小計 | 9ファイル | ~122行 |

**v1→v2 削減:**
- ファイル数: 24 → 17 (-7)
- 新規行数: ~2,200 → ~1,065 (-52%)
- 削除: gbp_posting_service.py, test_service_gbp_posting.py, views_social_api.py, social_api_urls.py, api_urls.py変更

---

## テスト

**新規テストファイル (5ファイル, 計~550行):**

| ファイル | テスト対象 | 主要テスト |
|---------|-----------|-----------|
| `tests/test_models_social_posting.py` | モデル制約 | unique_together, EncryptedCharField暗号化/復号 |
| `tests/test_service_post_generator.py` | コンテンツ生成 | テンプレート展開, twitter-text-parser文字数検証, 日本語truncate |
| `tests/test_service_x_posting.py` | X API (mock) | 投稿成功/429/401/5xx, トークンリフレッシュ, 分散ロック |
| `tests/test_service_post_dispatcher.py` | ディスパッチ | PostHistory記録, レート制限スキップ, 冪等性 |
| `tests/test_tasks_social_posting.py` | Celery タスク | タスクルーティング, on_commit, リトライ |

---

## 検証手順

1. `python manage.py makemigrations booking && python manage.py migrate`
2. `pytest tests/test_models_social_posting.py tests/test_service_post_generator.py -v`
3. Django admin で SocialAccount/PostTemplate を手動作成
4. X Developer Portal でテスト用アプリ作成 → OAuth接続テスト
5. 手動投稿でツイートが投稿されることを確認
6. シフト公開操作 → 自動投稿をPostHistoryで確認
7. 17件/日制限テスト: Redis INCR を手動で16に設定 → 制限発動を確認

---

## NOT in scope (明示的に除外)

| 項目 | 理由 |
|------|------|
| GBP API連携 | レガシーAPI、403報告多数、後継無し。将来はサードパーティ(Ayrshare等)経由を検討 |
| REST APIエンドポイント | Django Adminで十分。フロント連携が必要になってから追加 |
| 画像投稿 | X v1.1 media upload (OAuth 1.0a必要) のため後回し |
| Instagram連携 | 別途API調査が必要 |
| Pay-per-use tier | Free tierで検証後に移行判断 |
| social-auth-app-django活用 | 既存はLINE OAuth用。X用に拡張するより独自実装の方がシンプル |

## What already exists (再利用する既存コード)

| 既存コード | 再利用方法 |
|-----------|-----------|
| `booking/fields.py` EncryptedCharField | SocialAccountのtoken暗号化にそのまま使用 |
| `booking/services/shift_notifications.py` | ディスパッチャーのパターン参考 |
| `booking/tasks.py` @shared_task | 既存パターンに追加 |
| `celery_config.py` beat_schedule | 既存辞書に追加 |
| `booking/admin_site.py` GROUPS | 既存パターンでグループ追加 |
| `redis` (CELERY_BROKER_URL) | レート制限カウンター + 分散ロックに流用 |
| `requests` (requirements.txt) | X API HTTPクライアント |
| `cryptography` (requirements.txt) | EncryptedCharField依存 |
