# 実装済み機能一覧 (FEATURES.md)

最終更新: 2026-04-09

---

## 1. 予約管理 (Booking Management)

**概要**: LINE / メール / 埋め込みカレンダー経由での予約受付から、チェックイン・キャンセル・返金までの一連のフローを管理。

### 1.1 予約フロー

| 機能 | URL | 説明 |
|------|-----|------|
| トップページ | `/` | 店舗カード・占い師カード・カレンダーカード・ショップカード表示 |
| 店舗一覧 | `/stores/` | 店舗サムネイル・営業時間・アクセス情報表示 |
| 全スタッフ一覧 | `/fortune-tellers/` | 全店舗のキャスト横断一覧 |
| スタッフ一覧 | `/store/<id>/staffs/` | 店舗所属のキャスト一覧（おすすめ順） |
| 店舗アクセス | `/store/<id>/access/` | 地図・アクセス情報表示 |
| スタッフカレンダー | `/staff/<id>/calendar/` | 時間枠カレンダー（30分/60分コマ対応） |
| 仮予約作成 | `/staff/<id>/prebooking/<year>/<month>/<day>/<hour>/` | 時間枠選択 + LINE/メール経路選択 |
| 日付先行カレンダー | `/date-calendar/` | 日付を先に選択し、空きスタッフを表示 |
| 予約経路選択 | `/booking/channel-choice/` | LINE / メール予約を選択 |
| メール予約 | `/booking/email/` | OTP認証付きメール予約 |
| メール認証 | `/booking/email/verify/` | 6桁OTPコードによるメール認証 |
| LINE予約 | `/line_enter/` | LINE OAuth2ログインフロー |
| LINEコールバック | `/booking/login/line/success/` | LINE認証成功後に予約確定 |
| 無料予約モード | SiteSettings.free_booking_mode | 全予約が決済スキップ・即確定 |
| ペンネーム対応 | Schedule.pen_name | 予約者名をペンネーム1フィールドに統合 |

### 1.2 キャンセル・返金

| 機能 | URL | 説明 |
|------|-----|------|
| 管理者キャンセル | `/cancel_reservation/<id>/` | 管理画面からのキャンセル |
| 顧客キャンセル | `/cancel/<reservation_number>/` | 8桁キャンセルトークンによる顧客セルフキャンセル |
| キャンセル確認 | `/cancel/<reservation_number>/confirm/` | キャンセル確定画面 |
| キャンセル通知 | メール送信 | キャンセル完了時に顧客へメール通知 |
| 返金追跡 | Schedule.refund_status | none / pending / completed の3段階管理 |
| 仮予約自動キャンセル | Celery(毎分) | 20分経過した仮予約を自動キャンセル |

### 1.3 QRチェックイン

| 機能 | URL | 説明 |
|------|-----|------|
| QRコード表示 | `/reservation/<number>/qr/` | 予約番号ベースのQRコード表示 |
| チェックインスキャン | `/checkin/` | カメラスキャンまたは口頭バックアップコード入力 |
| チェックインAPI | `POST /api/checkin/` | QR / バックアップコードによるチェックイン処理 |

### 1.4 仮予約確認フロー（LINE管理）

| 機能 | URL | 説明 |
|------|-----|------|
| 仮予約一覧 | `/admin/line/pending/` | 確認待ち仮予約一覧 |
| 確認API | `POST /api/line/reservations/<id>/confirm/` | 仮予約を確定 |
| 却下API | `POST /api/line/reservations/<id>/reject/` | 仮予約を却下（理由付き） |

**主要モデル**: `Schedule`, `Store`, `Staff`, `StoreScheduleConfig`

**ステータス**: 本番稼働中

---

## 2. シフト管理 (Shift Management)

**概要**: シフト募集期間の作成から、希望収集、自動配置、公開、交代・欠勤申請までをカバーする包括的なシフト管理システム。

### 2.1 マネージャー機能

