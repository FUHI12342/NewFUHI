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

- [x] シフトカレンダー管理メニュー統合
  - 管理メニュードロップダウン追加（募集期間・希望・確定・テンプレート・公開履歴・休業日）
  - テンプレート管理モーダル（CRUD、Alpine.js、既存API利用）
  - スタッフViewでは管理メニュー非表示
  - テスト 7件追加

- [x] 公開済みシフト撤回・個別修正（ハイブリッド方式）
  - ShiftChangeLog 新規モデル（個別変更の監査証跡）
  - ShiftPublishHistory に action(publish/revoke) + reason フィールド追加
  - `revoke_published_shifts()` サービス: approved→scheduled 戻し、Schedule キャンセル、is_synced リセット
  - `revise_assignment()` サービス: 個別修正 + 変更ログ + Schedule 更新
  - ShiftRevokeAPIView (`POST /api/shift/revoke/`) 新規
  - ShiftAssignmentAPIView.put: approved 期間で変更ログ自動作成 + 差分通知
  - 撤回通知 `notify_shift_revoked()` + 個別修正通知 `notify_shift_revised()`
  - カレンダーUI: 撤回ボタン + 確認ダイアログ（理由入力）、個別修正理由ダイアログ
  - 公開履歴に公開/撤回の種別表示 + 理由表示
  - ShiftChangeLogAdmin（読み取り専用）
  - テスト 14件追加（全1170件 pass）

- [x] スタッフ/キャスト分離 + マイページ + 管理メニュー
  - **C: スタッフ管理メニュー追加**
    - サイドバー `staff_manage` グループ新設（`cast` → `staff_manage` に統合）
    - manager: キャスト一覧・店舗スタッフ一覧・勤怠実績・スタッフ新規追加
    - staff: マイページリンクのみ
    - StaffAdmin に `list_filter` (staff_type, is_store_manager, store) 追加
  - **A: マイページプロフィール編集**
    - `MyPageProfile` ビュー (`/mypage/<pk>/profile/`) 新規
    - `OnlyStaffMixin` で本人のみ編集可能
    - staff_type 対応: キャストは price/introduction 編集可、店舗スタッフは非表示
    - MyPage トップにプロフィール/カレンダーボタン追加、staff_type バッジ表示
  - **B: シフトカレンダー staff_type フィルタ**
    - 週ナビゲーションに「全員/キャスト/スタッフ」フィルタボタン追加
    - `_render_week_grid` に `staff_type_filter` 引数追加
    - グリッドとスタッフリストをフィルタリング
  - **D: staff_type 活用改善**
    - MyPage: キャストのみ「直近の予約」セクション表示（店舗スタッフは非表示）
    - `has_cast_role` コンテキスト変数追加
  - テスト 15件追加（全1185件 pass）

## 未着手


