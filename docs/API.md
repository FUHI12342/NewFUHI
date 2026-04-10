# API仕様書 (API Reference)

最終更新: 2026-04-09

すべてのAPIエンドポイントは `/api/` プレフィックス配下に配置（i18n言語プレフィックスなし）。
認証が必要なエンドポイントは Django セッション認証（Cookie `sessionid`）を使用。

---

## 目次

1. [IoT API](#1-iot-api)
2. [予約・タイミング API](#2-予約タイミング-api)
3. [メニュー・注文 API](#3-メニュー注文-api)
4. [在庫 API](#4-在庫-api)
5. [テーブル注文 API](#5-テーブル注文-api)
6. [POS API](#6-pos-api)
7. [勤怠 API](#7-勤怠-api)
8. [シフト API](#8-シフト-api)
9. [ダッシュボード・分析 API](#9-ダッシュボード分析-api)
10. [来客分析 API](#10-来客分析-api)
11. [EC注文管理 API](#11-ec注文管理-api)
12. [AI推薦 API](#12-ai推薦-api)
13. [ECカート API](#13-ecカート-api)
14. [QRチェックイン API](#14-qrチェックイン-api)
15. [物件監視 API](#15-物件監視-api)
16. [デバッグ API](#16-デバッグ-api)
17. [LINE予約管理 API](#17-line予約管理-api)
18. [埋め込み URL](#18-埋め込み-url)
19. [SNS OAuth・下書き](#19-sns-oauth下書き)
20. [Webhook](#20-webhook)

---

## 1. IoT API

### POST /api/iot/events/
IoTデバイスからのイベント受信。APIキー認証（`X-API-Key` ヘッダー）。

| 項目 | 値 |
|------|-----|
| 認証 | APIキー（IoTDevice.api_key_hash で検証） |
| Content-Type | application/json |

**リクエストボディ例:**
```json
{
  "device_id": "pico-001",
  "mq9_value": 450,
  "light_level": 800,
  "sound_level": 65,
  "pir_triggered": true
}
```

### GET /api/iot/config/
デバイス設定・保留IRコマンド取得。

| 項目 | 値 |
|------|-----|
| 認証 | APIキー |
| パラメータ | `device_id` (query) |

### GET /api/iot/sensors/data/
センサーデータ取得（グラフ表示用）。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証 |
| パラメータ | `device_id`, `hours` (default: 36) |

### GET /api/iot/sensors/pir-events/
PIR（人感）イベント一覧取得。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証 |

### GET /api/iot/sensors/pir-status/
PIRセンサーの現在状態。

### POST /api/iot/ir/send/
赤外線コマンド送信（IoTデバイスの pending IR commands に追加）。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証（管理者） |
| ボディ | `device_id`, `ir_code_id` |

---

## 2. 予約・タイミング API

### GET /api/endTime
予約終了時刻を取得。

### GET /api/currentTime
サーバー現在時刻を取得。

### GET /api/reservation/{pk}/
予約詳細を取得。

### GET /api/reservation_times/{pk}/
予約の時間帯情報を取得。

---

## 3. メニュー・注文 API

### GET /api/menu
商品メニューJSON（公開）。

| 項目 | 値 |
|------|-----|
| 認証 | 不要 |
| パラメータ | `store_id` (query) |

**レスポンス例:**
```json
{
  "categories": [
    {
      "id": 1,
      "name": "ドリンク",
      "products": [
        {"id": 1, "name": "コーヒー", "price": 500, "stock": 50}
      ]
    }
  ]
}
```

### GET /api/products/alternatives/
欠品時の代替商品レコメンド。

| 項目 | 値 |
|------|-----|
| 認証 | 不要 |
| パラメータ | `product_id` (query) |

### POST /api/orders/create/
注文作成。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証 |
| ボディ | `store_id`, `items[]`, `order_type` |

### GET /api/orders/status/
注文ステータス取得。

### PATCH /api/staff/orders/items/{item_id}/status/
注文アイテムのステータス更新（ORDERED → PREPARING → SERVED）。

| 項目 | 値 |
|------|-----|
| 認証 | スタッフ認証 |
| ボディ | `status` |

### POST /api/staff/orders/served/
注文を配膳済みにマーク。

---

## 4. 在庫 API

### POST /api/stock/inbound/apply/
在庫入庫処理。`select_for_update` による原子的更新。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証 |
| ボディ | `product_id`, `quantity`, `note` |

---

## 5. テーブル注文 API

QRコードスキャン後のセルフオーダリング用API。テーブルUUIDで識別。

### POST /api/table/{table_id}/cart/add/
テーブルカートにアイテム追加。

| 項目 | 値 |
|------|-----|
| 認証 | 不要（テーブルUUID認証） |
| ボディ | `product_id`, `quantity` |

### POST /api/table/{table_id}/cart/update/
テーブルカートのアイテム数量更新。

### POST /api/table/{table_id}/cart/remove/
テーブルカートからアイテム削除。

### POST /api/table/{table_id}/order/create/
テーブル注文確定。

### GET /api/table/{table_id}/orders/status/
テーブルの注文状況取得。

---

## 6. POS API

### POST /api/pos/orders/
POS注文作成。

| 項目 | 値 |
|------|-----|
| 認証 | スタッフ認証 |
| ボディ | `store_id`, `items[]` |

### POST /api/pos/order-items/
注文アイテム追加。

### GET /api/pos/order-items/{pk}/
注文アイテム詳細取得。

### POST /api/pos/checkout/
POS決済処理。

| 項目 | 値 |
|------|-----|
| 認証 | スタッフ認証 |
| ボディ | `order_id`, `payment_method`, `amount` |

**決済方法:** `cash`, `coiney`, `paypay`, `ic`, `other`

### PATCH /api/pos/order-item/{pk}/status/
キッチン注文アイテムのステータス変更。

| ステータス遷移 | 説明 |
|---------------|------|
| ORDERED → PREPARING | 調理開始 |
| PREPARING → SERVED | 配膳完了 |

### GET /api/pos/kitchen-orders/
キッチン注文のHTML部分更新（HTMX用）。

### POST /api/pos/order/{pk}/complete/
注文完了（全アイテム配膳済み）。

### POST /api/pos/order/{pk}/uncomplete/
注文完了を取り消し（SERVEDステータスに戻す）。

---

## 7. 勤怠 API

### POST /api/attendance/stamp/
TOTP認証付き打刻。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証 |
| ボディ | `totp_code`, `stamp_type`, `latitude`, `longitude` |

**打刻種別:** `clock_in`, `clock_out`, `break_start`, `break_end`

### POST /api/attendance/pin-stamp/
PIN認証打刻。

| 項目 | 値 |
|------|-----|
| 認証 | 不要（PIN認証） |
| ボディ | `pin`, `stamp_type` |

### POST /api/attendance/qr-stamp/
QRスキャン打刻（ログイン不要、TOTP+PIN認証）。

| 項目 | 値 |
|------|-----|
| 認証 | 不要（TOTP+PIN認証） |
| ボディ | `totp_code`, `pin`, `stamp_type` |

### POST /api/attendance/manual-stamp/
管理者による代理打刻。

| 項目 | 値 |
|------|-----|
| 認証 | 管理者認証 |
| ボディ | `staff_id`, `stamp_type`, `timestamp` |

### POST /api/attendance/totp/refresh/
TOTP QRコードの再生成。

### GET /api/attendance/day-status/
当日の打刻ステータス取得。

### GET /api/attendance/day-status-html/
当日の打刻ステータスHTML部分更新。

### GET /api/attendance/performance/
期間指定の勤務実績データ。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証 |
| パラメータ | `start_date`, `end_date`, `staff_id` (optional) |

---

## 8. シフト API

すべて `/api/shift/` プレフィックス配下。namespace: `shift_api`。

### GET /api/shift/week-grid/
週間シフトグリッドデータ。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証 |
| パラメータ | `store_id`, `date` (YYYY-MM-DD, 週の基準日) |

### GET /api/shift/detail/{pk}/
シフトセル詳細情報。

### POST /api/shift/assignments/
シフト割当作成。

| 項目 | 値 |
|------|-----|
| 認証 | マネージャー認証 |
| ボディ | `staff_id`, `store_id`, `date`, `start_time`, `end_time`, `period_id` |

### PUT /api/shift/assignments/{pk}/
シフト割当更新。

### DELETE /api/shift/assignments/{pk}/
シフト割当削除。

### POST /api/shift/bulk-assign/
複数シフトを一括作成。

| 項目 | 値 |
|------|-----|
| 認証 | マネージャー認証 |
| ボディ | `assignments[]` (配列) |

### POST /api/shift/auto-schedule/
カバレッジベースの自動シフト割当。

| 項目 | 値 |
|------|-----|
| 認証 | マネージャー認証 |
| ボディ | `period_id`, `store_id` |

### POST /api/shift/apply-template/
定型シフトテンプレートをワンタップ適用。

| 項目 | 値 |
|------|-----|
| 認証 | マネージャー認証 |
| ボディ | `template_id`, `period_id`, `date` |

### GET /api/shift/templates/
シフトテンプレート一覧。

### POST /api/shift/templates/
シフトテンプレート作成。

### PUT /api/shift/templates/{pk}/
シフトテンプレート更新。

### DELETE /api/shift/templates/{pk}/
シフトテンプレート削除。

### POST /api/shift/publish/
確定シフトをスタッフへ通知。

| 項目 | 値 |
|------|-----|
| 認証 | マネージャー認証 |
| ボディ | `period_id` |

### POST /api/shift/revoke/
公開済みシフトを撤回。

### POST /api/shift/reopen/
不足枠の再募集。

### GET /api/shift/change-logs/
シフト変更の監査証跡。

### POST /api/shift/periods/
シフト募集期間の作成。

| 項目 | 値 |
|------|-----|
| 認証 | マネージャー認証 |
| ボディ | `store_id`, `start_date`, `end_date`, `deadline` |

### PUT /api/shift/periods/{pk}/
シフト募集期間の更新。

### DELETE /api/shift/periods/{pk}/
シフト募集期間の削除。

### GET/POST /api/shift/closed-dates/
店舗休業日の管理。

### GET /api/shift/my-requests/
自分のシフト希望一覧。

### PUT /api/shift/my-requests/{pk}/
シフト希望更新。

### DELETE /api/shift/my-requests/{pk}/
シフト希望削除。

### POST /api/shift/requests/{period_id}/bulk/
複数日分の希望を一括送信。

| 項目 | 値 |
|------|-----|
| 認証 | スタッフ認証 |
| ボディ | `requests[]` (日付・種別の配列) |

### POST /api/shift/requests/{period_id}/copy-week/
先週のパターンをコピー。

### GET /api/shift/vacancies/
シフト不足枠リスト。

### POST /api/shift/vacancies/{pk}/apply/
シフト不足枠への応募。

### POST /api/shift/swap-requests/
交代/カバー/欠勤の申請。

| 項目 | 値 |
|------|-----|
| 認証 | スタッフ認証 |
| ボディ | `type` (swap/cover/absence), `assignment_id`, `reason` |

### PUT /api/shift/swap-requests/{pk}/
交代申請の更新。

### GET /api/shift/staffing/
必要人数設定の取得。

### POST /api/shift/staffing/
必要人数設定の作成・更新。

### GET/POST /api/shift/staffing/overrides/
日付指定オーバーライドの管理。

### PUT/DELETE /api/shift/staffing/overrides/{pk}/
日付指定オーバーライドの更新・削除。

---

## 9. ダッシュボード・分析 API

すべて `/api/dashboard/` プレフィックス配下。セッション認証必須。

### GET/PUT /api/dashboard/layout/
ユーザーごとのダッシュボードレイアウト保存・取得。

### 売上・予約分析

| エンドポイント | 説明 |
|---------------|------|
| `GET /api/dashboard/reservations/` | 予約数KPI・月次推移 |
| `GET /api/dashboard/sales/` | 売上額・日次推移 |
| `GET /api/dashboard/channel-sales/` | EC/POS/テーブル/予約別の売上分析 |
| `GET /api/dashboard/sales-heatmap/` | 曜日 x 時間帯の売上マトリクス |
| `GET /api/dashboard/aov-trend/` | 客単価(AOV)推移 |
| `GET /api/dashboard/forecast/` | 過去データに基づく売上予測 |
| `GET /api/dashboard/analysis-text/` | AI生成の売上分析レポート |

**共通パラメータ:** `store_id`, `start_date`, `end_date`

### メニュー分析

| エンドポイント | 説明 |
|---------------|------|
| `GET /api/dashboard/menu-engineering/` | Star/Plow Horse/Puzzle/Dog分類 |
| `GET /api/dashboard/abc-analysis/` | 売上貢献度によるABC分類 |
| `GET /api/dashboard/basket/` | 同時購入パターン分析 |

### 顧客分析

| エンドポイント | 説明 |
|---------------|------|
| `GET /api/dashboard/cohort/` | 初回来店月ベースのリテンション分析 |
| `GET /api/dashboard/rfm/` | Recency/Frequency/Monetary スコアリング |
| `GET /api/dashboard/clv/` | 顧客生涯価値の推計 |
| `GET /api/dashboard/nps/` | Net Promoter Score集計 |
| `GET /api/dashboard/feedback/` | NPS + 各種評価の一覧 |

### 運営分析

| エンドポイント | 説明 |
|---------------|------|
| `GET /api/dashboard/staff-performance/` | スタッフ別の売上・予約数 |
| `GET /api/dashboard/shift-summary/` | シフト充足率・過不足 |
| `GET /api/dashboard/checkin-stats/` | チェックイン率・時間帯分布 |
| `GET /api/dashboard/kpi-scorecard/` | 総合KPIスコア |
| `GET /api/dashboard/insights/` | AI生成のビジネス改善提案 |
| `GET /api/dashboard/visitor-forecast/` | 過去データに基づく来客予測 |
| `GET /api/dashboard/low-stock/` | 閾値以下の在庫リスト |
| `GET /api/dashboard/auto-order/` | 在庫と売上データに基づく発注提案 |
| `GET /api/dashboard/external-data/` | 外部データ（天気, Google Business Profile） |

---

## 10. 来客分析 API

### GET /api/analytics/visitors/
PIRセンサーベースの来客集計。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証 |
| パラメータ | `store_id`, `start_date`, `end_date` |

### GET /api/analytics/heatmap/
曜日 x 時間帯の来客マトリクス。

### GET /api/analytics/conversion/
来客→注文のコンバージョン率。

---

## 11. EC注文管理 API

### GET /api/ec/orders/
EC注文リスト取得。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証（管理者） |
| パラメータ | `status`, `start_date`, `end_date` |

### PATCH /api/ec/orders/{pk}/shipping/
発送ステータス・追跡番号更新。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証（管理者） |
| ボディ | `shipping_status`, `tracking_number` |

---

## 12. AI推薦 API

### GET /api/ai/recommendations/
日付・時間帯別の推薦スタッフ数。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証 |
| パラメータ | `store_id`, `date` |

### POST /api/ai/train/
ランダムフォレストモデルの学習実行。

| 項目 | 値 |
|------|-----|
| 認証 | 管理者認証 |
| ボディ | `store_id` |

### GET /api/ai/model-status/
学習済みモデルの精度・ステータス。

---

## 13. ECカート API

### POST /api/shop/cart/add/
ECカートにアイテム追加。

| 項目 | 値 |
|------|-----|
| 認証 | 不要（セッションベースカート） |
| ボディ | `product_id`, `quantity` |

### POST /api/shop/cart/update/
ECカートのアイテム数量更新。

### POST /api/shop/cart/remove/
ECカートからアイテム削除。

---

## 14. QRチェックイン API

### POST /api/checkin/
QRコード / バックアップコードによるチェックイン。

| 項目 | 値 |
|------|-----|
| 認証 | 不要（予約番号認証） |
| ボディ | `reservation_number` or `backup_code` |

---

## 15. 物件監視 API

### GET /api/properties/{pk}/status/
物件のリアルタイムステータス（設置デバイス・アラート状況）。

### POST /api/alerts/{pk}/resolve/
アラートを解決済みにマーク。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証 |

---

## 16. デバッグ API

### GET /api/debug/panel/
デバッグパネルデータ取得。

| 項目 | 値 |
|------|-----|
| 認証 | 管理者認証 |

### POST /api/debug/log-level/
ログレベルのランタイム変更。

| 項目 | 値 |
|------|-----|
| 認証 | 管理者認証 |
| ボディ | `logger_name`, `level` |

---

## 17. LINE予約管理 API

### POST /api/line/reservations/{pk}/confirm/
仮予約を確定。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証（管理者） |

### POST /api/line/reservations/{pk}/reject/
仮予約を却下。

| 項目 | 値 |
|------|-----|
| 認証 | セッション認証（管理者） |
| ボディ | `rejection_reason` |

---

## 18. 埋め込み URL

i18nプレフィックスなし。iframe内で完結する予約フロー。namespace: `embed`。

| URL | ビュー | 説明 |
|-----|--------|------|
| `/embed/demo/` | EmbedDemoView | デモ表示 |
| `/embed/booking/{store_id}/` | EmbedBookingView | 予約カレンダー埋め込み |
| `/embed/shift/{store_id}/` | EmbedShiftView | シフト表示埋め込み |
| `/embed/calendar/{store_id}/{pk}/` | EmbedStaffCalendarView | スタッフカレンダー |
| `/embed/calendar/{store_id}/{pk}/{year}/{month}/{day}/` | EmbedStaffCalendarView | 日付指定カレンダー |
| `/embed/prebooking/{store_id}/{pk}/{year}/{month}/{day}/{hour}/` | EmbedPreBookingView | 仮予約 |
| `/embed/prebooking/{store_id}/{pk}/{year}/{month}/{day}/{hour}/{minute}/` | EmbedPreBookingView | 仮予約（分指定） |
| `/embed/channel-choice/{embed_token}/` | EmbedChannelChoiceView | 予約経路選択 |
| `/embed/email/{embed_token}/` | EmbedEmailBookingView | メール予約 |
| `/embed/email/{embed_token}/verify/` | EmbedEmailVerifyView | メール認証 |
| `/embed/line/{embed_token}/` | EmbedLineRedirectView | LINEリダイレクト |

---

## 19. SNS OAuth・下書き

i18n_patterns 内。すべて `/admin/social/` プレフィックス。管理者認証必須。

| URL | メソッド | 説明 |
|-----|---------|------|
| `/admin/social/connect/x/` | GET | X OAuth2認証フロー開始 |
| `/admin/social/callback/x/` | GET | X OAuth2コールバック |
| `/admin/social/drafts/` | GET | 下書き一覧 |
| `/admin/social/drafts/{pk}/edit/` | GET/POST | 下書き編集 |
| `/admin/social/drafts/{pk}/post/` | POST | 即時投稿 |
| `/admin/social/drafts/{pk}/schedule/` | POST | 予約投稿（日時指定） |
| `/admin/social/drafts/generate/` | POST | AI下書き生成 |
| `/admin/social/drafts/{pk}/regenerate/` | POST | AI再生成（品質スコア付き） |

---

## 20. Webhook

### POST /line/webhook/
LINE Messaging API Webhook受信。

| 項目 | 値 |
|------|-----|
| 認証 | LINE署名検証（X-Line-Signature） |
| 対応イベント | Follow, Unfollow, Message, Postback |

### POST /coiney_webhook/{orderId}/
Coiney決済Webhook。

| 項目 | 値 |
|------|-----|
| 認証 | Coiney署名検証 |

---

## テーブル注文 画面URL

namespace: `table`。QRコードスキャン後のセルフオーダリング画面。

| URL | ビュー | 説明 |
|-----|--------|------|
| `/t/{table_id}/` | TableMenuView | テーブルメニュー |
| `/t/{table_id}/cart/` | TableCartView | テーブルカート |
| `/t/{table_id}/order/` | TableOrderView | テーブル注文送信 |
| `/t/{table_id}/history/` | TableOrderHistoryView | 注文履歴 |
| `/t/{table_id}/checkout/` | TableCheckoutView | テーブル会計 |

---

## 共通仕様

### 認証方式

| 方式 | 用途 |
|------|------|
| Django セッション (Cookie) | 管理画面・スタッフAPI |
| APIキー (X-API-Key) | IoTデバイス通信 |
| TOTP + PIN | 勤怠打刻 |
| 予約番号 / embed_token | 公開予約フロー |
| LINE署名 (X-Line-Signature) | LINE Webhook |
| テーブルUUID | テーブル注文 |

### レスポンス形式

成功時:
```json
{"status": "ok", "data": {...}}
```

エラー時:
```json
{"status": "error", "message": "エラー内容"}
```

### レートリミット

- 同一IPから60秒以内に100リクエスト超過で `429 Too Many Requests`
- `Retry-After` ヘッダーに待機秒数を返却
- SecurityAuditMiddleware で監視・記録

### CSRF

- APIエンドポイント: Django CSRF保護が適用（セッション認証時）
- IoT API: APIキー認証のため CSRF免除
- LINE Webhook: 署名検証のため CSRF免除
- 公開キャンセルビュー: LINE in-appブラウザ対応のため CSRF免除