| 機能 | URL | 説明 |
|------|-----|------|
| シフトカレンダー | `/admin/shift/calendar/` | 月間シフトカレンダー（全スタッフ表示、10色プリセット） |
| 本日のシフト | `/admin/shift/today/` | タイムライン形式の当日シフト表示 |
| 必要人数設定 | `/admin/shift/staffing/` | 曜日別デフォルト＋日付指定オーバーライド統合ページ |
| シフト期間作成 | `POST /api/shift/periods/` | 月単位のシフト募集期間を作成 |
| 一括割当 | `POST /api/shift/bulk-assign/` | 複数シフトを一括作成 |
| 自動配置 | `POST /api/shift/auto-schedule/` | カバレッジベースの自動シフト割当 |
| シフト公開 | `POST /api/shift/publish/` | 確定シフトをスタッフへ通知 |
| シフト撤回 | `POST /api/shift/revoke/` | 公開済みシフトを撤回 |
| 再募集 | `POST /api/shift/reopen/` | 不足枠の再募集 |
| テンプレート適用 | `POST /api/shift/apply-template/` | 定型シフト（早番/遅番等）をワンタップ適用 |
| 週次グリッド | `GET /api/shift/week-grid/` | 週間シフトグリッドデータ |
| 変更ログ | `GET /api/shift/change-logs/` | シフト変更の監査証跡 |
| 休業日管理 | `GET/POST /api/shift/closed-dates/` | 店舗休業日の管理 |

### 2.2 スタッフ機能

| 機能 | URL | 説明 |
|------|-----|------|
| シフトカレンダー | `/shift/` | 自分のシフト閲覧 |
| 希望提出 | `/shift/<period_id>/submit/` | 出勤可能/希望/不可をカレンダーで提出 |
| 月別提出 | `/shift/<year>/<month>/` | 自由入力モード（募集期間なし） |
| 一括希望登録 | `POST /api/shift/requests/<period_id>/bulk/` | 複数日分の希望を一括送信 |
| 週コピー | `POST /api/shift/requests/<period_id>/copy-week/` | 先週のパターンをコピー |
| 不足枠一覧 | `GET /api/shift/vacancies/` | シフト不足枠リスト |
| 不足枠応募 | `POST /api/shift/vacancies/<id>/apply/` | シフト不足枠への応募 |
| 交代・欠勤申請 | `POST /api/shift/swap-requests/` | 交代/カバー/欠勤の申請 |
| 自分の希望 | `GET /api/shift/my-requests/` | 自分のシフト希望一覧 |

**主要モデル**: `ShiftPeriod`, `ShiftRequest`, `ShiftAssignment`, `ShiftTemplate`, `ShiftPublishHistory`, `ShiftChangeLog`, `StoreClosedDate`, `ShiftStaffRequirement`, `ShiftStaffRequirementOverride`, `ShiftVacancy`, `ShiftSwapRequest`

**ステータス**: 本番稼働中

---

## 3. POS (Point of Sale)

**概要**: タブレット/PC向けのPOSレジシステム。会計・レシート発行・キッチンディスプレイ連携。

| 機能 | URL | 説明 |
|------|-----|------|
| POSレジ画面 | `/admin/pos/` | 商品選択・会計操作・割引・税計算 |
| レシート表示 | `/admin/pos/receipt/<number>/` | レシート番号による印刷用表示 |
| キッチンディスプレイ | `/admin/pos/kitchen/` | 調理待ち・調理中の注文リアルタイム表示 |
| 注文作成API | `POST /api/pos/orders/` | POS注文作成 |
| アイテム追加API | `POST /api/pos/order-items/` | 注文アイテム追加 |
| 会計API | `POST /api/pos/checkout/` | 決済処理（現金/Coiney/PayPay/IC） |
| アイテムステータス変更 | `PATCH /api/pos/order-item/<id>/status/` | Ordered → Preparing → Served |
| キッチン注文HTML | `GET /api/pos/kitchen-orders/` | キッチン注文のHTML部分更新 |
| 注文完了 | `POST /api/pos/order/<id>/complete/` | 全アイテム配膳完了 |
| 注文完了取消 | `POST /api/pos/order/<id>/uncomplete/` | 完了を取り消しSERVEDに戻す |

