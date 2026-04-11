# E2E テスト結果 — timebaibai.com

日時: 2026-04-11 23:18
テスター: Playwright (headless Chromium)
環境: 本番 (https://timebaibai.com)

## サマリー

| Phase | テスト数 | PASS | FAIL | BLOCKED |
|---|---|---|---|---|
| Phase 1: ログイン | 4 | 4 | 0 | 0 |
| Phase 2: ワークフロー | 12 | 12 | 0 | 0 |
| Phase 3: ロール間連動 | 3 | 3 | 0 | 0 |
| Phase 4: 権限境界 | 4 | 4 | 0 | 0 |
| Phase 5: 公開ページ | 2 | 2 | 0 | 0 |
| **合計** | **25** | **25** | **0** | **0** |

## 詳細結果

| ID | テスト名 | 結果 | 備考 | スクリーンショット |
|---|---|---|---|---|
| T1.1 | cast login + sidebar | PASS | Status: 200; 'シフト': OK; 'IoT制御登録': OK; 'SNS自動投稿': OK | login_cast.png |
| T1.2 | staff login + sidebar | PASS | Status: 200; 'シフト': OK; 'IoT制御登録': OK; 'SNS自動投稿': OK | login_staff.png |
| T1.3 | manager login + sidebar | PASS | Status: 200; '予約管理': OK; 'シフト': OK; 'IoT制御登録': OK; 'SNS自動投稿': OK | login_manager.png |
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

## 発見事項

- [INFO] 全テスト正常完了、問題なし

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