# CHANGELOG

最終更新: 2026-04-14

---

## 2026-04-14: SNS自動投稿 Phase4 — Instagram + GBP 完全対応 + コード品質改善

### feat
- Instagram ブラウザポスター堅牢化: 多言語セレクタフォールバック(日/英), 画像ファイル存在チェック, 各ステップのデバッグスクリーンショット
- GBP ブラウザポスター堅牢化: 多言語セレクタフォールバック, 画像アップロード対応(オプション), 投稿成功メッセージ検出
- ブラウザ投稿共通基盤: `browser_session()` コンテキストマネージャでリソースリーク防止, モバイルviewportコンテキスト追加
- ブラウザ投稿でも PostHistory を記録する仕組みを追加 (`_dispatch_browser_post()`, `task_browser_post` タスク)
- 投稿ルーティング自動判定: X=API優先→ブラウザフォールバック, Instagram/GBP=ブラウザ自動
- 管理画面 list.html: 「API投稿」「ブラウザ投稿」ボタンを「投稿」1つに統合
- 管理画面: 各ドラフトにプラットフォーム別セッション状態(有効/要セットアップ/期限切れ)を表示
- `setup_browser_session` 管理コマンド: EC2上でのブラウザセッション設定（X11転送GUI対応）
- デプロイスクリプトに Playwright ブラウザ自動インストール追加
- Celery worker に `browser_posting` キュー追加

### security
- IDOR防止: 全ビューに store レベル認可チェック追加
- プラットフォーム入力バリデーション (`VALID_PLATFORMS` frozenset)
- プロファイルディレクトリ権限 0o700, storage_state.json 権限 0o600
- `--no-sandbox` を root 実行時のみに制限（条件付きサンドボックス）
- list.html の innerHTML → DOM API (XSS防止), ハードコードURL → {% url %} タグ
- エラーメッセージからの内部情報漏洩防止（ユーザー向けメッセージに統一）
- retry_count を F() アトミック更新に変更（レースコンディション防止）

### test
- test_instagram_poster.py (7テスト): バリデーション, セレクタ多言語, ブラウザフロー
- test_gbp_poster.py (8テスト): バリデーション, セレクタ多言語, ブラウザフロー, 成功確認検出
- test_dispatch_browser.py (9テスト): ルーティング, セッション状態, PostHistory記録, ヘルパー関数
- 全30テスト通過

---

## 2026-04-14: SNS自動投稿 Phase3 — 画像自動添付 + 管理画面UI改善

### feat
- DraftPost に画像自動添付機能: 出勤キャスト thumbnail → store thumbnail の優先順で自動選択
- staff_list ページに OG メタタグ追加 (og:title, og:image, twitter:card) — X カードプレビュー対応
- 管理画面サイドバー統合: SNS自動投稿グループを6項目→3項目に整理
- DraftPost Admin に画像プレビュー表示・「AI下書き生成」「即時投稿」アクション追加
- サイドバーに「AI下書き生成」「投稿履歴」カスタムリンク追加

### refactor
- sns_image_selector.py を新規モジュールとして分離（画像選択ロジック）
- PostTemplate, KnowledgeEntry, PostHistory を hidden_models でサイドバーから非表示化

---

## 2026-04-08: シフトUI大幅改善 + 管理画面UX改修

### feat
- シフト表示色を10色プリセットに変更、作成後すぐに編集サイドバー表示
- シフト期間カードを横スクロール表示に変更
- シフトメニューUI改善 -- 必要人数設定を統合ページ化、3ボタンバー追加
- 定休日を曜日チェックボックス選択式に変更・店舗削除ボタン非表示
- 店舗編集画面のタブ内に保存ボタン配置・サイトカスタマイズをタブ化
- 予約コマをラジオボタン選択に変更
- 店舗スケジュール設定UIを改善（ドロップダウン化・fieldsets整理）
- カレンダーに1時間ごとの濃淡表示と区切り線を追加