**決済方法**: 現金, Coiney(クレジットカード), PayPay, IC決済(交通系/電子マネー), その他

**主要モデル**: `Order`, `OrderItem`, `POSTransaction`, `PaymentMethod`, `TaxServiceCharge`

**ステータス**: 本番稼働中

---

## 4. 在庫管理 (Inventory Management)

**概要**: 商品在庫のリアルタイム管理。入庫QR、閾値アラート、棚卸調整をサポート。

| 機能 | URL | 説明 |
|------|-----|------|
| 在庫ダッシュボード | `/admin/inventory/` | 在庫状況一覧・低在庫アラート表示 |
| 入庫フォーム | `/admin/inventory/stock-in/` | 商品コードスキャンによる入庫処理 |
| 入庫QR | `/stock/inbound/` | QRコード読取による入庫操作 |
| 入庫API | `POST /api/stock/inbound/apply/` | 在庫数量を原子的に更新（`select_for_update`） |
| メニュー表示 | `/menu/<store_id>/` | 顧客向けメニュー一覧 |
| メニューJSON API | `GET /api/menu` | 商品メニューJSON |
| 代替品提案API | `GET /api/products/alternatives/` | 欠品時の代替商品レコメンド |
| 低在庫アラートAPI | `GET /api/dashboard/low-stock/` | 閾値以下の在庫リスト |
| 自動発注提案API | `GET /api/dashboard/auto-order/` | 在庫と売上データに基づく発注提案 |
| 在庫アラート通知 | Celery(毎時) | LINE Notifyによる低在庫通知（4時間間隔制限） |

**主要モデル**: `Product`, `Category`, `StockMovement`, `ProductTranslation`, `ECProduct`, `ECCategory`

**ステータス**: 本番稼働中

---

## 5. 勤怠管理 (Attendance Management)

**概要**: QRコード/PIN/TOTP認証による打刻システム。ジオフェンスによる位置確認も対応。

| 機能 | URL | 説明 |
|------|-----|------|
| QR勤怠表示 | `/admin/attendance/qr/` | TOTP付きQRコードの表示（30秒更新） |
| PIN打刻画面 | `/admin/attendance/pin/` | 4桁PIN入力による打刻 |
| 出退勤ボード | `/admin/attendance/board/` | 全スタッフの当日出退勤ステータス |
| 勤務実績ダッシュボード | `/admin/attendance/performance/` | 月次勤務時間・出勤率の統計表示 |
| スマホ打刻ページ | `/attendance/stamp/` | ログイン不要のQRスキャン打刻 |
| 打刻API | `POST /api/attendance/stamp/` | TOTP認証付き打刻 |
| PIN打刻API | `POST /api/attendance/pin-stamp/` | PIN認証打刻 |
| QRスキャン打刻API | `POST /api/attendance/qr-stamp/` | QR+PIN認証打刻（ログイン不要） |
| マニュアル打刻API | `POST /api/attendance/manual-stamp/` | 管理者による代理打刻 |
| TOTP更新API | `POST /api/attendance/totp/refresh/` | TOTP QRコードの再生成 |
| 日次ステータスAPI | `GET /api/attendance/day-status/` | 当日の打刻ステータス取得 |
| 日次ステータスHTML | `GET /api/attendance/day-status-html/` | HTML部分更新 |
| 勤務実績API | `GET /api/attendance/performance/` | 期間指定の勤務実績データ |

**打刻種別**: 出勤 / 退勤 / 休憩開始 / 休憩終了

**主要モデル**: `AttendanceStamp`, `AttendanceTOTPConfig`, `WorkAttendance`

**ステータス**: 本番稼働中

---

