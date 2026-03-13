# Timebaibai (NewFUHI) 包括的レビューレポート

**実施日:** 2026-03-13
**対象:** ~/NewFUHI/ Django プロジェクト
**レビュー手法:** ECC並列エージェント (python-reviewer, security-reviewer, architect, HANDTEST分析, テストカバレッジ, ビルド検証)

---

## エグゼクティブサマリー

| カテゴリ | 評価 | CRITICAL | HIGH | MEDIUM | LOW |
|---------|------|----------|------|--------|-----|
| コード品質 | **要改善** | 5 | 10 | 7 | 4 |
| セキュリティ | **要改善** | 4 | 5 | 6 | 4 |
| テストカバレッジ | **60%** | - | - | - | - |
| ビルド/動作 | **良好** | 0 | 0 | 1 | 1 |
| HANDTEST網羅性 | **要追加** | - | 20欠落 | 10不足 | 4古い |
| アーキテクチャ | **要改善** | 3 | 4 | 3 | 2 |
| **合計** | | **12** | **19** | **27** | **15** |

---

## 1. テストカバレッジ検証

### 結果

```
769 passed, 7 skipped, 0 failed (867テスト関数定義)
全体カバレッジ: 60%
実行時間: 77秒
```

### カバレッジ詳細

| ファイル | カバレッジ | 評価 |
|---------|-----------|------|
| models.py | 89% | 良好 |
| views.py | 65% | 要改善 |
| views_restaurant_dashboard.py | 57% | 要改善 |
| views_attendance.py | 52% | 要改善 |
| ai_staff_recommend.py | 50% | 要改善 |
| views_chat.py | **0%** | 未テスト |
| clv_analysis.py | **0%** | 未テスト |
| auto_order.py | **0%** | 未テスト |
| external_data.py | **0%** | 未テスト |
| visitor_forecast.py | **0%** | 未テスト |
| utils.py | **0%** | 未テスト |
| ventilation_control.py | 31% | 不十分 |
| attendance_service.py | 100% | 優秀 |
| shift_scheduler.py | 99% | 優秀 |
| payroll_calculator.py | 97% | 優秀 |
| insight_engine.py | 94% | 良好 |

### 改善優先順位

1. `views_chat.py` — AI チャットのテスト追加
2. `clv_analysis.py` — 顧客生涯価値分析のテスト追加
3. `auto_order.py` — 自動発注のテスト追加
4. `views.py` — 65%→80%へ引き上げ（決済・LINE連携中心）
5. `views_restaurant_dashboard.py` — 57%→80%へ引き上げ

---

## 2. コード品質レビュー

### CRITICAL (5件)

| # | 問題 | ファイル:行 |
|---|------|-----------|
| C-1 | `process_payment` で `DoesNotExist` 未捕捉 → 500エラー | views.py:1439 |
| C-2 | レートカウンターがスレッドセーフでない | middleware.py:20-22 |
| C-3 | `hmac.new()` は非公式API（バージョン依存） | views.py:1522, totp_service.py:53 |
| C-4 | `except Exception: pass` で例外完全黙殺 | views.py:634-635 |
| C-5 | `UserSerializer` が models.py 内に存在 | models.py:272-275 |

### HIGH (10件)

| # | 問題 | ファイル |
|---|------|---------|
| H-1 | views.py **3,086行** (上限800行の4倍) | views.py |
| H-2 | models.py **2,067行**, admin.py **1,463行** | models.py, admin.py |
| H-3 | 型ヒントの欠如（パブリック関数が未注釈） | utils.py, views.py |
| H-4 | `from __future__ import` Python2遺物 | views.py:1, tasks.py:1 |
| H-5 | `pytz.timezone('Asia/Tokyo')` 7箇所ハードコード | views.py |
| H-6 | `get_reservation_times` と `get_reservation` が完全重複 | views.py:273-281 |
| H-7 | トランザクション内から `redirect` 返却 | views.py:2541-2546 |
| H-8 | DRF `permission_classes` 未設定で手動認証チェック | views_restaurant_dashboard.py:62 |
| H-9 | N+1クエリ（`product.store.name`） | tasks.py:61-67 |
| H-10 | 祝日テーブルが2020-2021年で停止 | settings/base.py:150-186 |

---

## 3. セキュリティ監査

### CRITICAL (4件)

