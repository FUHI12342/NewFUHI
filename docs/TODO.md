# TODO -- 未実装タスク・残課題

最終更新: 2026-04-16

---

## 1. ソースコード内の TODO/FIXME

### booking/services/external_data.py
- [ ] **L77**: `# TODO: 実際のAPI呼び出し実装` -- OpenWeatherMap API統合（現在はモックデータを返却）
- [ ] **L136**: `# TODO: 実際のAPI呼び出し実装` -- Google Business Profile API統合（現在はモックデータを返却）

### MB_IoT_device_main/code.py
- [ ] **L303**: `# TODO: Implement web server request handling` -- Pico Wデバイスのウェブサーバーリクエストハンドリング実装
- [ ] IoT Config API の `?provision=1` パラメータ対応（WiFi認証情報の取得）

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
- [ ] 決済処理のテスト追加（Coiney API mock + webhook + refund）
- [ ] 予約作成E2Eテスト（選択→決済→確認の全フロー）
- [ ] SNS投稿の統合テスト強化（Playwright mock + 画像処理 + リトライ）
- [ ] CI/CD で `continue-on-error: false` に変更（テスト通過を必須化）

---

## 9. パフォーマンス・スケーラビリティ

- [ ] SQLite → PostgreSQL 移行検討（同時接続数増加時）
- [ ] 静的ファイルのCDN配信（CloudFront等）
- [ ] ダッシュボードAPI のキャッシュ戦略（Redis cache）
- [ ] IoTイベントの大量データ対応（パーティション or アーカイブ）
- [ ] `SiteSettings.load()` の Redis キャッシュ化（毎リクエスト2回DB問い合わせ削減）
- [ ] `SensorDataAPIView` のストリーミング対応（全件メモリロード回避）
- [x] N+1クエリ修正: `check_property_alerts` （prefetch_related + 一括取得）
- [x] N+1クエリ修正: `get_available_dates` （14日分Schedule一括取得）

---

## 10. セキュリティ

### CRITICAL（手動対応必須）
- [ ] **Gemini APIキーのローテーション**（git履歴 commit bf017c46 で露出）
- [ ] **db.sqlite3 の git 履歴削除**（`git-filter-repo --path db.sqlite3 --invert-paths`）

### HIGH
- [ ] Stored XSS 対策: `|safe` フィルタのレンダー時再サニタイズ（`safe_html` カスタムフィルタ）
- [ ] `AdminCSPRelaxMiddleware` の CSP 緩和を最小限に（`unsafe-eval` のみに限定）
- [ ] `StoreThemeForm` / `StoreAdminForm` の `fields='__all__'` → 明示的フィールド指定
- [ ] `CustomerFeedbackAPIView` の `permission_classes=[]` → GET/POST分離
- [ ] Embed OTP ブルートフォース防止（`django-ratelimit` で 5/min 制限）
- [ ] `LineCallbackView.get` の God メソッド分割（260行→`LineBookingService`に抽出）
- [ ] Coiney 決済処理の重複コード統合（`payment_service.py` に抽出）
- [ ] `SecurityAuditMiddleware._rate_counter` を Redis ベースに変更
- [ ] `fields.py` の broad except を `InvalidToken` 限定に変更
- [ ] bare `except Exception: pass` のロギング追加（middleware.py, views_line_admin.py）

### 既存
- [ ] social-auth-app-django 5.6.0+ への移行（Django 5.1必要 -- Django 5.x 移行と同時に）
  - 現在 GHSA-wv4w-6qv2-qqfg は CSRF_COOKIE_HTTPONLY + session validation で緩和
- [ ] Django 5.x LTS 移行計画策定
- [ ] IoTデバイスのAPIキーローテーション自動化
- [ ] 管理画面の2FA（TOTP）対応

### 完了済み（2026-04-14）
- [x] `hmac.compare_digest` 導入: embed API key + OTP 比較（タイミング攻撃防止）
- [x] `timezone.now()` 修正: `line_chatbot.py` の `datetime.now()` 置換
- [x] cancel_token 競合条件修正（IntegrityError リトライ）
- [x] IoT Config API にレート制限追加 + WiFi パスワード返却をプロビジョニング時のみに制限
- [x] Gemini API キーを URL クエリパラメータ → `x-goog-api-key` ヘッダーに移行
- [x] PostHistory / DraftPost にDBインデックス追加（6件）

---

## 11. 運用改善