## 6. 分析・ダッシュボード (Analytics & Dashboard)

**概要**: 売上・来客・メニュー・顧客分析の統合ダッシュボード。ドラッグ&ドロップのレイアウトカスタマイズ対応。

### 6.1 売上・予約分析

| API | 説明 |
|-----|------|
| `GET /api/dashboard/reservations/` | 予約数KPI・月次推移 |
| `GET /api/dashboard/sales/` | 売上額・日次推移 |
| `GET /api/dashboard/channel-sales/` | EC/POS/テーブル/予約別の売上分析 |
| `GET /api/dashboard/sales-heatmap/` | 曜日x時間帯の売上マトリクス |
| `GET /api/dashboard/aov-trend/` | 客単価(AOV)推移 |
| `GET /api/dashboard/forecast/` | 過去データに基づく売上予測 |
| `GET /api/dashboard/analysis-text/` | AI生成の売上分析レポート |

### 6.2 メニュー分析

| API | 説明 |
|-----|------|
| `GET /api/dashboard/menu-engineering/` | Star/Plow Horse/Puzzle/Dog分類 |
| `GET /api/dashboard/abc-analysis/` | 売上貢献度によるABC分類 |
| `GET /api/dashboard/basket/` | 同時購入パターン分析 |

### 6.3 顧客分析

| API | 説明 |
|-----|------|
| `GET /api/dashboard/cohort/` | 初回来店月ベースのリテンション分析 |
| `GET /api/dashboard/rfm/` | Recency/Frequency/Monetary スコアリング |
| `GET /api/dashboard/clv/` | 顧客生涯価値の推計 |
| `GET /api/dashboard/nps/` | Net Promoter Score集計 |
| `GET /api/dashboard/feedback/` | NPS + 各種評価の一覧 |

### 6.4 来客分析

| 機能 | URL/API | 説明 |
|------|---------|------|
| 来客分析ダッシュボード | `/admin/analytics/visitors/` | 時間帯別来客数・コンバージョン率 |
| `GET /api/analytics/visitors/` | PIRセンサーベースの来客集計 |
| `GET /api/analytics/heatmap/` | 曜日x時間帯の来客マトリクス |
| `GET /api/analytics/conversion/` | 来客→注文のコンバージョン率 |
| `GET /api/dashboard/visitor-forecast/` | 過去データに基づく来客予測 |

### 6.5 運営分析

| API | 説明 |
|-----|------|
| `GET /api/dashboard/staff-performance/` | スタッフ別の売上・予約数 |
| `GET /api/dashboard/shift-summary/` | シフト充足率・過不足 |
| `GET /api/dashboard/checkin-stats/` | チェックイン率・時間帯分布 |
| `GET /api/dashboard/kpi-scorecard/` | 総合KPIスコア |
| `GET /api/dashboard/insights/` | AI生成のビジネス改善提案 |
| `GET/PUT /api/dashboard/layout/` | ユーザーごとのレイアウト保存 |

**統合ダッシュボード画面**: `/admin/dashboard/sales/`

**主要モデル**: `DashboardLayout`, `BusinessInsight`, `CustomerFeedback`, `VisitorCount`, `VisitorAnalyticsConfig`

**ステータス**: 本番稼働中

---

## 7. LINE連携 (LINE Integration)

**概要**: LINE Messaging APIを使った予約、リマインダー、セグメント配信、チャットボット機能。

### 7.1 LINE認証・Webhook

| 機能 | URL | 説明 |
|------|-----|------|
| LINE Webhookエンドポイント | `/line/webhook/` | Follow/Unfollow/Message/Postback受信 |
| LINE認証 | `/line_enter/` | LINE OAuth2ログインフロー |
| タイマー | `/line_timer/<user_id>/` | LINE予約タイマー管理 |

### 7.2 LINE管理機能