| # | 問題 | 影響 | 修正 |
|---|------|------|------|
| S-C1 | 認証なしAPI **20箇所以上** (POS決済, 勤怠, デバッグ, IoT) | 不正決済・データ漏洩 | `REST_FRAMEWORK` デフォルト設定追加 |
| S-C2 | `AdminDebugPanelAPIView` 演算子優先順位バグ | 不正アクセス | 括弧追加 + ヘルパー関数化 |
| S-C3 | `hmac.new` は非公式API | 署名検証バイパスリスク | `hmac.HMAC()` に変更 |
| S-C4 | 本番で暗号化キーが空文字フォールバック | 暗号化無効化 | `env_required()` に変更 |

### HIGH (5件)

| # | 問題 | 影響 |
|---|------|------|
| S-H1 | `/healthz` が内部情報漏洩（git SHA, Django version） | 情報収集に悪用 |
| S-H2 | 勤怠打刻API (`AttendanceStampAPIView`) 認証なし | 勤怠改ざん |
| S-H3 | POS決済API (`POSCheckoutAPIView`) 認証なし | 不正決済 |
| S-H4 | キッチン注文ステータス・勤怠状況API 認証なし | データ漏洩 |
| S-H5 | `.env` ファイルパーミッション `644` (全員読取可) | シークレット漏洩 |

### MEDIUM (6件)

| # | 問題 |
|---|------|
| S-M1 | PIN平文比較（タイミング攻撃に脆弱） |
| S-M2 | ステージングで `SECURE_SSL_REDIRECT` 未設定 |
| S-M3 | `OrderStatusAPIView` でIDOR（注文ID列挙）可能 |
| S-M4 | TOTP コードが認証なしで公開 |
| S-M5 | `PASSWORD_HASHERS` 未設定（PBKDF2デフォルト） |
| S-M6 | CSP, Referrer-Policy, Permissions-Policy ヘッダー未設定 |

### 良好な実装

- SECRET_KEY の環境変数管理（全環境で `env_required()`）
- LINE user ID の Fernet 暗号化保存
- IoT APIキーのSHA-256ハッシュ保存
- Webhook 署名検証で `hmac.compare_digest` 使用
- 本番HSTS設定 (`SECURE_HSTS_SECONDS = 31536000`)
- ORM一貫使用（生SQLクエリなし）
- `format_html` 適切使用（`mark_safe` 未使用）
- SSRF対策 (`Media._is_safe_url()` で内部IPブロック)

---

## 4. 動作チェック・ビルド確認

### 結果

| チェック項目 | 結果 |
|-------------|------|
| `.venv` (Python 3.9 + Django 4.2.25) | **正常動作** |
| pytest 769テスト | **全パス** |
| 構文エラー (139ファイル) | **なし** |
| マイグレーション (65件) | **全適用済み** |
| SQLite DB (71テーブル) | **正常** |

### 注意事項

| 深刻度 | 問題 |
|--------|------|
| MEDIUM | 不要なvenvが2つ残存 (`venv/` Django 6.0.1, `myvenv/` Django 5.2.9) — `requirements.txt` の `<5.0` 制約違反 |
| LOW | venv整理推奨（`.venv` のみに統一） |

---

## 5. HANDTEST確認項目・手順

### 既存HANDTESTの評価

- 29セクション、1,213行の充実した文書
- IoT連携、ダッシュボード、POS、シフト、決済、セキュリティを網羅

### 欠落している機能 (20件)

| # | 欠落機能 | 対応コード |
|---|---------|-----------|
| 1 | CMS機能（SiteSettings, HeroBanner, BannerAd, CustomBlock） | models.py L1316-1520 |
| 2 | マイページ（スタッフ向け予約管理） | views.py MyPage* |
| 3 | スタッフ呼称カスタマイズ | models.py L1353-1356 |
| 4 | バナー広告管理 | models.py L1476-1499 |
| 5 | 外部リンク管理 | models.py L1504-1520 |
| 6 | カスタムHTMLブロック | models.py L1386-1408 |
| 7 | Instagram埋め込み | models.py L1349-1350 |
| 8 | SNS連携URL設定 | models.py L1333-1336 |
| 9 | 予約ランキング表示 | models.py L1342-1343 |
| 10 | 法定ページ（プライバシーポリシー・特商法） | views.py L2283-2296 |
| 11 | メニュー権限管理（AdminMenuConfig） | admin_site.py |
| 12 | 雇用契約管理 | models.py L1531-1572 |
| 13 | 給与体系（SalaryStructure） | models.py L1716-1743 |
| 14 | 代替商品提案API | views.py L1621 |
| 15 | 顧客向けメニューページ | views.py L1571, L1595 |
| 16 | 注文ステータス表示API（顧客側） | views.py L1782 |
| 17 | ヘルプページ | views.py L244 |
| 18 | コンバージョン分析 | views_analytics.py L100 |
| 19 | 来客分析設定 | admin_site.py |
| 20 | 日付先行カレンダー予約 | views.py L875 |

