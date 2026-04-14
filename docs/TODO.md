# TODO -- 未実装タスク・残課題

最終更新: 2026-04-09

---

## 1. ソースコード内の TODO/FIXME

### booking/services/external_data.py
- [ ] **L77**: `# TODO: 実際のAPI呼び出し実装` -- OpenWeatherMap API統合（現在はモックデータを返却）
- [ ] **L136**: `# TODO: 実際のAPI呼び出し実装` -- Google Business Profile API統合（現在はモックデータを返却）

### MB_IoT_device_main/code.py
- [ ] **L303**: `# TODO: Implement web server request handling` -- Pico Wデバイスのウェブサーバーリクエストハンドリング実装

---

## 2. デモモード

- [ ] デモデータ生成: POSTransaction, WorkAttendance, CustomerFeedback の当日データ生成対応
- [ ] デモモードAPI: REST APIレスポンスにもデモフィルタ適用
- [ ] デモデータ一括削除コマンド（`clear_demo_data`）

---

## 3. 自動バックアップ

- [ ] S3保持ポリシー実装（`s3_retention_days` に基づく古いS3オブジェクト削除）
- [ ] バックアップ復元コマンド（`restore_backup`）
- [ ] バックアップファイルのダウンロード機能（管理画面から）
- [ ] `exclude_demo_data` オプション実装（デモデータ除外バックアップ）
- [ ] LINE Notify 通知のテスト送信機能

---

## 4. LINE機能拡張

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
- [ ] line-bot-sdk deprecation warning 対応（v3 utils）

---

## 5. 外部API統合

- [ ] OpenWeatherMap API 実装（`services/external_data.py` -- 現在モック）
- [ ] Google Business Profile API 実装（`services/external_data.py` -- 現在モック）

---

## 6. AI/チャット機能

- [ ] AIチャット機能の復旧（Gemini APIキー再発行待ち -- `views_chat.py` のコメントアウト解除）
  - `AdminChatAPIView` -- 管理者チャット
  - `GuideChatAPIView` -- 公開チャット（廃止済み -- Gemini APIコストリスク対策）

---

## 7. PDFドキュメント

- [ ] 全機能の使用方法PDFを生成・更新（LINE連携、デモモード、バックアップ含む）

---

## 8. テスト

- [ ] シフトテスト34件の失敗修正（LINE機能とは無関係の既存テスト）
- [ ] テストカバレッジ80%目標への到達（現状未計測）
- [ ] E2Eテストの継続的実行環境構築（CI/CD統合）

---

## 9. パフォーマンス・スケーラビリティ

- [ ] SQLite → PostgreSQL 移行検討（同時接続数増加時）
- [ ] 静的ファイルのCDN配信（CloudFront等）
- [ ] ダッシュボードAPI のキャッシュ戦略（Redis cache）
- [ ] IoTイベントの大量データ対応（パーティション or アーカイブ）

---

## 10. セキュリティ

- [ ] social-auth-app-django 5.6.0+ への移行（Django 5.1必要 -- Django 5.x 移行と同時に）
  - 現在 GHSA-wv4w-6qv2-qqfg は CSRF_COOKIE_HTTPONLY + session validation で緩和
- [ ] Django 5.x LTS 移行計画策定
- [ ] IoTデバイスのAPIキーローテーション自動化
- [ ] 管理画面の2FA（TOTP）対応

---

## 11. 運用改善

- [ ] デプロイのゼロダウンタイム化（Blue-Green or Rolling）
- [ ] ログ集約（CloudWatch Logs or ELK Stack）
- [ ] アラート閾値の自動チューニング（IoT/在庫）
- [ ] マルチテナント対応の本格化（現在はマルチストアだが単一DB）

---

## 12. UI/UX

- [ ] モバイルアプリ対応（PWA or ネイティブ）
- [ ] ダッシュボードのリアルタイム更新（WebSocket）
- [ ] 管理画面のダークモード復活（現在はライトモード固定）

---

## 13. EC機能

- [ ] PayPay オンライン決済対応（現在はPOS店頭のみ）
- [ ] 複数配送先対応
- [ ] クーポン・ポイントシステム
- [ ] 在庫切れ時の入荷通知メール

---

## 14. SNS投稿

- [x] X API v2 テキスト投稿 (OAuth 2.0 PKCE)
- [x] AI下書き生成 (Gemini Flash)
- [x] 予約URL自動付与
- [x] TikTok OAuth + Content Posting API
- [x] DraftPost への画像自動添付
- [x] staff_list ページ OGメタタグ (X カードプレビュー)
- [x] 管理画面サイドバー統合 (6項目→3項目)
- [x] Instagram ブラウザ投稿堅牢化（多言語セレクタ + 画像バリデーション + デバッグスクリーンショット）
- [x] GBP ブラウザ投稿堅牢化（多言語セレクタ + 画像アップロード対応 + 成功確認検出）
- [x] ブラウザ投稿の PostHistory 記録対応
- [x] 投稿ルーティング自動判定（X=API優先/Instagram・GBP=ブラウザ自動）
- [x] 管理画面に BrowserSession 状態表示
- [x] 投稿ボタン統合（API/ブラウザ → 1つの「投稿」ボタン）
- [ ] X API メディアアップロード (OAuth 1.0a)
- [ ] Instagram Graph API（現在はブラウザ自動化のみ）
- [ ] Instagram アカウント作成 + EC2セッション設定
- [ ] GBP アカウント作成 + オーナー確認 + EC2セッション設定
- [ ] EC2 Playwright 環境確認・インストール
- [ ] 投稿のA/Bテスト機能
- [ ] 投稿パフォーマンス分析（エンゲージメント率追跡）

---

## 優先度分類

### 高（ビジネスインパクト大）
- 外部API統合（天気・Google Business Profile）
- LINE機能改善（Flex Message, 配信レポート）
- シフトテスト修正

### 中（運用効率向上）
- バックアップ復元コマンド
- S3保持ポリシー
- デモデータ一括削除
- テストカバレッジ向上

### 低（将来的な改善）
- PostgreSQL移行
- CDN配信
- モバイルアプリ
- WebSocket リアルタイム更新