| 機能 | URL | 説明 |
|------|-----|------|
| セグメント配信 | `/admin/line/segment/` | 顧客セグメント（新規/リピーター/VIP/休眠）別配信 |
| セグメント送信 | `/admin/line/segment/send/` | セグメント別メッセージ送信実行 |
| 仮予約確認 | `/admin/line/pending/` | LINE経由の仮予約承認/却下 |

### 7.3 自動機能（Celery Beat）

| タスク | スケジュール | 説明 |
|--------|-------------|------|
| 前日リマインダー | 毎日18:00 | 翌日予約者にLINEリマインダー送信 |
| 当日リマインダー | 30分ごと | 2時間前リマインダー送信 |
| セグメント再計算 | 毎日04:30 | 来店回数・金額ベースのセグメント更新 |
| チャットボット | 常時(Webhook) | LINE上での会話型予約(状態機械) |

**フィーチャーフラグ**: `line_chatbot_enabled`, `line_reminder_enabled`, `line_segment_enabled`

**主要モデル**: `LineCustomer`, `LineMessageLog`, `Timer`

**ステータス**: 本番稼働中（各機能はフィーチャーフラグで個別制御）

---

## 8. EC注文管理 (EC Order Management)

**概要**: オンラインショップ（ECサイト）機能。商品閲覧、カート、Coiney決済、発送管理まで。

### 8.1 顧客向けEC

| 機能 | URL | 説明 |
|------|-----|------|
| ショップ一覧 | `/shop/` | EC商品一覧（カテゴリ別・多言語対応） |
| カート | `/shop/cart/` | カート表示・数量変更 |
| チェックアウト | `/shop/checkout/` | 購入者情報入力 |
| 注文確認 | `/shop/confirm/` | 注文内容確認画面 |
| 決済 | `/shop/order/<id>/payment/` | Coiney決済フロー |
| 完了 | `/shop/order/<id>/complete/` | 注文完了・確認メール送信 |
| カートAPI | `POST /api/shop/cart/{add\|update\|remove}/` | カート操作 |

### 8.2 EC管理

| 機能 | URL/API | 説明 |
|------|---------|------|
| EC注文ダッシュボード | `/admin/ec/orders/` | 注文一覧・ステータス管理 |
| EC注文API | `GET /api/ec/orders/` | 注文リスト取得 |
| 発送更新API | `PATCH /api/ec/orders/<id>/shipping/` | 発送ステータス・追跡番号更新 |

**主要モデル**: `Order`, `OrderItem`, `ECProduct`, `ECCategory`, `ShippingConfig`

**ステータス**: 本番稼働中

---

## 9. テーブル注文 (Table Ordering)

**概要**: QRコードスキャンによるセルフオーダリングシステム。

| 機能 | URL | 説明 |
|------|-----|------|
| テーブルメニュー | `/t/<table_id>/` | QRスキャン後のメニュー画面 |
| テーブルカート | `/t/<table_id>/cart/` | 注文かご |
| テーブル注文 | `/t/<table_id>/order/` | 注文送信 |
| 注文履歴 | `/t/<table_id>/history/` | テーブルの注文履歴 |
| 会計 | `/t/<table_id>/checkout/` | テーブル会計 |
| カート操作API | `POST /api/table/<table_id>/cart/{add\|update\|remove}/` | テーブルカートAPI |
| 注文作成API | `POST /api/table/<table_id>/order/create/` | 注文確定 |
| 注文状況API | `GET /api/table/<table_id>/orders/status/` | 注文状況取得 |

**主要モデル**: `TableSeat`, `Order`, `OrderItem`

**ステータス**: 本番稼働中

---

## 10. AI推薦 (AI Recommendations)

**概要**: scikit-learnベースの機械学習によるスタッフ最適配置推薦。

| 機能 | URL/API | 説明 |
|------|---------|------|
| AI推薦画面 | `/admin/ai/recommendation/` | 推薦結果の可視化・手動トレーニング |
| 推薦API | `GET /api/ai/recommendations/` | 日付・時間帯別の推薦スタッフ数 |
| モデル学習API | `POST /api/ai/train/` | ランダムフォレストモデルの学習実行 |
| モデルステータスAPI | `GET /api/ai/model-status/` | 学習済みモデルの精度・ステータス |