### fix
- ヘルプツアー最終ステップ修正、代理入力ボタン常時表示
- 自動配置ダイアログ文言改善、ヘルプボタン追加、スマホ対応
- 日付指定オーバーライドの種別セレクトボックスの幅を拡大
- 休業日パネル表示修正、代理記入を複数日一括申請化、ボタン色修正
- 3ボタンバーを希望提出状況の下に移動、必要人数設定をインライン展開化
- シフト保存/削除/作成後にページリロードで確実に反映
- 既存シフトクリック時にサイドバーを表示する
- シフト作成/編集/削除のカレンダー即時反映を修正
- シフト保存/削除のカレンダー即時反映 + 時刻5分刻み対応
- シフト編集が保存されない問題を修正、プリセット色をデモデータに合わせる
- 新規作成シフトのHTMX属性が動作しない問題を修正
- シフト作成時にstart_time/end_timeが文字列のまま保存される問題を修正
- シフト作成時の重複エラーを更新処理に変更（UNIQUE constraint対策）
- シフト期間作成時のdeadline解析エラーとJS unexpected token対策
- 店舗の削除権限を復活（右サイドバー）
- インライン内の削除リンクをJS非表示
- スケジュール設定の削除ボタンを非表示に

### chore
- 未使用の/users/エンドポイントを無効化

### docs
- 営業資料・比較資料の更新

---

## 2026-04-07: キャンセル通知 + 予約フォーム統合

### feat
- キャンセル完了時に顧客へメール通知を送信
- 予約フォームを「予約者名（ペンネーム可）」1フィールドに統合

### fix
- embed メール送信エラー時の pen_name 参照を削除

---

## 2026-04-06: 無料予約モード

### feat
- 無料予約モード + ペンネーム対応（SiteSettings.free_booking_mode で決済スキップ）

---

## 2026-04-05: in-appブラウザ対応 + 仮予約修正

### feat
- in-appブラウザ検出・LINEログイン改善・WPキャスト別ショートコード

### fix
- 仮予約の自動キャンセルを20分に統一・確実に動作するよう修正
- in-appブラウザ時のボトムシートモーダル復元+LINE直接開くボタン追加
- in-appブラウザモーダル廃止、LINEアプリからログイン案内に変更
- in-appブラウザモーダルをボトムシート型に変更（スマホ対応）

---

## 2026-04-04: LINE連携 + デモモード + 自動バックアップ + 埋め込みUI

### feat
- LINE連携6フェーズ実装完了 + デモモード切替 + 自動バックアップ + 埋め込みコード生成UI
- デモモードにシフト・出勤・チェックインデータを追加
- チェックイン画面に口頭コードの当日のみ有効の注意文を追加
- iframe内予約フロー完結（embed_token方式）
- 埋め込みコード生成UIリデザイン（タブ切替・ダークコードブロック・プレビュー）
- 管理画面からWPプラグインDL + HTMLコードはプラグイン不要の案内追加
- WordPress ショートコード対応 + プラグインファイル追加

### fix
- パンくず・タブのモバイルCSSをjazzmin_overrides.cssに追加
- 管理画面スマホ版のパンくず・タブ表示を改善
- 管理画面・埋め込みカレンダーのスマホ表示を改善
- LINE/メールコールバックでaware datetimeのmake_aware二重適用を修正
- 埋め込みコード生成UIのタブボタンにtype=button追加
- 埋め込みコード生成UIのJSエスケープ修正 (format_html→mark_safe)

### chore
- add AI training opt-out notice

---

## 2026-04-03: デモモード切替 + 自動バックアップ

### デモモード切替
- 主要8モデルに `is_demo = BooleanField(default=False, db_index=True)` 追加
  - Order, POSTransaction, Schedule, VisitorCount, WorkAttendance, CustomerFeedback, BusinessInsight, StaffRecommendationResult
- SiteSettings に `demo_mode_enabled` フラグ追加（管理画面→メインサイト設定→デモモード）
- `demo_data_service.py` -- `is_demo_mode_active()`（60秒キャッシュ）, `get_demo_exclusion(prefix)`
- `DashboardAuthMixin.build_demo_filter(prefix)` で全ダッシュボードビューに統一フィルタ適用
- 対象ビュー: views_dashboard_sales, views_dashboard_analytics, views_dashboard_operations, views_analytics
- `seed_mock_data.py` -- 全シードデータを `is_demo=True` でマーク
- `generate_live_demo_data` 管理コマンド -- 当日分のデモデータ自動生成
- Celeryタスク `generate_live_demo_data_task`（30分毎）
- ダッシュボードに「DEMO MODE」バナー表示（デモモード有効時）
- 管理画面でデモモード変更時にキャッシュ自動無効化

