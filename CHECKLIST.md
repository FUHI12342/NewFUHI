# NewFUHI 改修チェックリスト

> 最終更新: 2026-03-17

## 完了済み

- [x] POS レシート/領収書ページ (`/admin/pos/receipt/<receipt_number>/`)
  - POSReceiptView 新規作成
  - 印刷用テンプレート (80mm サーマルプリンター対応)
  - URL登録
  - POS画面 `alert()` → `window.open()` に変更
  - 管理画面 POSTransactionAdmin にレシートリンク追加
  - テスト 6件追加 (全27件 pass)

- [x] サイドバーメニュー表示修正 (AdminSidebarMixin 追加)
  - `InventoryDashboardView` — 修正済み
  - `StockInFormView` — 修正済み
  - `IoTDeviceDebugView` — 修正済み

- [x] Schedule 管理画面ラベル変更
  - `占いスタッフ` → `キャスト` (models.py + locale)
  - `customer_name` に verbose_name `予約者名` 追加

- [x] 予約一覧「予約を追加」ボタンのデザイン統一
  - カスタムテンプレートのオーバーライド削除 → Jazzmin デフォルトボタンに統一

- [x] スタッフ勤務実績ダッシュボード (`/admin/attendance/performance/`)
  - サービス層: `booking/services/attendance_summary.py`
  - ビュー: `booking/views_performance_dashboard.py`
  - テンプレート: 表/グラフ切り替え (Alpine.js + Chart.js)
  - API: `/api/attendance/performance/` (年月・店舗・スタッフ絞り込み)
  - テスト 19件追加

- [x] オンラインショップ管理画面 (EC注文管理・発送管理)
  - Order モデルに顧客フィールド追加 (customer_name/email/phone/address)
  - 発送管理フィールド追加 (shipping_status/tracking_number/shipped_at/shipping_note)
  - ShopCheckoutView データロス修正 (email/address が未保存だった問題)
  - EC注文管理ダッシュボード (`/admin/ec/orders/`) — Alpine.js + Tailwind
  - EC注文一覧API (`/api/ec/orders/`) + 発送ステータス更新API
  - OrderAdmin に発送情報・顧客情報セクション追加 + 一括発送済みアクション
  - サイドバー EC グループにダッシュボードリンク追加
  - テスト 16件追加 (全1150件 pass)

## 未着手


