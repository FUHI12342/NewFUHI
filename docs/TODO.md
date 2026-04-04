# TODO

## デモモード
- [ ] デモデータ生成: POSTransaction, WorkAttendance, CustomerFeedback の当日データ生成対応
- [ ] デモモードAPI: REST APIレスポンスにもデモフィルタ適用
- [ ] デモデータ一括削除コマンド（`clear_demo_data`）

## 自動バックアップ
- [ ] S3保持ポリシー実装（`s3_retention_days` に基づく古いS3オブジェクト削除）
- [ ] バックアップ復元コマンド（`restore_backup`）
- [ ] バックアップファイルのダウンロード機能（管理画面から）
- [ ] `exclude_demo_data` オプション実装（デモデータ除外バックアップ）
- [ ] LINE Notify 通知のテスト送信機能

## PDFドキュメント
- [ ] 全機能の使用方法PDFを生成・更新（LINE連携、デモモード、バックアップ含む）

## LINE機能拡張

### 未実装・改善
- [ ] LINE Messaging API v3 への移行（現在v2 line-bot-sdk 3.x）
- [ ] チャットボット: Flex Message カルーセルUI（現在はテキストベース）
- [ ] チャットボット: 有料予約時のCoiney決済URL連携
- [ ] チャットボット: 仮予約確認フロー（confirmation_status='pending'）との統合
- [ ] セグメント配信: 配信履歴・開封率レポート画面
- [ ] セグメント配信: Flex Message テンプレート対応
- [ ] リマインダー: 顧客ごとの送信時刻カスタマイズ
- [ ] リマインダー: リマインダー送信のON/OFF切り替え（顧客単位）
- [ ] リッチメニュー: API経由での動的リッチメニュー設定
- [ ] 既存 views_booking.py 内の LineBotApi 直接呼び出しを line_bot_service.py に移行
- [ ] LINE Webhook の署名検証ログ（SecurityLog連携）
- [ ] backfill_line_customers コマンドの本番実行

### 既存機能の改善
- [ ] シフトテスト 34件の失敗修正（LINE機能とは無関係）
- [ ] line-bot-sdk deprecation warning 対応（v3 utils）