- [ ] デプロイのゼロダウンタイム化（Blue-Green or Rolling）
- [ ] ログ集約（CloudWatch Logs or ELK Stack）
- [ ] アラート閾値の自動チューニング（IoT/在庫）
- [ ] マルチテナント対応の本格化（現在はマルチストアだが単一DB）
- [ ] デプロイ失敗時の自動ロールバック（`deploy_to_ec2.sh` に追加）
- [ ] systemd: Celery に `Wants=redis-server.service` 追加
- [ ] Gunicorn ワーカー数を CPU コア数に応じて自動設定

---

## 12. UI/UX

### 完了済み（2026-04-15）
- [x] 日本語フォント追加（Noto Sans JP, Hiragino, YuGothic）
- [x] フォーカスインジケーター追加（WCAG 2.4.7準拠）
- [x] prefers-reduced-motion 対応
- [x] インラインスタイル → CSSクラス抽出（social_drafts 2テンプレート: 95箇所→2箇所）
- [x] ブランドカラー統一（`#4f46e5`/`#6366f1` → `var(--brand-primary)`）
- [x] 空の admin.css 削除
- [x] admin_components.css 新規作成（ダークモード対応済みコンポーネント）
- [x] インラインスタイル → CSSクラス抽出（page_builder 4テンプレート + store/change_form + site_wizard + theme_customizer: 37箇所→0箇所、動的値6箇所のみ残存）
- [x] admin_components.css に共有テーブル・ボタン・ステータスクラス追加（`.ac-table`, `.ac-btn--brand`, `.ac-status--*` 等）
- [x] store/change_form.html の onmouseover/onmouseout JSホバー → CSS :hover に移行

### 未実装
- [ ] モバイルアプリ対応（PWA or ネイティブ）
- [ ] ダッシュボードのリアルタイム更新（WebSocket）
- [x] ARIA属性追加（editor, page_layout, theme_customizer, site_wizard, generate: dialog/toolbar/switch/progressbar/group等14箇所）

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
- [x] EC2 Playwright 環境確認・インストール（deploy script + requirements.txt 対応済み）
- [x] `setup_browser_session` 管理コマンド実装（セッション設定・確認・環境チェック）
- [ ] Instagram アカウント作成 + EC2セッション設定（手動作業）
- [ ] GBP アカウント作成 + オーナー確認 + EC2セッション設定（手動作業）
- [ ] 投稿のA/Bテスト機能
- [ ] 投稿パフォーマンス分析（エンゲージメント率追跡）

---

## 15. アーキテクチャ改善（2026-04-14 レビューで判明）

### 高（正確性・安全性）
- [ ] settings.py 統合（`project/settings.py` と `project/settings/` の二重管理解消）
- [ ] 非ローカル環境で SQLite 使用時にエラー発生させる起動チェック追加
- [ ] API バージョニング導入（`/api/v1/` プレフィックス）

### 中（保守性向上）
- [ ] `booking/models/cms.py`（919行）を分割 → `cms.py`, `admin_config.py`, `analytics.py`, `security.py`, `ml.py`
- [ ] `booking/` モノリスからドメイン別アプリ抽出（`shifts/`, `hr/`, `iot/`, `social/`）
- [ ] 統一通知サービス作成（LINE, email, event を統合）
- [ ] フィーチャーフラグの統合（SiteSettings booleans + SystemConfig KV → 一元管理）
- [ ] `UserSerializer` を `booking/models/core.py` → `booking/serializers/` に移動
- [ ] `pytz.timezone('Asia/Tokyo')` ハードコード19箇所 → store.timezone + zoneinfo ヘルパー
- [ ] サービス層の型アノテーション追加（availability.py, post_dispatcher.py 等）
- [ ] `views_booking.py` のインライン import 解消（循環依存のリファクタリング）

---

## 優先度分類

### 高（ビジネスインパクト大）
- Gemini APIキーローテーション（CRITICAL セキュリティ）
- git 履歴から db.sqlite3 削除（CRITICAL セキュリティ）
- 外部API統合（天気・Google Business Profile）
- LINE機能改善（Flex Message, 配信レポート）
- 決済処理テスト追加

### 中（運用効率向上）
- バックアップ復元コマンド
- S3保持ポリシー
- デモデータ一括削除
- テストカバレッジ向上
- settings.py 統合
- SiteSettings キャッシュ化

### 低（将来的な改善）
- PostgreSQL移行
- CDN配信
- モバイルアプリ
- WebSocket リアルタイム更新
- モノリス分割