**主要モデル**: `StaffRecommendationModel`, `StaffRecommendationResult`

**ステータス**: 本番稼働中

---

## 11. IoTセンサー (IoT Sensors)

**概要**: Raspberry Pi Pico Wベースのマルチセンサーノード。ガス検知・照度・音・人感センサー・IRリモコン。

### 11.1 センサーモニタリング

| 機能 | URL | 説明 |
|------|-----|------|
| MQ-9グラフ | `/dashboard/mq9/` | CO/可燃ガスセンサーのリアルタイムグラフ（1.5日スクロール表示） |
| センサーダッシュボード | `/dashboard/sensors/` | 照度・音・PIR統合表示 |
| 管理者センサー画面 | `/admin/iot/sensors/` | 全デバイスのセンサー状況 |
| デバイスデバッグ | `/admin/debug/device/<id>/` | 個別デバイスの詳細ログ |
| IoTイベントAPI | `POST /api/iot/events/` | デバイスからのイベント受信（APIキー認証） |
| IoTコンフィグAPI | `GET /api/iot/config/` | デバイス設定・保留IRコマンド取得 |
| センサーデータAPI | `GET /api/iot/sensors/data/` | センサーデータ取得 |
| PIRイベントAPI | `GET /api/iot/sensors/pir-events/` | PIR（人感）イベント一覧 |
| IR送信API | `POST /api/iot/ir/send/` | 赤外線コマンド送信 |

### 11.2 自動制御

| 機能 | 説明 |
|------|------|
| 換気扇自動制御 | MQ-9閾値連動でSwitchBotスマートプラグ経由ON/OFF（クールダウン付き） |
| ガスアラート | 閾値超過時にメール + LINE通知 |
| 物件監視 | ガス漏れ/長期不在(3日)/デバイスオフライン(30分)自動検知 |

### 11.3 物件管理

| 機能 | URL | 説明 |
|------|-----|------|
| 物件一覧 | `/properties/` | 管理物件一覧 |
| 物件詳細 | `/properties/<id>/` | 設置デバイス・アラート状況 |
| 物件ステータスAPI | `GET /api/properties/<id>/status/` | リアルタイム状況 |
| アラート解決API | `POST /api/alerts/<id>/resolve/` | アラートを解決済みに |

**主要モデル**: `IoTDevice`, `IoTEvent`, `VentilationAutoControl`, `IRCode`, `Property`, `PropertyDevice`, `PropertyAlert`

**ステータス**: 本番稼働中

---

## 12. テーマ・ページビルダー (Theme & Page Builder)

**概要**: Shopify風のテーマカスタマイズとGrapesJSベースのビジュアルページビルダー。

### 12.1 テーマカスタマイズ

| 機能 | URL | 説明 |
|------|-----|------|
| テーマプレビュー | `/admin/theme/preview/<store_id>/` | リアルタイムプレビュー |
| テーマカスタマイザー | `/admin/theme/customizer/<store_id>/` | カラー・フォント・ロゴ・カスタムCSS |
| プリセットAPI | `GET /admin/theme/presets/` | 7プリセット（default/elegant/modern/natural/luxury/pop/japanese） |

### 12.2 ページレイアウトエディタ

| 機能 | URL | 説明 |
|------|-----|------|
| レイアウトエディタ | `/admin/page-layout/<store_id>/` | セクションのドラッグ&ドロップ並べ替え |

### 12.3 ページビルダー (GrapesJS)

