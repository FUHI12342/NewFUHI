# CHANGELOG

## 2026-04-03: デモモード切替 + 自動バックアップ

### デモモード切替
- 主要8モデルに `is_demo = BooleanField(default=False, db_index=True)` 追加
  - Order, POSTransaction, Schedule, VisitorCount, WorkAttendance, CustomerFeedback, BusinessInsight, StaffRecommendationResult
- SiteSettings に `demo_mode_enabled` フラグ追加（管理画面 → メインサイト設定 → デモモード）
- `demo_data_service.py` — `is_demo_mode_active()`（60秒キャッシュ）, `get_demo_exclusion(prefix)`
- `DashboardAuthMixin.build_demo_filter(prefix)` で全ダッシュボードビューに統一フィルタ適用
- 対象ビュー: views_dashboard_sales, views_dashboard_analytics, views_dashboard_operations, views_analytics
- `seed_mock_data.py` — 全シードデータを `is_demo=True` でマーク
- `generate_live_demo_data` 管理コマンド — 当日分のデモデータ自動生成
- Celeryタスク `generate_live_demo_data_task`（30分毎）
- ダッシュボードに「DEMO MODE」バナー表示（デモモード有効時）
- 管理画面でデモモード変更時にキャッシュ自動無効化

### 自動バックアップ
- BackupConfig シングルトンモデル（interval: off/minute/hourly/daily, S3設定, 保持数, LINE通知）
- BackupHistory モデル（status, trigger, ファイルサイズ, S3アップロード状況, エラーメッセージ）
- `backup_service.py` — Python `sqlite3.backup()` によるアトミックバックアップ
- S3アップロード（boto3, `exclude_demo_data` オプション対応）
- ローカル保持ポリシー（デフォルト30件、古いファイル自動削除）
- `create_backup` 管理コマンド（手動バックアップ）
- Celeryタスク `run_scheduled_backup`（毎分実行、内部で間隔判定）
- 管理画面: BackupConfig設定 + 手動バックアップアクション + BackupHistory一覧（読み取り専用）

### テスト
- `test_demo_data_service.py` — 8テスト（フィルタON/OFF、キャッシュ、プレフィックス、実クエリ）
- `test_backup_service.py` — 7テスト（シングルトン、バックアップ作成、S3無効時、失敗記録、保持ポリシー）
- 全15テスト パス

### マイグレーション
- 0118: is_demo フィールド + demo_mode_enabled + BackupConfig + BackupHistory

## 2026-04-02: LINE機能拡張 6フェーズ実装

### Phase 1: 基盤整備
- LineCustomer / LineMessageLog モデル追加
- SiteSettings に LINE フィーチャーフラグ 3つ追加（line_chatbot_enabled, line_reminder_enabled, line_segment_enabled）
- LINE Messaging API 共通サービス（line_bot_service.py）— push_text, reply_text, push_flex, get_customer_or_create
- LINE Webhook 受信エンドポイント（/line/webhook/）— 署名検証、Follow/Unfollow/Message/Postback対応
- Admin登録（LineCustomerAdmin, LineMessageLogAdmin）
- バックフィル管理コマンド（backfill_line_customers）
- マイグレーション: 0115

### Phase 3: リマインダー通知
- Schedule に reminder_sent_day_before / reminder_sent_same_day フラグ追加
- 前日18:00リマインダー / 当日2時間前リマインダー
- Celery Beat スケジュール追加
- フィーチャーフラグによる制御
- マイグレーション: 0116

### Phase 4: リッチメニュー連携
- Postback ハンドラ（start_booking, check_booking, contact）— Phase 1 で実装済み
- リッチメニュー設定手順書（docs/line_richmenu_setup.md）

### Phase 5: セグメント配信
- セグメント計算サービス（new/regular/vip/dormant）
- 日次セグメント再計算 Celery タスク（毎日04:30）
- セグメント配信管理画面（/admin/line/segment/）
- 配信実行タスク（レート制限付き一括送信）
- Celery Beat スケジュール追加

### Phase 2: LINEチャットボット予約
- 会話エンジン（状態機械: idle → select_store → select_staff → select_date → select_time → confirm）
- 空き枠検索サービス（availability.py）
- 10分タイムアウト自動リセット
- Schedule 作成 + QR生成 + 通知

### Phase 6: 仮予約確認フロー
- Schedule に confirmation_status / confirmed_at / confirmed_by / rejection_reason 追加
- 仮予約確認管理画面（/admin/line/pending/）
- 確定/却下 API（/api/line/reservations/{id}/confirm|reject/）
- delete_temporary_schedules に confirmation_status='none' 条件追加
- LINE通知（確定/却下）
- マイグレーション: 0117

### テスト
- 5テストファイル、31テスト全パス
  - test_line_bot_service.py (7)
  - test_line_reminder.py (6)
  - test_line_webhook.py (3)
  - test_line_chatbot.py (6)
  - test_line_segment.py (9)
