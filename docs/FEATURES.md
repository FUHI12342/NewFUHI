# 実装済み機能一覧

## デモモード

| 機能 | フラグ | 説明 |
|------|--------|------|
| デモモード切替 | `demo_mode_enabled` | ON: デモ＋実データ表示、OFF: 実データのみ |
| デモデータフィルタ | — | 全ダッシュボードビューで `is_demo` による統一フィルタリング |
| デモデータ自動生成 | `demo_mode_enabled` | 30分毎に当日分のデモ注文・予約・来客数を自動生成 |
| DEMOバナー表示 | `demo_mode_enabled` | ダッシュボード上部にデモモード表示中バナー |

対象モデル: Order, POSTransaction, Schedule, VisitorCount, WorkAttendance, CustomerFeedback, BusinessInsight, StaffRecommendationResult

## 自動バックアップ

| 機能 | 説明 |
|------|------|
| バックアップ設定 | 管理画面からinterval（off/毎分/毎時/毎日）、S3、保持数を設定 |
| 自動バックアップ | Celeryで毎分チェック、設定間隔に基づき `sqlite3.backup()` 実行 |
| S3アップロード | バックアップファイルをS3バケットに自動アップロード（無効化可） |
| ローカル保持ポリシー | 設定数を超えた古いバックアップファイルを自動削除（デフォルト30件） |
| 手動バックアップ | 管理画面アクション or `python manage.py create_backup` |
| バックアップ履歴 | 管理画面で実行履歴・ステータス・ファイルサイズ・エラー確認 |
| LINE通知 | バックアップ完了/失敗時にLINE Notify通知（有効化可） |

## LINE連携機能

| 機能 | フラグ | 説明 |
|------|--------|------|
| LINE Webhook | 常時有効 | 友だち追加/ブロック検知、メッセージ/Postback受信 |
| LINE顧客管理 | 常時有効 | LineCustomer マスタ、送信ログ、Admin管理画面 |
| LINEチャットボット予約 | `line_chatbot_enabled` | LINEトーク内で店舗→スタッフ→日時選択→予約確定 |
| LINEリマインダー | `line_reminder_enabled` | 前日18:00 / 当日2時間前の自動リマインダー |
| LINEセグメント配信 | `line_segment_enabled` | 顧客セグメント別（新規/リピーター/VIP/休眠）一括配信 |
| リッチメニュー | 常時有効 | 予約する/予約確認/お問い合わせのPostback対応 |
| 仮予約確認フロー | 常時有効 | 管理画面から予約の確定/却下 + LINE通知 |

## フィーチャーフラグ

管理画面 → メインサイト設定 → LINE連携 セクションでON/OFF切り替え可能。
デフォルトは全てOFF（安全にデプロイ可能）。

## API エンドポイント

| パス | メソッド | 説明 |
|------|---------|------|
| `/line/webhook/` | POST | LINE Webhook受信 |
| `/api/line/reservations/<id>/confirm/` | POST | 仮予約確定 |
| `/api/line/reservations/<id>/reject/` | POST | 仮予約却下 |

## 管理画面

| パス | 説明 |
|------|------|
| `/admin/line/segment/` | セグメント配信管理 |
| `/admin/line/pending/` | 仮予約確認管理 |
| `/admin/booking/linecustomer/` | LINE顧客一覧 |
| `/admin/booking/linemessagelog/` | LINE送信ログ |

## 管理画面（バックアップ・デモ）

| パス | 説明 |
|------|------|
| メインサイト設定 → デモモード | デモモードON/OFF切替 |
| `/admin/booking/backupconfig/` | バックアップ設定（シングルトン） |
| `/admin/booking/backuphistory/` | バックアップ履歴一覧 |

## Celery タスク

| タスク | スケジュール | 説明 |
|--------|-------------|------|
| `send_day_before_reminders` | 毎日18:00 | 前日リマインダー |
| `send_same_day_reminders` | 30分ごと | 当日リマインダー |
| `recompute_customer_segments` | 毎日04:30 | セグメント日次再計算 |
| `generate_live_demo_data_task` | 30分ごと | デモモード有効時に当日デモデータ生成 |
| `run_scheduled_backup` | 毎分 | バックアップ間隔チェック＋実行 |

## 管理コマンド

| コマンド | 説明 |
|----------|------|
| `generate_live_demo_data` | 当日分デモデータ手動生成 |
| `create_backup` | 手動バックアップ実行 |
| `seed_mock_data` | モックデータ生成（`is_demo=True`でマーク） |