### 自動バックアップ
- BackupConfig シングルトンモデル（interval: off/minute/hourly/daily, S3設定, 保持数, LINE通知）
- BackupHistory モデル（status, trigger, ファイルサイズ, S3アップロード状況, エラーメッセージ）
- `backup_service.py` -- Python `sqlite3.backup()` によるアトミックバックアップ
- S3アップロード（boto3, `exclude_demo_data` オプション対応）
- ローカル保持ポリシー（デフォルト30件、古いファイル自動削除）
- `create_backup` 管理コマンド（手動バックアップ）
- Celeryタスク `run_scheduled_backup`（毎分実行、内部で間隔判定）
- 管理画面: BackupConfig設定 + 手動バックアップアクション + BackupHistory一覧（読み取り専用）

### テスト
- `test_demo_data_service.py` -- 8テスト（フィルタON/OFF、キャッシュ、プレフィックス、実クエリ）
- `test_backup_service.py` -- 7テスト（シングルトン、バックアップ作成、S3無効時、失敗記録、保持ポリシー）
- 全15テスト パス

### マイグレーション
- 0118: is_demo フィールド + demo_mode_enabled + BackupConfig + BackupHistory

---

## 2026-04-02: LINE機能拡張6フェーズ + 管理画面UI大改修

### LINE機能拡張（6フェーズ）

#### Phase 1: 基盤整備
- LineCustomer / LineMessageLog モデル追加
- SiteSettings に LINE フィーチャーフラグ 3つ追加（line_chatbot_enabled, line_reminder_enabled, line_segment_enabled）
- LINE Messaging API 共通サービス（line_bot_service.py）-- push_text, reply_text, push_flex, get_customer_or_create
- LINE Webhook 受信エンドポイント（/line/webhook/）-- 署名検証、Follow/Unfollow/Message/Postback対応
- Admin登録（LineCustomerAdmin, LineMessageLogAdmin）
- バックフィル管理コマンド（backfill_line_customers）
- マイグレーション: 0115

#### Phase 2: LINEチャットボット予約
- 会話エンジン（状態機械: idle→select_store→select_staff→select_date→select_time→confirm）
- 空き枠検索サービス（availability.py）
- 10分タイムアウト自動リセット
- Schedule 作成 + QR生成 + 通知

#### Phase 3: リマインダー通知
- Schedule に reminder_sent_day_before / reminder_sent_same_day フラグ追加
- 前日18:00リマインダー / 当日2時間前リマインダー
- Celery Beat スケジュール追加
- フィーチャーフラグによる制御
- マイグレーション: 0116

#### Phase 4: リッチメニュー連携
- Postback ハンドラ（start_booking, check_booking, contact）
- リッチメニュー設定手順書（docs/line_richmenu_setup.md）

#### Phase 5: セグメント配信
- セグメント計算サービス（new/regular/vip/dormant）
- 日次セグメント再計算 Celery タスク（毎日04:30）
- セグメント配信管理画面（/admin/line/segment/）
- 配信実行タスク（レート制限付き一括送信）

#### Phase 6: 仮予約確認フロー
- Schedule に confirmation_status / confirmed_at / confirmed_by / rejection_reason 追加
- 仮予約確認管理画面（/admin/line/pending/）
- 確定/却下 API（/api/line/reservations/{id}/confirm|reject/）
- delete_temporary_schedules に confirmation_status='none' 条件追加
- LINE通知（確定/却下）
- マイグレーション: 0117

