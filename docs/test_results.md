# NewFUHI テスト結果レポート

**最終実行日:** 2026-03-18
**Djangoバージョン:** Django Booking Platform (NewFUHI)

---

## 1. テスト実行概要

| 項目 | 結果 |
|------|------|
| 総テスト数 | 1,343 |
| 成功 (passed) | 1,336 |
| スキップ (skipped) | 7 |
| 失敗 (failed) | 0 |
| 実行時間 | 約192秒 |
| テストファイル数 | 82ファイル (`tests/` ディレクトリ) |
| カバレッジ | **80%** (9,947文 / 1,997未カバー) |

---

## 2. カバレッジ結果

### 2.1 モジュール別カバレッジ一覧

#### コアモジュール

| モジュール | カバレッジ | 総文数 | 未カバー | 状態 |
|-----------|-----------|--------|---------|------|
| models.py | 92% | 1,414 | 120 | 良好 |
| views.py | 73% | 1,757 | 478 | 要改善 |
| admin.py | ~60% | 1,364 | 602 | 要改善 |
| forms.py | 100% | - | 0 | 完了 |
| middleware.py | 97% | - | - | 良好 |
| health.py | 100% | - | 0 | 完了 |

#### ビュー系モジュール

| モジュール | カバレッジ | 状態 |
|-----------|-----------|------|
| views_chat.py | 100% | 完了 |
| views_dashboard.py | 90% | 良好 |
| views_property.py | 97% | 良好 |
| views_attendance.py | 75% | 要改善 |
| views_pos.py | 81% | 基準達成 |
| views_restaurant_dashboard.py | 74% | 要改善 |
| views_shift_api.py | 69% | 要改善 |
| views_shift_manager.py | 72% | 要改善 |

#### サービス層

| モジュール | カバレッジ | 改善前 | 状態 |
|-----------|-----------|--------|------|
| services/staff_evaluation.py | ~90% | 0% | 大幅改善 |
| services/ai_staff_recommend.py | ~70% | 50% | 改善 |
| services/basket_analysis.py | ~85% | 71% | 改善 |
| services/rfm_analysis.py | ~90% | 74% | 大幅改善 |
| services/sales_forecast.py | ~90% | 78% | 改善 |
| services/attendance_service.py | 100% | - | 完了 |
| services/auto_order.py | 96% | - | 良好 |

#### ユーティリティ・その他

| モジュール | カバレッジ | 状態 |
|-----------|-----------|------|
| line_notify.py | 100% | 完了 |
| ventilation_control.py | 100% | 完了 |

#### 管理コマンド

| モジュール | カバレッジ | 改善前 | 状態 |
|-----------|-----------|--------|------|
| management/commands/delete_food_drink_data.py | ~90% | 0% | 大幅改善 |
| management/commands/seed_restaurant_menu.py | ~90% | 0% | 大幅改善 |
| management/commands/sync_menu_config.py | ~90% | 0% | 大幅改善 |

### 2.2 カバレッジサマリー

| カテゴリ | 100%達成 | 90%以上 | 80%以上 | 80%未満 |
|---------|---------|--------|--------|---------|
| ビュー | 1 | 2 | 1 | 4 |
| サービス | 1 | 4 | 1 | 1 |
| コア | 2 | 1 | 0 | 2 |
| コマンド | 0 | 3 | 0 | 0 |
| ユーティリティ | 3 | 0 | 0 | 0 |

---

## 3. テスト分類

### 3.1 モデルテスト

コアデータモデルの整合性・バリデーションを検証。

- コアモデル (core)
- 注文モデル (order)
- シフトモデル (shift)
- 給与モデル (payroll)
- 物件モデル (property)
- セキュリティモデル (security)
- CMSモデル (CMS)
- テーブルモデル (table)

### 3.2 ビューテスト (統合テスト)

HTTPリクエスト/レスポンスのエンドツーエンド検証。

- 予約フロー (booking flow)
- ダッシュボード (dashboard)
- レストラン管理 (restaurant)
- ショップ/EC (shop/EC)
- POSシステム (POS)
- シフト管理 (shift)
- 勤怠管理 (attendance)
- チャット機能 (chat)
- デバッグ (debug)
- 在庫管理 (inventory)
- パフォーマンス (performance)
- 物件管理 (property)
- メニュープレビュー (menu preview)
- 分析機能 (analytics)

### 3.3 サービステスト

ビジネスロジック層の単体テスト。

- AIチャット (AI chat)
- AIレコメンド (AI recommend)
- 勤怠サービス (attendance)
- 給与計算 (payroll)
- QRコード (QR)
- シフト通知 (shift notifications)
- シフトスケジューラー (shift scheduler)
- TOTP認証 (TOTP)
- 全銀エクスポート (zengin export)
- 分析サービス (analytics)

### 3.4 APIテスト

REST APIエンドポイントの包括的テスト。

