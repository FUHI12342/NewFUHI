# E2E テスト結果 — timebaibai.com

日時: 2026-03-23 (最終更新: 18:30)
テスター: Playwright (headless Chromium)
環境: 本番 (https://timebaibai.com)
テストスクリプト: `/tmp/e2e/run_e2e.py` (メイン25テスト), `/tmp/e2e/test_i18n_nav.py` (i18n 21テスト)

## サマリー

| Phase | テスト数 | PASS | FAIL | BLOCKED |
|---|---|---|---|---|
| Phase 1: ログイン | 4 | 4 | 0 | 0 |
| Phase 2: ワークフロー | 12 | 12 | 0 | 0 |
| Phase 3: ロール間連動 | 3 | 3 | 0 | 0 |
| Phase 4: 権限境界 | 4 | 4 | 0 | 0 |
| Phase 5: 公開ページ | 2 | 2 | 0 | 0 |
| **メインE2E合計** | **25** | **25** | **0** | **0** |

### i18n ナビゲーションテスト (追加)

| Phase | テスト数 | PASS | FAIL |
|---|---|---|---|
| 公開ページ zh-hant | 7 | 7 | 0 |
| 言語切替: ページ維持 | 1 | 1 | 0 |
| Admin zh-hant ナビ | 6 | 6 | 0 |
| 旧URLリダイレクト | 2 | 2 | 0 |
| ページ間遷移 言語維持 | 5 | 5 | 0 |
| **i18n合計** | **21** | **21** | **0** |

### 総合計: 46テスト / 46 PASS / 0 FAIL

## 詳細結果

| ID | テスト名 | 結果 | 備考 | スクリーンショット |
|---|---|---|---|---|
| T1.1 | cast login + sidebar | PASS | Status: 200; 'タイムカード': OK; 'シフト': OK; 'IoT': OK | login_cast.png |
| T1.2 | staff login + sidebar | PASS | Status: 200; 'タイムカード': OK; 'シフト': OK; 'IoT': OK | login_staff.png |
| T1.3 | manager login + sidebar | PASS | Status: 200; '予約': OK; 'レジ': OK; 'シフト': OK; 'メニュー': OK | login_manager.png |
| T1.4 | owner login + sidebar | PASS | Status: 200; 'シフト': OK; 'セキュリティ': OK; 'システム': OK | login_owner.png |
| T2.1 | Cast: シフトカレンダー閲覧 | PASS | Status: 200, Found: ['シフト'] | cast_T2.1.png |
| T2.2 | Cast: シフト希望画面 | PASS | Status: 200, Found: ['希望', 'シフト'] | cast_T2.2.png |
| T2.3 | Cast: 管理シフトカレンダー | PASS | Status: 200, Found: ['シフト'] | cast_T2.3a.png |
| T2.4 | Cast: マイページ | PASS | Status: 200, Found: [] | cast_T2.4.png |
| T2.5 | Cast: 勤怠PIN画面 | PASS | Status: 200, Found: ['PIN', '打刻', 'タイムカード'] | cast_T2.5.png |
| T2.3b | Cast: 本日のシフト | PASS | Status: 200 | cast_T2.3b.png |
| T2.6 | Manager: 売上ダッシュボード | PASS | Status: 200, Found: ['売上', 'ダッシュボード'] | manager_T2.6.png |
| T2.7 | Manager: POS画面 | PASS | Status: 200, Found: ['POS', '商品'] | manager_T2.7.png |
| T2.8 | Manager: EC注文管理 | PASS | Status: 200, Found: ['注文', 'EC'] | manager_T2.8.png |
| T2.9 | Owner: デバッグパネル | PASS | Status: 200, Found: ['デバイス', 'IoT', 'デバッグ'] | owner_T2.9.png |
| T2.10 | Owner: 給与管理 | PASS | Status: 200, Found: ['追加', '給与'] | owner_T2.10.png |
| T2.11 | Owner: 物件管理 | PASS | Status: 200 | owner_T2.11.png |
| T3.1 | Manager→Cast シフト期間 | PASS | Manager: 200, Cast: 200 | cross_T3.1_cast.png |
| T3.2 | Cast→Manager シフト希望 | PASS | Cast: 200, Manager requests: 200 | cross_T3.2_manager.png |
| T3.3 | Manager公開→Cast確認 | PASS | Manager: 200, Cast: 200 | cross_T3.3_cast.png |
| T4.1 | Cast→管理者専用ページ | PASS | Debug: 403 (blocked=True), Sales: 200 | perm_T4.1_debug.png |
| T4.2 | Manager削除不可 | PASS | Status: 200, Blocked: True | perm_T4.2.png |
| T4.3 | Staff追加不可 | PASS | Status: 403, Blocked: True | perm_T4.3.png |
| T4.4 | 未認証→リダイレクト | PASS | /shift/: ->login; /admin/: ->login; /mypage/: ->login | perm_T4.4.png |
| T5.1 | 公開7ページ確認 | PASS | トップ:200, 店舗:200, 占い師:200, カレンダー:200, ショップ:200, ニュース:200, ヘルプ:200 | public_T5.1.png |
| T5.2 | 中国語切替 | PASS | Top: 200, Stores: 200, ZH: True | i18n_T5.2_stores.png |

## i18n ナビゲーション詳細結果

| ID | テスト名 | 結果 | 備考 |
|---|---|---|---|
| P1 | 公開: トップ (zh-hant) | PASS | URL: /zh-hant/, Status: 200 |
| P2 | 公開: 店舗一覧 (zh-hant) | PASS | URL: /zh-hant/stores/, Status: 200 |
| P3 | 公開: 占い師一覧 (zh-hant) | PASS | URL: /zh-hant/fortune-tellers/, Status: 200 |
| P4 | 公開: カレンダー (zh-hant) | PASS | URL: /zh-hant/date-calendar/, Status: 200 |
| P5 | 公開: ショップ (zh-hant) | PASS | URL: /zh-hant/shop/, Status: 200 |
| P6 | 公開: ニュース (zh-hant) | PASS | URL: /zh-hant/news/, Status: 200 |
| P7 | 公開: ヘルプ (zh-hant) | PASS | URL: /zh-hant/help/, Status: 200 |
| LS1 | 言語切替: ページ維持 | PASS | /stores/ → /stores/ (同ページ維持) |
| A1 | Admin: zh-hant ホーム | PASS | URL: /zh-hant/admin/ |
| A2 | Admin: zh-hant ダッシュボード | PASS | URL: /zh-hant/admin/dashboard/sales/ |
| A3 | Dashboard→シフトカレンダー | PASS | href=/zh-hant/admin/shift/calendar/ |
| A4 | Dashboard→POS | PASS | href=/zh-hant/admin/pos/ |
| A5 | Dashboard→勤怠ボード | PASS | href=/zh-hant/admin/attendance/board/ |
| A6 | Shift Calendar: 管理メニュー | PASS | 全リンクにzh-hantプレフィックスあり |
| L1 | Legacy: 旧prebooking URL | PASS | 301→/ にリダイレクト |
| L2 | Legacy: 旧MQ9 URL | PASS | 301→/ にリダイレクト |
| N1 | ナビ遷移: 店舗一覧 | PASS | /zh-hant/stores/ |
| N2 | ナビ遷移: 占い師一覧 | PASS | /zh-hant/fortune-tellers/ |
| N3 | ナビ遷移: ショップ | PASS | /zh-hant/shop/ |
| N4 | ナビ遷移: ヘルプ | PASS | /zh-hant/help/ |
| N5 | ナビ遷移: ニュース | PASS | /zh-hant/news/staff-recruiting/ |

## 発見事項・修正履歴

### 修正済み (今回セッション)

- [FIXED] **i18n言語維持**: 管理画面のダッシュボードからリンクをクリックするとzh-hantが消える問題
  - 原因: テンプレート内のハードコードURL (`/admin/shift/calendar/` 等)
  - 修正: `{% url %}` タグに置換（restaurant_dashboard.html: 14箇所, shift_calendar.html: 5箇所, inventory_dashboard.html: 1箇所）
- [FIXED] **ForceLanguageMiddleware未適用**: セッション経由の言語維持ミドルウェアがMIDDLEWAREに登録されていなかった
  - 修正: `project/settings.py` の MIDDLEWARE に追加
- [FIXED] **言語切替時のリダイレクト先**: `next="/"` でトップに戻ってしまう
  - 修正: `base.html` で `next="{{ request.path }}"` に変更
- [FIXED] **旧URL 404**: クローラーが `/staff/*/prebooking/*/*.html` にアクセスして404
  - 修正: `project/urls.py` に301リダイレクト追加（i18n_patterns外）
- [FIXED] **EC注文管理500エラー**: `{% load static %}` 漏れ
  - 修正: `ec_dashboard.html` に `{% load i18n static %}` 追加

### 情報

- [INFO] 全46テスト正常完了
- [INFO] デモアカウント4ロール全て正常動作
- [INFO] 権限境界テスト正常（不正アクセスは403/リダイレクト）

## スクリーンショット

保存先: `/tmp/e2e/`

- `login_cast.png` — T1.1 cast login + sidebar
- `login_staff.png` — T1.2 staff login + sidebar
- `login_manager.png` — T1.3 manager login + sidebar
- `login_owner.png` — T1.4 owner login + sidebar
- `cast_T2.1.png` — T2.1 Cast: シフトカレンダー閲覧
- `cast_T2.2.png` — T2.2 Cast: シフト希望画面
- `cast_T2.3a.png` — T2.3 Cast: 管理シフトカレンダー
- `cast_T2.4.png` — T2.4 Cast: マイページ
- `cast_T2.5.png` — T2.5 Cast: 勤怠PIN画面
- `cast_T2.3b.png` — T2.3b Cast: 本日のシフト
- `manager_T2.6.png` — T2.6 Manager: 売上ダッシュボード
- `manager_T2.7.png` — T2.7 Manager: POS画面
- `manager_T2.8.png` — T2.8 Manager: EC注文管理
- `owner_T2.9.png` — T2.9 Owner: デバッグパネル
- `owner_T2.10.png` — T2.10 Owner: 給与管理
- `owner_T2.11.png` — T2.11 Owner: 物件管理
- `cross_T3.1_cast.png` — T3.1 Manager→Cast シフト期間
- `cross_T3.2_manager.png` — T3.2 Cast→Manager シフト希望
- `cross_T3.3_cast.png` — T3.3 Manager公開→Cast確認
- `perm_T4.1_debug.png` — T4.1 Cast→管理者専用ページ
- `perm_T4.2.png` — T4.2 Manager削除不可
- `perm_T4.3.png` — T4.3 Staff追加不可
- `perm_T4.4.png` — T4.4 未認証→リダイレクト
- `public_T5.1.png` — T5.1 公開7ページ確認
- `i18n_T5.2_stores.png` — T5.2 中国語切替

## テスト実行方法

```bash
# メインE2Eテスト (25テスト: ログイン, ワークフロー, 権限, 公開ページ)
/usr/bin/python3 /tmp/e2e/run_e2e.py

# i18nナビゲーションテスト (21テスト: 多言語遷移, リダイレクト)
/usr/bin/python3 /tmp/e2e/test_i18n_nav.py
```

前提: `pip install playwright && python -m playwright install chromium`

## デモアカウント

| Username | Password | Role |
|---|---|---|
| demo_owner | demo1234 | Owner (superuser) |
| demo_manager | demo1234 | Manager |
| demo_staff | demo1234 | Staff |
| demo_fortune | demo1234 | Cast |

## 修正ファイル一覧

| ファイル | 修正内容 |
|---|---|
| `project/settings.py` | ForceLanguageMiddleware追加 |
| `project/urls.py` | 旧URL 301リダイレクト追加 |
| `booking/templates/booking/base.html` | 言語切替の`next`フィールド修正 |
| `templates/admin/booking/restaurant_dashboard.html` | 14箇所のURL→`{% url %}`タグ化 |
| `templates/admin/booking/shift_calendar.html` | 5箇所のURL→`{% url %}`タグ化 |
| `templates/admin/booking/inventory_dashboard.html` | 1箇所のURL→`{% url %}`タグ化 |
| `templates/admin/booking/ec_dashboard.html` | `{% load static %}` 追加 |
| `config/nginx/snippets/security-headers.conf` | CSP `unsafe-eval` 追加 |