### 管理画面UI改修
- 管理画面全リスト 10件ページング + ソート対応
- 管理画面リスト省略テキストに自動一方通行マーキー効果
- SNSサイドバーにInstagram/Xタブ切替UI追加
- シフト超過強調表示, メンテナンスログ, Admin改善, フッターSNSリンク
- サイドバー並び順を管理画面から設定可能に + 運営会社をデフォルト最下部に
- SNS連携(Threads/TikTok追加), AI推薦充実化, ダッシュボード改善
- ダークモード無効化（ライトモード専用に統一）
- デプロイにスモークテスト自動実行を統合
- LINE未フォロー/ブロック時の予約テスト + デバッグモード
- 分析サブタブに簡易説明文を追加
- サイドバースクロール位置の自動保持
- マルチストア対応, メンテナンスモード, カメラガイド, ダッシュボード改善
- ダッシュボード改善 - デモデータ, ページネーション, チェックインKPI, 免責表示
- 管理UI改善, カスタムページ, テーマシステム, ヘルスエンドポイント
- 顧客キャンセルフロー, LINE非フレンドフォールバック

### fix
- Media.save() がタイトルを10文字で切り詰める + 毎回上書きする問題を修正
- ナビ店舗名折り返し防止, ご予約リンク廃止, 所属キャスト→キャスト情報
- deploy script maintenance mode uses raw SQL to avoid migration ordering issue
- スモークテスト関連修正（curl追従, URL修正, .envソース）
- EC/Instore analysis chart のデモデータ追加
- add csrf_exempt to public cancel views for LINE in-app browser

---

## 2026-03-30: SNS自動投稿 + WordPress埋め込み

### feat
- SNS自動投稿基盤 -- モデル（SocialAccount, PostTemplate, PostHistory, KnowledgeEntry, DraftPost）
- X API投稿サービス + ディスパッチャー
- SNS下書きAI生成 + LLM Judge評価 + ブラウザ自動投稿
- platform-specific AI generation rules and draft editing UI
- wire browser posting into draft flow with API/browser toggle
- WordPress iframe埋め込み -- 予約カレンダー + シフト表示
- 管理画面の機能表示制御 -- SiteSettingsトグル6種追加
- 全ロールに sns_posting グループの表示権限を追加

### fix
- LLM Judge JSON parsing for markdown code blocks from Gemini
- update Gemini model to 2.5-flash (free tier supports flash only)
- increase maxOutputTokens for Gemini 2.5-flash thinking overhead
- disable thinking for LLM Judge, request concise feedback
- サイドバー非表示グループのモデルが「その他」に流出するバグ修正

---

## 2026-03-23: 本番ハードニング + E2Eテスト + セキュリティレビュー

### feat
- CMS通知設定 + ErrorReportモデル + イベント通知サービス

### security
- セキュリティレビュー全19件対応
- IoTセキュリティ強化 -- 認証・バリデーション・暗号鍵必須化
- CSP unsafe-eval対応 + Tailwind CDN→ローカルCSS + favicon追加
- デプロイ安全策 -- env整合性チェック + systemdサービス管理

### fix
- 依存パッケージ42脆弱性修正 + settings.pyリファクタ
- KPIScoreCardAPIView 500エラー修正（Storeフィルタ修正 + TableSeatインポート追加）
- 最後のハードコードURL2箇所を{% url %}タグに置換
- 旧URLリダイレクトをi18n_patterns外に移動 (500→301)
- i18n言語維持修正 + 旧URL 404リダイレクト
- ec_dashboard.htmlにload static追加 (500エラー修正)
- QA残課題4件対応 -- プレースホルダー表示・CSP・Tailwind移行・IoTリトライ

### refactor
- 不要ファイル削除 + Sentry導入 + セキュリティ改修

### docs
- 本番ローンチチェックリスト + デプロイスクリプト修正
- E2Eテストレポート最終版 -- 177/177 PASS (3スイート統合)
- 多言語営業資料 + スクリーンショット + i18nダッシュボード

---

## 2026-03-20: ダッシュボード大規模改修 + 管理画面i18n根治

### feat
- ダッシュボード大規模改修 -- AI分析・セキュリティ・営業資料
- 全ダッシュボードタブにデモデータ追加
- キャスト・ECショップ売上・店内メニュー売上タブ追加
- チャネル別売上分析API + キャストタブ動的ラベル
- チェックイン機能拡張 -- 通知・ダッシュボード・無料予約QR・Admin改善
- シフト品質改善7項目 + QRチェックイン認証強化
- 管理画面i18n根治 + 言語固定設定
- 売上データ1年分拡充コマンド (extend_order_data)