- 総合API (comprehensive)
- 注文API (order)
- 在庫API (stock)
- テーブルオーダーAPI (table order)

### 3.5 管理画面テスト

Django Adminカスタマイズの検証。

- 権限テスト (permissions)
- ロールテスト (roles)

### 3.6 コマンドテスト

Django管理コマンドの動作検証。

- bootstrap_admin
- cancel_temp
- check_aws_costs
- cleanup_logs

### 3.7 セキュリティテスト

セキュリティ機能の専用テスト。

- CSRF保護
- ミドルウェア
- 監査ログ (audit)
- 大容量ファイル拒否 (large file rejection)

### 3.8 設定・インフラテスト

アプリケーション設定の検証。

- Django設定 (Django config)
- データベース設定 (database)
- サーバー設定 (server)
- ソース設定 (sources)
- マネージャー設定 (manager)

### 3.9 カバレッジ向上テスト

既存コードのカバレッジ向上を目的とした追加テスト。

- スタッフ評価 (staff evaluation)
- バスケット分析 (basket analysis)
- RFM分析 (RFM analysis)
- 売上予測 (sales forecast)
- Admin changelist

---

## 4. カバレッジ改善履歴

| バージョン | カバレッジ | 総文数 | 未カバー | 改善内容 |
|-----------|-----------|--------|---------|---------|
| 改善前 | 78% | 9,947 | ~2,188 | ベースライン |
| 改善後 | **80%** | 9,947 | 1,997 | サービス層・コマンド・Admin強化 |

### 主な改善ポイント

| 対象 | 改善前 | 改善後 | 施策 |
|------|--------|--------|------|
| services/staff_evaluation.py | 0% | ~90% | 新規テスト作成 |
| management/commands/delete_food_drink_data.py | 0% | ~90% | 新規テスト作成 |
| management/commands/seed_restaurant_menu.py | 0% | ~90% | 新規テスト作成 |
| management/commands/sync_menu_config.py | 0% | ~90% | 新規テスト作成 |
| services/rfm_analysis.py | 74% | ~90% | テストケース追加 |
| services/sales_forecast.py | 78% | ~90% | テストケース追加 |
| services/basket_analysis.py | 71% | ~85% | テストケース追加 |
| services/ai_staff_recommend.py | 50% | ~70% | テストケース追加 |

**合計改善: +2ポイント (78% -> 80%)、約191文の追加カバー**

---

## 5. 残課題

### 5.1 80%未満のモジュール (優先度順)

| 優先度 | モジュール | 現在 | 目標 | 未カバー文数 | 備考 |
|--------|-----------|------|------|-------------|------|
| 高 | admin.py | ~60% | 80% | 602 | 文数最多、改善効果大 |
| 高 | views.py | 73% | 80% | 478 | コアビュー、影響範囲広 |
| 中 | views_restaurant_dashboard.py | 74% | 80% | - | 特定機能のビュー |
| 中 | views_attendance.py | 75% | 80% | - | 勤怠管理 |
| 中 | views_shift_manager.py | 72% | 80% | - | シフト管理 |
| 中 | views_shift_api.py | 69% | 80% | - | シフトAPI |
| 低 | services/ai_staff_recommend.py | ~70% | 80% | - | AI依存部分のモック必要 |

### 5.2 改善の優先順位

1. **admin.py (60% -> 80%)**: 602文が未カバーで最大の改善余地。Admin changelist、フィルタ、アクション機能のテスト追加が有効。
2. **views.py (73% -> 80%)**: 478文が未カバー。エッジケースやエラーハンドリングパスのテスト追加を推奨。
3. **シフト関連ビュー (69-75%)**: views_shift_api.py、views_shift_manager.py、views_attendance.py をまとめてテスト強化。
4. **レストランダッシュボード (74%)**: ダッシュボード表示ロジックのテスト追加。

### 5.3 スキップされたテスト (7件)

スキップ理由の調査と、可能であれば有効化を検討する。

---

## 6. テスト実行方法

### 6.1 全テスト実行

```bash
cd ~/NewFUHI
python manage.py test
```

### 6.2 カバレッジ付き実行

```bash
cd ~/NewFUHI
coverage run manage.py test
coverage report -m
coverage html  # HTMLレポート生成 (docs/coverage_html/)
```

### 6.3 特定テストの実行

```bash
# 特定テストファイル
cd ~/NewFUHI
python manage.py test tests.test_models_core

# 特定テストクラス
python manage.py test tests.test_models_core.CoreModelTest

# 特定テストメソッド
python manage.py test tests.test_models_core.CoreModelTest.test_specific_method
```

### 6.4 pytest での実行

```bash
cd ~/NewFUHI
pytest tests/ -v
pytest tests/ -v --cov --cov-report=term-missing
pytest tests/test_specific.py -v -k "test_name"
```

### 6.5 カバレッジレポートの確認

```bash
# ターミナル表示
coverage report -m

# HTMLレポート
open docs/coverage_html/index.html
```