### 追加すべき新規セクション (8件)

- **A: CMS・ホームページ管理** — SiteSettings, ヒーローバナー, バナー広告, カスタムHTML, 法定ページ
- **B: マイページ機能** — スタッフ向け予約管理、カレンダー、休日追加
- **C: 日付先行カレンダー予約** — 日付選択→空きスタッフ表示フロー
- **D: 雇用契約・給与体系** — EmploymentContract, SalaryStructure のCRUD
- **E: 顧客向け注文フロー** — メニューページ、注文ステータス、代替商品
- **F: 勤怠管理追加テスト** — 休憩打刻、ジオフェンス、WorkAttendance自動生成
- **G: ロール別アクセス制御** — ownerロール、AdminMenuConfigカスタマイズ
- **H: 追加APIエンドポイント** — 15個の未テストAPI

---

## 6. アーキテクチャ改修提案

### CRITICAL

| # | 課題 | 難易度 | 推奨時期 |
|---|------|--------|---------|
| A-1 | 単一アプリ問題（booking に56モデル集約） | 大 | 1-2ヶ月(段階的) |
| A-2 | views.py 分割 (3,086行) | 中 | 即座に |
| A-3 | テスト戦略刷新 (booking/tests.py 1ファイル → テストスイート) | 大 | 1-2週間 |

### HIGH

| # | 課題 | 難易度 | 推奨時期 |
|---|------|--------|---------|
| A-4 | N+1クエリ修正 (select_related/prefetch_related) | 小 | 即座に |
| A-5 | サービスレイヤーへのロジック移動 (LineCallbackView等) | 中 | 1週間 |
| A-6 | CI/CD パイプライン構築 | 中 | 1週間 |
| A-7 | APIバージョニング + レスポンス形式統一 | 中 | 2週間 |

### 推奨アプリ分割案

```
apps/
  core/          — Store, Staff, Company, 共通mixins
  booking/       — Timer, Schedule, LINE連携, 予約フロー
  pos/           — Category, Product, Order, テーブルオーダー, EC
  shift/         — ShiftPeriod, ShiftRequest, ShiftAssignment
  attendance/    — WorkAttendance, Payroll*, 給与計算
  iot/           — IoTDevice, IoTEvent, VentilationAutoControl
  property/      — Property, PropertyDevice, PropertyAlert
  analytics/     — DashboardLayout, BusinessInsight, 分析サービス
  cms/           — SiteSettings, HeroBanner, BannerAd
  security/      — SecurityAudit, SecurityLog, ミドルウェア
```

---

## 7. 改修ロードマップ

### Phase 1: 緊急対応 (今週中)

1. `REST_FRAMEWORK` デフォルト認証・認可設定を `settings/base.py` に追加
2. `production.py` で暗号化キーを `env_required()` に変更
3. POS・勤怠APIに `LoginRequiredMixin` 追加
4. `AdminDebugPanelAPIView` の演算子優先順位バグ修正
5. `.env` ファイルパーミッションを `600` に変更

### Phase 2: 短期改善 (1-2週間)

6. views.py を機能別に分割 (iot, line, pos, ec, property, mypage)
7. `/healthz` の情報漏洩削減
8. N+1クエリ修正 (`select_related` 追加)
9. `_get_user_store()` 重複除去 (4ファイル→1箇所)
10. テストカバレッジ 60%→80% (未テスト5ファイルのテスト追加)

### Phase 3: 中期改善 (1ヶ月)

11. CI/CD パイプライン構築 (GitHub Actions)
12. Djangoアプリ分割 (core, iot, property から開始)
13. APIバージョニング (`/api/v1/`)
14. キャッシュ戦略導入 (SiteSettings, ダッシュボード)
15. Sentry 導入

### Phase 4: SaaS化準備 (3-6ヶ月)

16. PostgreSQL 移行
17. マルチテナント基盤 (`django-tenants`)
18. テナント別サブドメインルーティング

---

## 添付: テスト実行結果

```
$ pytest tests/ --cov=booking --cov=project -q
769 passed, 7 skipped, 28 warnings in 77.37s
TOTAL: 9352 statements, 3728 missing, 60% coverage
```