### fix
- 管理画面のページ遷移で言語がリセットされる問題を修正
- Jazzmin設定のi18n対応 + 不足翻訳4件追加
- デプロイスクリプトに compilemessages を追加
- keep sidebar menu groups open after navigation
- IoT sensor page i18n + escapejs safety for JS translations
- ダッシュボードのダークモード対応
- セキュリティ・コード品質修正（レビュー指摘対応）

---

## 2026-03-19: シフト自動調整 + テスト強化

### feat
- シフト自動調整カバレッジベース化 + 不足枠再募集 + 交代・欠勤申請
- シフト自由入力モード -- 募集期間なしでもシフト提出可能に
- add download_missing_images management command

### fix
- 本番セキュリティ改善 + ファイル分割 + テスト修正
- コードレビュー指摘のCRITICAL/HIGH修正 + テスト68件追加
- 営業時間外リクエストを全拒否→クリップに変更
- display product images on shop page

---

## 2026-03-18: i18n完全翻訳 + POS/在庫/シフト統合改修

### feat
- i18n 100%カバレッジ -- 全画面完全翻訳 (7ロケール x 1366文字列)
- ナイトモード切替 + サイドバー開閉状態の維持
- オンラインストアUX改善 + 送料機能追加 + IoT全アカウント表示
- 注文一覧にチャネルグループフィルタ追加（店内/EC切替対応）
- シフト必要人数設定（曜日別デフォルト + 日付オーバーライド）
- 店内メニューとEC商品管理を完全分離
- メニュー再構成 + スタッフ評価システム + ShiftChangeLog 403修正
- キッチン完了取消 + 従業員一覧統一 + SiteSettings 403修正
- 管理画面UI統一 + スタッフ機能拡張
- SiteSettings管理画面のUI改善
- LINE通知フル実装 + ホームページカード設定反映 + UI修正
- PIN打刻→タイムカード打刻に名称変更、管理サイドバー設定をシステムに分離
- full sidebar feature toggles for business type customization
- sensor graph 1.5-day scrollable view with AM/PM time axis
- HTMX partial navigation, staff/cast grid separation, auto-refresh
- add sidebar visibility toggles and restaurant menu demo data

### fix
- 注文管理→注文履歴管理、小メニュー名も履歴一覧に変更
- SiteSettings各種UI修正（右端スペース, タブ折り返し, 保存ボタンstickyバー）
- キッチン完了済み並び順を昇順に + 取り消し時にアイテムをSERVEDに戻す
- シフトメニュー重複解消 + 日付指定オーバーライドのリンク追加
- changelistテーブル横スクロール対応 + 商品一覧カラム短縮
- 出退勤ボードJSON表示バグ修正 + LINE IDセキュリティ + UI改善
- StockMovement管理画面廃止 + SiteSettings UI整理
- 機能ON/OFFからAIアシスタント非表示、シフトテンプレート廃止
- シフト自動配置・公開ボタンが動作しない問題を修正
- KDS shows only in-store orders, add order delete action
- 商品名クリックで編集画面へ遷移可能に（list_display_links追加）

---

## 2026-03-17: EC決済 + シフト抜本改修 + EC注文管理

### feat
- EC決済フロー（カート→決済→完了）+ 占いグッズデモデータ20品
- Coiney EC決済統合 + 従業員管理メニュー + 占い師枠情報表示
- EC注文管理ダッシュボード + POS領収書 + 勤務実績 + シフト改善
- シフト管理 抜本的改修 -- 休業日・ロール別サイドバー・マイシフト
- シフト撤回・個別修正 + スタッフ/キャスト分離 + マイページプロフィール
- スケジュール済み撤回・個別編集・再募集機能
- 管理者からのシフト希望代理登録

### fix
- シフトAPI セキュリティ・品質改修 -- 認証・IDOR・バリデーション・ファイル分割
- AdminMenuConfig とコード側デフォルトのマージ + デプロイ時自動同期
- deploy script venv path (.venv) / pkill pattern to avoid killing SSH session
- スタッフ種別ラベル変更(占い師→キャスト)
- delete_food_drink_data で関連OrderItem/StockMovementも削除
- 従業員管理メニュー4項目のみ + 飲食データ削除コマンド追加

### refactor
- シフトグループのモデルリンクを非表示化（カレンダー+本日のシフトのみ表示）