| 機能 | URL | 説明 |
|------|-----|------|
| ページ一覧 | `/admin/pages/<store_id>/` | 作成したページの管理 |
| ページ新規作成 | `/admin/pages/<store_id>/new/` | テンプレートから新規作成 |
| ページ編集 | `/admin/pages/<store_id>/<page_id>/edit/` | GrapesJSビジュアルエディタ |
| ページ公開 | `/admin/pages/<store_id>/<page_id>/publish/` | 公開/非公開切替 |
| ページ複製 | `/admin/pages/<store_id>/<page_id>/duplicate/` | 既存ページをコピー |
| 画像アップロード | `/admin/pages/<store_id>/upload/` | ページ用画像アップロード |
| 保存済みブロック | `/admin/pages/<store_id>/blocks/` | 再利用可能なHTMLブロック管理 |
| 公開ページ | `/p/<store_id>/<slug>/` | カスタムページの公開表示 |

**主要モデル**: `StoreTheme`, `PageLayout`, `SectionSchema`, `CustomPage`, `PageTemplate`, `SavedBlock`

**ステータス**: 本番稼働中

---

## 13. SNS自動投稿 (Social Media Posting)

**概要**: X (Twitter) への自動/予約投稿。AI生成テキスト、LLM品質評価、ナレッジベース連携。

### 13.1 OAuth認証・下書き管理

| 機能 | URL | 説明 |
|------|-----|------|
| X連携 | `/admin/social/connect/x/` | X OAuth2認証フロー |
| 下書き一覧 | `/admin/social/drafts/` | AI生成下書きの管理 |
| 下書き編集 | `/admin/social/drafts/<id>/edit/` | 下書き内容の編集 |
| 即時投稿 | `/admin/social/drafts/<id>/post/` | 下書きを即時投稿 |
| 予約投稿 | `/admin/social/drafts/<id>/schedule/` | 日時指定で予約投稿 |
| AI生成 | `/admin/social/drafts/generate/` | ナレッジベースからAI下書き生成 |
| AI再生成 | `/admin/social/drafts/<id>/regenerate/` | 品質スコア付きで再生成 |

### 13.2 自動投稿（Celery Beat）

| タスク | スケジュール | 説明 |
|--------|-------------|------|
| 本日のスタッフ投稿 | 毎日09:30 | 当日出勤キャストの紹介投稿 |
| 週間スケジュール投稿 | 毎週月曜10:00 | 週間スケジュールの告知 |
| 下書き自動生成 | 毎日08:00 | AI下書きの自動生成+LLM Judge品質評価 |
| 予約投稿チェック | 5分ごと | 予約時刻到達の投稿を実行 |
| トークンリフレッシュ | 毎日03:30 | 期限切れ間近のOAuthトークン更新 |

**主要モデル**: `SocialAccount`, `PostTemplate`, `PostHistory`, `KnowledgeEntry`, `DraftPost`

**ステータス**: 本番稼働中

---

## 14. 多言語対応 (i18n)

**対応言語**: 日本語(ja), English(en), 繁體中文(zh-hant), 简体中文(zh-hans), 한국어(ko), Espanol(es), Portugues(pt)

- URLプレフィックス方式 + 言語スイッチャー(Cookie)
- `SiteSettings.forced_language` によるサイト言語固定
- `ProductTranslation` テーブルによる商品名・説明の多言語化
- `SiteSettings.staff_label_i18n` によるスタッフ呼称の多言語化
- 全1,366文字列の完全翻訳

**ステータス**: 本番稼働中（7言語100%翻訳完了）

---

## 15. HR・給与計算 (HR & Payroll)

- 雇用契約管理（正社員/パート/契約社員、時給/月給）
- 給与計算（残業1.25倍/深夜1.35倍/休日1.50倍の割増自動計算）
- 社会保険料自動計算（厚生年金/健康保険/雇用保険/介護保険）
- 全銀フォーマット振込データ出力
- スタッフ5段階評価（S/A/B/C/D、自動+手動）

**主要モデル**: `EmploymentContract`, `SalaryStructure`, `PayrollPeriod`, `PayrollEntry`, `PayrollDeduction`, `EvaluationCriteria`, `StaffEvaluation`

