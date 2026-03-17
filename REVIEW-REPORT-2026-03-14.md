# Timebaibai (NewFUHI) 変更レポート — 2026-03-14

**実施日:** 2026-03-14
**対象:** ~/NewFUHI/ Django プロジェクト
**ブランチ:** dev

---

## エグゼクティブサマリー

| カテゴリ | 前回 (03-13) | 今回 (03-14) | 変化 |
|---------|-------------|-------------|------|
| テスト数 | 769 pass | 817 pass | +48 |
| カバレッジ | 60% | 62% | +2% |
| models.py | 89% | 91% | +2% |
| views.py | 65% | 67% | +2% |
| urls.py | — | 100% | — |
| tasks.py | — | 88% | — |

---

## 1. 新機能: 店舗アクセス情報

### 1.1 Store モデル変更

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `map_url` | CharField(max_length=500) | Google Maps リンク |
| `access_info` | TextField | 道順テキスト（改行対応） |

- マイグレーション: `0066_store_access_info_store_map_url.py`
- 管理画面: 自動表示（ModelAdmin デフォルト動作）

### 1.2 決済完了メッセージ

`booking/views.py` の `process_payment` を更新:

- `_build_access_lines(store)` ヘルパー関数を追加
- `Schedule.objects.get()` に `.select_related('staff__store')` を追加（N+1回避）
- LINE 顧客メッセージ末尾にアクセス情報を追加
- メール通知本文末尾にアクセス情報を追加
- アクセス情報未設定の場合はセクション自体を非表示

### 1.3 公開アクセスページ

| 項目 | 内容 |
|------|------|
| URL | `/store/<int:pk>/access/` |
| ビュー | `StoreAccessView` (DetailView) |
| テンプレート | `booking/templates/booking/store_access.html` |

表示内容: 店舗名、住所、最寄り駅、営業時間、定休日、アクセス情報、Google Maps リンクボタン

### 1.4 店舗一覧リンク

`booking/templates/booking/store_list.html` に「アクセス情報」ボタンを追加。

---

## 2. UI 改善

### 2.1 メインページ: モバイル 2×2 グリッド

**ファイル:** `booking/templates/booking/booking_top.html`

| 要素 | モバイル | デスクトップ |
|------|---------|------------|
| グリッド | 2列×2行 | 4列×1行 |
| アイコン | h-20, w-10 | h-40, w-16 |
| パディング | p-3 | p-5 |
| タイトル | text-sm | text-lg |
| 説明文 | 非表示 (hidden) | 表示 (md:block) |
| フッター | text-[10px] | text-xs |

### 2.2 ヘッダーログインボタン非表示

**ファイル:** `booking/templates/booking/base.html`

- デスクトップ: `{% else %}` ブロック（未ログイン時のログインボタン）を削除
- モバイル: 未ログイン時のログインリンクを削除
- フッター: ログインリンクは既存のまま（フッターから管理画面にアクセス可能）

### 2.3 管理画面: モバイルサイト名表示

**ファイル:** `static/css/jazzmin_overrides.css`

```css
@media (max-width: 991.98px) {
    .main-header .navbar-brand { display: flex !important; ... }
    .brand-text { display: inline !important; visibility: visible !important; }
}
```

Jazzmin はモバイルでサイドバー折りたたみ時に `.brand-text` を非表示にするため、CSS で上書き。

---

## 3. テスト追加

### 3.1 tests/test_admin_roles.py (39テスト)

| テストクラス | テスト数 | 内容 |
|------------|---------|------|
| TestAdminTopAccess | 6 | 全ロール `/admin/` アクセス |
| TestStaffChangelistAccess | 5 | スタッフ一覧のロール別アクセス |
| TestStoreAdminAccess | 4 | 店舗管理のロール別アクセス |
| TestPayrollAdminAccess | 2 | 給与管理のアクセス制限 |
| TestDebugPanelAccess | 5 | デバッグパネルのアクセス制限 |
| TestFortuneTellerVsStoreStaff | 6 | 両staff_typeの同等権限確認 |
| TestManagerCRUDPermissions | 3 | 店長のCRUD権限確認 |
| TestStoreAccessView | 3 | 公開アクセスページ |
| TestGetUserRole | 8 | ロール判定ロジック |

### 3.2 tests/test_payment_access_info.py (9テスト)

| テストクラス | テスト数 | 内容 |
|------------|---------|------|
| TestBuildAccessLines | 5 | `_build_access_lines` 単体テスト |
| TestProcessPaymentAccessInfo | 3 | LINE/メール通知のアクセス情報 |

---

## 4. ロール別権限分析

### 4.1 ロール解決 (`get_user_role`)

優先順位: `superuser` > `developer` > `owner` > `manager` > `staff`

- `staff_type='fortune_teller'` → `'staff'`
- `staff_type='store_staff'` → `'staff'`
- `is_store_manager=True` → `'manager'`
- `is_owner=True` → `'owner'`
- `is_developer=True` → `'developer'`

### 4.2 重要な発見

1. **`staff_type` は管理画面権限に影響しない**: `fortune_teller` と `store_staff` は完全同一権限
2. **サイドバー表示 ≠ アクセス権限**: `_build_full_app_list` でサイドバーにモデルが表示されても、changelist は Django 標準の `has_view_or_change_permission` で制御。staff ロールはサイドバーにモデルが見えるが changelist は 403
3. **`_is_owner_or_super`**: `is_superuser` or `is_owner` のみ。`is_developer` は含まれない
4. **developer の changelist アクセス**: `_is_owner_or_super=False` のため、一部 ModelAdmin の changelist で 403 になる可能性あり

### 4.3 エンドポイント別アクセスマトリクス

| エンドポイント | staff | manager | owner | developer | superuser |
|--------------|-------|---------|-------|-----------|-----------|
| `/admin/` | 200 | 200 | 200 | 200 | 200 |
| `/admin/booking/staff/` | 403 | 200 | 200 | — | 200 |
| `/admin/booking/store/` | 403 | — | — | — | 200 |
| `/admin/booking/payrollperiod/` | 403 | — | — | — | — |
| `/admin/debug/` | 403 | 403 | — | 200 | 200 |
| `/admin/booking/staff/add/` | 403 | 200 | — | — | — |

*「—」はテスト未実施*

---

## 5. 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `booking/models.py` | 変更 | Store に `map_url`, `access_info` 追加 |
| `booking/views.py` | 変更 | `_build_access_lines`, `StoreAccessView`, `process_payment` 更新 |
| `booking/urls.py` | 変更 | `/store/<pk>/access/` 追加 |
| `booking/templates/booking/store_access.html` | 新規 | 店舗アクセスページテンプレート |
| `booking/templates/booking/store_list.html` | 変更 | アクセス情報ボタン追加 |
| `booking/templates/booking/booking_top.html` | 変更 | モバイル 2×2 グリッド |
| `booking/templates/booking/base.html` | 変更 | ヘッダーログインボタン削除 |
| `static/css/jazzmin_overrides.css` | 変更 | モバイル admin ブランド表示 |
| `booking/migrations/0066_*.py` | 新規 | マイグレーション |
| `tests/test_admin_roles.py` | 新規 | ロール別管理画面テスト (39) |
| `tests/test_payment_access_info.py` | 新規 | 決済アクセス情報テスト (9) |