**ステータス**: 本番稼働中

---

## 16. CMS機能 (Content Management)

- お知らせ（`/news/`, `/news/<slug>/`）SEO対応スラッグURL、HTMLサニタイズ
- ヒーローバナースライダー（店舗/スタッフ/外部URLリンク対応）
- バナー広告（5つの配置位置指定）
- カスタムHTMLブロック（カードの上下・サイドバー）
- 外部リンク管理
- メディア掲載情報（URLから自動メタ情報取得）
- プライバシーポリシー/特商法表記（カスタムHTML対応）

**主要モデル**: `Notice`, `HeroBanner`, `BannerAd`, `HomepageCustomBlock`, `ExternalLink`, `Media`, `Company`, `SiteSettings`

**ステータス**: 本番稼働中

---

## 17. セキュリティ (Security)

- セキュリティ監査ミドルウェア（ログイン/API認証/権限拒否/レートリミット監視）
- レートリミット（同一IP 100req/60s で429返却）
- 日次セキュリティ監査（Django設定・認証情報・エンドポイント・依存関係チェック）
- セキュリティログクリーンアップ（90日超自動削除）
- AWSコストモニタリング（EC2/S3/EBS/EIP）
- 暗号化フィールド（LINE user ID, IoTパスワード, 決済APIキー, SwitchBotトークン）
- メンテナンスモード（管理者以外に503返却）
- エラー報告システム（スクリーンショット対応）
- 5xxサーバーエラー時の自動通知

**主要モデル**: `SecurityAudit`, `SecurityLog`, `CostReport`, `ErrorReport`

**ステータス**: 本番稼働中

---

## 18. 外部埋め込み (Embed / WordPress連携)

- iframe埋め込み用予約カレンダー（`/embed/booking/<store_id>/`）
- iframe埋め込み用シフト表示（`/embed/shift/<store_id>/`）
- iframe内で完結する予約フロー（embed_token方式）
- WordPressプラグイン（ショートコード `[timebaibai]` 対応）
- ドメイン制限（`Store.embed_allowed_domains`）

**ステータス**: 本番稼働中

---

## 19. バックアップ (Backup)

- 自動バックアップ（毎分/毎時/毎日の間隔設定）
- S3アップロード（boto3）
- ローカル保持ポリシー（デフォルト30件）
- デモデータ除外オプション
- LINE Notify完了/失敗通知

**主要モデル**: `BackupConfig`, `BackupHistory`

**ステータス**: 本番稼働中

---

## 20. サイト設定・デモモード

### SiteSettings（シングルトン）

カード表示/サイドバー表示/SNS連携/スタッフ呼称/AIチャット/デモモード/LINE機能フラグ/管理サイドバー機能ON/OFF(20項目)/メンテナンスモード/埋め込み/無料予約モード/法定ページ/通知設定

### デモモード

- `demo_mode_enabled` フラグ
- 主要8モデルの `is_demo` フィールドで実データと分離
- 30分毎にデモデータ自動生成
- ダッシュボードにDEMOバナー表示

### サイトセットアップウィザード

初期設定を対話形式で完了（`/admin/site-wizard/<store_id>/`）

**ステータス**: 本番稼働中

---

## 21. マイページ (Staff My Page)

- マイページダッシュボード（`/mypage/`）
- プロフィール編集（`/mypage/<id>/profile/`）
- 予約カレンダー・日付詳細・予約詳細
- 予約削除・休日追加

**ステータス**: 本番稼働中

---

## 22. 管理画面カスタマイズ

- django-jazzmin ベースの管理画面UI
- ロール別サイドバーメニュー制御（developer/owner/manager/staff）
- 管理画面テーマ（カラー・ヘッダー画像カスタマイズ）
- デバッグパネル（`/admin/debug/`）
- ログレベルランタイム制御（`POST /api/debug/log-level/`）
- サイドバースクロール位置の自動保持

**ステータス**: 本番稼働中
