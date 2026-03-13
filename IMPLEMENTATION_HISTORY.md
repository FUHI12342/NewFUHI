# NewFUHI 実装機能履歴 & テスト項目一覧

> 最終更新: 2026-03-13
> 自動テスト: **776件** (pytest) | 手動テスト: **27セクション・200+項目** (HANDTEST.md)

---

## 目次

1. [プロジェクト概要](#プロジェクト概要)
2. [技術スタック](#技術スタック)
3. [モデル一覧 (55モデル)](#モデル一覧)
4. [API エンドポイント一覧 (49ルート)](#apiエンドポイント一覧)
5. [実装機能履歴 (Task #24〜#36)](#実装機能履歴)
6. [コード解析・改修履歴 (2026-03-13)](#コード解析改修履歴)
7. [自動テスト一覧 (776テスト)](#自動テスト一覧)
8. [手動テスト項目一覧 (HANDTEST.md)](#手動テスト項目一覧)
9. [マイグレーション履歴 (64件)](#マイグレーション履歴)

---

## プロジェクト概要

**NewFUHI** は飲食店 (シーシャバー) 向け統合管理システム。
Django + Django REST Framework をバックエンドに、予約・POS・シフト・給与・IoT・分析をワンストップで管理。

| 項目 | 値 |
|------|-----|
| フレームワーク | Django 4.x + DRF |
| DB | SQLite (開発) / PostgreSQL (本番) |
| タスクキュー | Celery + Redis |
| デプロイ | AWS EC2 + Gunicorn + Nginx |
| IoT | Raspberry Pi Pico 2W (MQ-9, PIR) |
| 外部連携 | LINE, Coiney, SwitchBot, AWS S3 |

---

## 技術スタック

- **Backend**: Python 3.9, Django 4.x, Django REST Framework
- **Frontend**: Django Templates, Chart.js, Vanilla JS
- **IoT**: MicroPython (Pico 2W), MQ-9/PIR センサー
- **CI/CD**: pytest (776テスト), HANDTEST.md (手動)
- **インフラ**: EC2, Nginx, Gunicorn, Celery, Redis, S3

---

## モデル一覧

全55モデル (`booking/models.py`)

### コアモデル
| モデル | 説明 |
|--------|------|
| Store | 店舗 |
| Staff | スタッフ (ユーザー紐付け) |
| Schedule | 予約 |
| Timer | タイマー |
| Company | 会社情報 |

### 注文・POS
| モデル | 説明 |
|--------|------|
| Order | 注文 |
| OrderItem | 注文明細 |
| Category | 商品カテゴリ |
| Product | 商品 |
| ProductTranslation | 商品翻訳 |
| StockMovement | 在庫移動 |
| TableSeat | テーブル席 |
| PaymentMethod | 決済方法 |
| POSTransaction | POSトランザクション |

### シフト・勤怠・給与
| モデル | 説明 |
|--------|------|
| ShiftPeriod | シフト期間 |
| ShiftRequest | シフト希望 |
| ShiftAssignment | シフト割当 |
| ShiftTemplate | シフトテンプレート |
| ShiftPublishHistory | シフト公開履歴 |
| EmploymentContract | 雇用契約 |
| WorkAttendance | 勤怠記録 |
| PayrollPeriod | 給与期間 |
| PayrollEntry | 給与明細 |
| PayrollDeduction | 給与控除 |
| SalaryStructure | 給与体系 |
| AttendanceTOTPConfig | 出退勤TOTP設定 |
| AttendanceStamp | 出退勤打刻 |

### IoT
| モデル | 説明 |
|--------|------|
| IoTDevice | IoTデバイス |
| IoTEvent | IoTイベント |
| VentilationAutoControl | 換気扇自動制御 (SwitchBot連携) |
| IRCode | 赤外線コード |
| Property | 物件 |
| PropertyDevice | 物件デバイス |
| PropertyAlert | 物件アラート |

### 分析・AI
| モデル | 説明 |
|--------|------|
| DashboardLayout | ダッシュボードレイアウト |
| BusinessInsight | ビジネスインサイト (AI生成) |
| CustomerFeedback | 顧客フィードバック (NPS) |
| VisitorCount | 来客カウント |
| VisitorAnalyticsConfig | 来客分析設定 |
| StaffRecommendationModel | AI推薦モデル |
| StaffRecommendationResult | AI推薦結果 |

### CMS・設定
| モデル | 説明 |
|--------|------|
| Notice | お知らせ |
| Media | メディア |
| SiteSettings | サイト設定 |
| HomepageCustomBlock | ホームページカスタムブロック |
| HeroBanner | ヒーローバナー |
| BannerAd | バナー広告 |
| ExternalLink | 外部リンク |
| StoreScheduleConfig | 店舗スケジュール設定 |

### システム・セキュリティ
| モデル | 説明 |
|--------|------|
| SystemConfig | システム設定 |
| AdminTheme | 管理画面テーマ |
| AdminMenuConfig | 管理画面メニュー設定 |
| SecurityAudit | セキュリティ監査 |
| SecurityLog | セキュリティログ |
| CostReport | コストレポート |

---

## APIエンドポイント一覧

全49ルート (`booking/api_urls.py`)

### IoT (6)
| パス | メソッド | 認証 | 説明 |
|------|--------|------|------|
| `/api/iot/events/` | POST | X-API-KEY | センサーデータ送信 |
| `/api/iot/config/` | GET | X-API-KEY | デバイス設定取得 |
| `/api/iot/ir/send/` | POST | X-API-KEY | IR コマンド送信 |
| `/api/iot/sensors/data/` | GET | Session | センサーデータ配列 |
| `/api/iot/sensors/pir-events/` | GET | Session | PIRイベント配列 |
| `/api/iot/sensors/pir-status/` | GET | Session | PIRステータス |

### ダッシュボード (18)
| パス | メソッド | 説明 |
|------|--------|------|
| `/api/dashboard/layout/` | GET/POST | レイアウト保存・取得 |
| `/api/dashboard/reservations/` | GET | 予約統計 |
| `/api/dashboard/sales/` | GET | 売上統計 |
| `/api/dashboard/staff-performance/` | GET | スタッフパフォーマンス |
| `/api/dashboard/shift-summary/` | GET | シフトサマリー |
| `/api/dashboard/low-stock/` | GET | 在庫不足アラート |
| `/api/dashboard/menu-engineering/` | GET | メニューエンジニアリング |
| `/api/dashboard/abc-analysis/` | GET | ABC分析 |
| `/api/dashboard/forecast/` | GET | 売上予測 |
| `/api/dashboard/sales-heatmap/` | GET | 時間帯別ヒートマップ |
| `/api/dashboard/aov-trend/` | GET | 客単価推移 |
| `/api/dashboard/cohort/` | GET | コホート分析 |
| `/api/dashboard/rfm/` | GET | RFMセグメンテーション |
| `/api/dashboard/basket/` | GET | バスケット分析 |
| `/api/dashboard/insights/` | GET/POST | ビジネスインサイト |
| `/api/dashboard/kpi-scorecard/` | GET | KPIスコアカード |
| `/api/dashboard/feedback/` | GET/POST | 顧客フィードバック |
| `/api/dashboard/nps/` | GET | NPS統計 |

### 分析 (3)
| パス | メソッド | 説明 |
|------|--------|------|
| `/api/analytics/visitors/` | GET | 来客分析 |
| `/api/analytics/heatmap/` | GET | ヒートマップ |
| `/api/analytics/conversion/` | GET | コンバージョン |

### AI推薦 (3)
| パス | メソッド | 説明 |
|------|--------|------|
| `/api/ai/recommendations/` | GET | 推薦取得 |
| `/api/ai/train/` | POST | モデル学習 |
| `/api/ai/model-status/` | GET | モデル状態 |

### シフト (3+)
| パス | メソッド | 説明 |
|------|--------|------|
| `/api/shift/*` | GET/POST | シフト管理 (week-grid, assignments, publish, auto-schedule) |
| `/api/shift/requests/<id>/bulk/` | POST | 一括シフト希望 |
| `/api/shift/requests/<id>/copy-week/` | POST | 週コピー |

### 出退勤 (4)
| パス | メソッド | 説明 |
|------|--------|------|
| `/api/attendance/stamp/` | POST | TOTP打刻 |
| `/api/attendance/pin-stamp/` | POST | PIN打刻 |
| `/api/attendance/day-status/` | GET | 本日の出退勤状況 |
| `/api/attendance/totp/refresh/` | POST | TOTP更新 |

### POS (5)
| パス | メソッド | 説明 |
|------|--------|------|
| `/api/pos/orders/` | GET | 本日オーダー |
| `/api/pos/order-items/` | GET/POST | 注文アイテム |
| `/api/pos/checkout/` | POST | 会計処理 |
| `/api/pos/order-item/<pk>/status/` | PUT | ステータス更新 |
| `/api/pos/kitchen-orders/` | GET | キッチンオーダー |

### テーブル注文 (5)
| パス | メソッド | 説明 |
|------|--------|------|
| `/api/table/<id>/cart/add/` | POST | カート追加 |
| `/api/table/<id>/cart/update/` | POST | カート更新 |
| `/api/table/<id>/cart/remove/` | POST | カート削除 |
| `/api/table/<id>/order/create/` | POST | 注文作成 |
| `/api/table/<id>/orders/status/` | GET | 注文状況 |

### ECショップ (3)
| パス | メソッド | 説明 |
|------|--------|------|
| `/api/shop/cart/add/` | POST | カート追加 |
| `/api/shop/cart/update/` | POST | カート更新 |
| `/api/shop/cart/remove/` | POST | カート削除 |

### その他 (4)
| パス | メソッド | 説明 |
|------|--------|------|
| `/api/debug/panel/` | GET | デバッグパネル |
| `/api/debug/log-level/` | POST | ログレベル変更 |
| `/api/chat/admin/` | POST | AIチャット (管理者) |
| `/api/chat/guide/` | POST | AIチャット (ガイド) |

---

## 実装機能履歴

### Task #24: Bug修正 — キッチンディスプレイ自動更新
- **問題**: `setInterval` で `loadKitchenOrders()` を呼び出していたが関数名不一致
- **修正**: 関数名を統一し、30秒間隔の自動リフレッシュを修復
- **テスト**: 3テスト追加 (自動更新動作確認)

### Task #25: 出退勤管理 (PIN打刻・QR打刻・出退勤ボード)
- **実装内容**:
  - `AttendanceTOTPConfig`, `AttendanceStamp` モデル追加
  - PIN打刻 API (`/api/attendance/pin-stamp/`)
  - 出退勤ボード画面 (`/admin/attendance/board/`)
  - QR打刻画面 (`/admin/attendance/qr/`)
- **マイグレーション**: 0050〜0052
- **テスト**: 30+テスト追加

### Task #26: スタッフ向けシフト希望カレンダーUI
- **実装内容**:
  - 週間カレンダーUI (ドラッグ選択)
  - 一括シフト希望 API
  - 週コピー機能
  - 終日・時間指定対応
- **テスト**: 15+テスト追加

### Task #27: メニューエンジニアリング マトリクス
- **実装内容**:
  - `MenuEngineeringAPIView` — 商品を Star/Puzzle/Plowhorse/Dog に分類
  - 散布図 (Chart.js) + 4象限表示
  - 人気度 × 利益率の2軸分析
- **API**: `/api/dashboard/menu-engineering/`
- **テスト**: 12テスト追加

### Task #28: ABC分析 (パレート)
- **実装内容**:
  - `ABCAnalysisAPIView` — 売上累積シェアでA/B/Cランク付け
  - パレート図 (棒グラフ+累積線)
  - A: 〜70%, B: 70〜90%, C: 90〜100%
- **API**: `/api/dashboard/abc-analysis/`
- **テスト**: 8テスト追加

### Task #29: 売上予測 (移動平均)
- **実装内容**:
  - `SalesForecastAPIView` — 7日移動平均ベースの14日予測
  - 信頼区間 (upper/lower) 付き折れ線グラフ
  - 過去実績 + 予測を一画面で表示
- **API**: `/api/dashboard/forecast/`
- **テスト**: 10テスト追加

### Task #30: 時間帯別ヒートマップ & 客単価推移
- **実装内容**:
  - `SalesHeatmapAPIView` — 曜日×時間帯の売上ヒートマップ
  - `AOVTrendAPIView` — 日別客単価 (AOV) 推移
  - Canvas ヒートマップ + 折れ線チャート
- **API**: `/api/dashboard/sales-heatmap/`, `/api/dashboard/aov-trend/`
- **テスト**: 16テスト追加

### Task #31: コホート分析 & RFMセグメンテーション
- **実装内容**:
  - `CohortAnalysisAPIView` — 月別初回購入コホートのリテンション率
  - `RFMAnalysisAPIView` — Recency/Frequency/Monetary スコアリング
  - コホートテーブル + RFMセグメント分布チャート
- **API**: `/api/dashboard/cohort/`, `/api/dashboard/rfm/`
- **テスト**: 18テスト追加

### Task #32: バスケット分析 (併売分析)
- **実装内容**:
  - `BasketAnalysisAPIView` — 同一注文内の商品ペア頻度分析
  - Support / Confidence / Lift 指標
  - 併売ペアランキングテーブル
- **API**: `/api/dashboard/basket/`
- **テスト**: 9テスト追加

### Task #33: ビジネスインサイト (AI分析)
- **実装内容**:
  - `BusinessInsight` モデル — AI生成インサイトの永続化
  - `InsightsAPIView` — GET (一覧) / POST (AI生成)
  - カテゴリ別タブ表示 (売上/メニュー/顧客/運営)
  - Claude AI (Anthropic API) による自動分析テキスト生成
- **API**: `/api/dashboard/insights/`
- **マイグレーション**: 0062
- **テスト**: 15テスト追加

### Task #34: KPIスコアカード
- **実装内容**:
  - `KPIScoreCardAPIView` — 7つの主要KPIを業界ベンチマークと比較
  - KPI: AOV, 売上, 注文数, リピート率, キャンセル率, テーブル回転率, 原価率
  - ベンチマーク定義 (good/warn/bad) + 色分けステータス表示
  - カード型UIでダッシュボード概要タブに統合
- **API**: `/api/dashboard/kpi-scorecard/`
- **テスト**: 11テスト追加

### Task #35: NPS & 顧客満足度
- **実装内容**:
  - `CustomerFeedback` モデル — NPS (0-10) + 料理/サービス/雰囲気 評価 (1-5) + コメント
  - `CustomerFeedbackAPIView` — POST (公開・QR経由) / GET (管理者一覧)
  - `NPSStatsAPIView` — NPS計算, 平均評価, 週次トレンド, 感情分布
  - NPSゲージ + レーダーチャート + トレンドチャート + フィードバックリスト
  - 自動感情分析 (NPSスコアベース)
- **API**: `/api/dashboard/feedback/`, `/api/dashboard/nps/`
- **マイグレーション**: 0063
- **テスト**: 19テスト追加

### Task #36: 操作チュートリアル
- **実装内容**:
  - 7ステップのガイドツアー (Pure JS, 外部依存なし)
  - ステップ: タブ切替 → 日付範囲 → 概要KPI → 売上チャート → 顧客分析 → メニュー分析 → 追加分析
  - `box-shadow` ベースのハイライト + ツールチップ
  - 初回アクセス時に自動表示 (`localStorage` で制御)
  - 「? ガイド」ボタンで再表示可能
- **テスト**: JS UIのみのため追加テストなし (手動テスト項目追加)

---

## コード解析・改修履歴

### 2026-03-13: 包括的コードベース解析 & Phase 1 セキュリティ改善

#### 解析概要

everything-claude-code 導入後、Django バックエンド (55モデル, 49 API, 776テスト) と IoT デバイスコード (MicroPython/CircuitPython, Pico 2W) を包括解析。

| 項目 | 結果 |
|------|------|
| 全テスト実行 | **776 passed**, 0 failed (74.93秒) |
| Django モデル数 | 55 |
| APIエンドポイント数 | 49 |
| IoTデバイスコード | 959行 (code.py), 3-tier通信 |

#### 検出された問題 (重要度別)

**CRITICAL**
| # | 問題 | ファイル | 対応状況 |
|---|------|---------|---------|
| 1 | POS決済: `transaction.atomic()` なし → race condition | `views_pos.py` | **修正済** |
| 2 | ダッシュボードAPI: 入力バウンドチェックなし | `views_restaurant_dashboard.py` | **修正済** |
| 3 | SwitchBotトークン: 平文保存 | `models.py` | **修正済 (Fernet暗号化)** |

**HIGH**
| # | 問題 | ファイル | 対応状況 |
|---|------|---------|---------|
| 4 | `except Exception:` 多用 (30+箇所) | 複数ファイル | **修正済 (主要ファイル)** |
| 5 | IoT Setup AP: ハードコードパスワード `"SETUP_PASSWORD"` | `pico_device/setup_ap.py` | 未対応 (Phase 2) |
| 6 | IoT API通信: HTTP (非HTTPS) | `config.py` | 未対応 (Phase 2) |
| 7 | WiFi credentials 平文コミット | `secrets.py` | 未対応 (Phase 2) |
| 8 | Staff attendance_pin: 平文4桁PIN | `models.py` | 未対応 (Phase 2) |

**MEDIUM**
| # | 問題 | ファイル | 対応状況 |
|---|------|---------|---------|
| 9 | N+1クエリ (ダッシュボードAPI) | `views_restaurant_dashboard.py` | 未対応 (Phase 3) |
| 10 | LINE通知リトライなし | `views.py` | 未対応 (Phase 3) |
| 11 | IoT: Watchdogタイマー未実装 | `code.py` | 未対応 (Phase 2) |
| 12 | IoT: DHT22センサープレースホルダー | `code.py` | 未対応 (Phase 2) |
| 13 | IoT API レート制限なし | `views.py` | 未対応 (Phase 3) |

#### Phase 1 修正内容 (2026-03-13 実施)

**Task #37: POS決済 race condition 修正**
- `views_pos.py`: `POSCheckoutAPIView.post()` を `transaction.atomic()` で包括
- 注文を `select_for_update()` で排他ロック
- 商品在庫更新を `Product.objects.select_for_update()` で安全に実行
- `items` クエリに `select_related('product')` 追加

**Task #38: ダッシュボードAPI入力バリデーション**
- `views_restaurant_dashboard.py`: `_clamp_int()` ヘルパー関数追加
- 8箇所の `int(request.GET.get('days', N))` を `_clamp_int()` に置換
- 対象API: MenuEngineering, ABCAnalysis, SalesForecast, SalesHeatmap, CohortAnalysis, RFMAnalysis, BasketAnalysis, KPIScoreCard
- `TypeError`/`ValueError` を安全にハンドリング

**Task #39: SwitchBotクレデンシャル暗号化**
- `models.py`: `VentilationAutoControl` に `set_switchbot_token()`, `get_switchbot_token()`, `set_switchbot_secret()`, `get_switchbot_secret()` メソッド追加
- `IOT_ENCRYPTION_KEY` を使用した Fernet 暗号化 (既存パターンに準拠)
- `admin.py`: `save_model()` オーバーライドで保存時自動暗号化
- `ventilation_control.py`: `rule.switchbot_token` → `rule.get_switchbot_token()` に変更
- フィールドの `max_length` を200→500に拡張 (暗号文対応)
- **マイグレーション**: `0064_switchbot_credential_encryption`

**Task #40: bare except 置換**
- `views_restaurant_dashboard.py`: 19箇所の `except Exception:` → `except (Staff.DoesNotExist, AttributeError):` 等
- `views.py`: 6箇所修正 (`PermissionDenied`, `TypeError/ValueError`)
- `views_debug.py`: 3箇所修正 (`OSError/UnicodeDecodeError`, `json.JSONDecodeError`)
- `context_processors.py`: 2箇所修正 + `Staff` import追加
- `admin.py`: `admin.sites.NotRegistered`, `json.JSONDecodeError`
- `admin_site.py`: DB未準備時のfallbackはコメント付きで維持

#### IoTデバイス解析結果

| 項目 | 詳細 |
|------|------|
| アーキテクチャ | boot.py → code.py → IoTDevice class |
| 通信方式 | 3-tier: Django HTTP (主) / AWS MQTT (副) / Setup AP (緊急) |
| センサー | MQ-9 (CO), PIR (人感), DHT22 (温湿度・プレースホルダー) |
| 送信間隔 | 20秒 |
| Setup AP | Wi-Fi設定用APモード (192.168.4.1) |
| OTA | 未実装 |
| Watchdog | 未実装 |

---

## 自動テスト一覧

**合計: 776テスト** (66テストファイル)

### テストファイル別一覧

| # | ファイル | 概要 |
|---|---------|------|
| 1 | `test_api_comprehensive.py` | API包括テスト |
| 2 | `test_api_order.py` | 注文API |
| 3 | `test_api_stock.py` | 在庫API |
| 4 | `test_api_table_order.py` | テーブル注文API |
| 5 | `test_ci_pipeline.py` | CI パイプライン |
| 6 | `test_cmd_bootstrap_admin.py` | bootstrap_admin コマンド |
| 7 | `test_cmd_cancel_temp.py` | cancel_temp コマンド |
| 8 | `test_cmd_check_aws_costs.py` | AWS コストチェック |
| 9 | `test_cmd_cleanup_logs.py` | ログクリーンアップ |
| 10 | `test_config_manager.py` | 設定マネージャー |
| 11 | `test_config_sources.py` | 設定ソース |
| 12 | `test_csrf_configuration.py` | CSRF設定 |
| 13 | `test_database_configuration.py` | DB設定 |
| 14 | `test_django_configuration.py` | Django設定 |
| 15 | `test_git_branch_protection.py` | Gitブランチ保護 |
| 16 | `test_health_endpoint.py` | ヘルスエンドポイント |
| 17 | `test_insight_engine.py` | インサイトエンジン |
| 18 | `test_iot_integration.py` | IoT統合 |
| 19 | `test_large_file_rejection.py` | 大ファイル拒否 |
| 20 | `test_middleware_security.py` | セキュリティミドルウェア |
| 21 | `test_models_cms.py` | CMSモデル |
| 22 | `test_models_core.py` | コアモデル |
| 23 | `test_models_order.py` | 注文モデル |
| 24 | `test_models_payroll.py` | 給与モデル |
| 25 | `test_models_property.py` | 物件モデル |
| 26 | `test_models_security.py` | セキュリティモデル |
| 27 | `test_models_shift.py` | シフトモデル |
| 28 | `test_models_shift_extended.py` | シフトモデル拡張 |
| 29 | `test_models_table.py` | テーブルモデル |
| 30 | `test_property_config_persistence.py` | 物件設定永続化 |
| 31 | `test_property_config_priority.py` | 物件設定優先度 |
| 32 | `test_property_dummy_detection.py` | ダミー検出 |
| 33 | `test_property_file_operations.py` | ファイル操作 |
| 34 | `test_property_logging.py` | ログ |
| 35 | `test_property_macos_filtering.py` | macOSフィルタ |
| 36 | `test_property_setup_activation.py` | セットアップ有効化 |
| 37 | `test_property_wifi_server_isolation.py` | WiFiサーバー分離 |
| 38 | `test_security_audit.py` | セキュリティ監査 |
| 39 | `test_server_configuration.py` | サーバー設定 |
| 40 | `test_service_ai_chat.py` | AIチャットサービス |
| 41 | `test_service_ai_recommend.py` | AI推薦サービス |
| 42 | `test_service_attendance.py` | 出退勤サービス |
| 43 | `test_service_payroll.py` | 給与サービス |
| 44 | `test_service_qr.py` | QRサービス |
| 45 | `test_service_shift_notifications.py` | シフト通知 |
| 46 | `test_service_shift_scheduler.py` | シフトスケジューラー |
| 47 | `test_service_totp.py` | TOTPサービス |
| 48 | `test_service_zengin_export.py` | 全銀エクスポート |
| 49 | `test_setup_ap.py` | APセットアップ |
| 50 | `test_staging_deployment.py` | ステージングデプロイ |
| 51 | `test_tasks.py` | Celeryタスク |
| 52 | `test_views_analytics.py` | 分析ビュー |
| 53 | `test_views_attendance_qr.py` | QR出退勤ビュー |
| 54 | `test_views_booking_flow.py` | 予約フロービュー |
| 55 | `test_views_chat.py` | チャットビュー |
| 56 | `test_views_dashboard.py` | ダッシュボードビュー |
| 57 | `test_views_debug.py` | デバッグビュー |
| 58 | `test_views_mypage.py` | マイページビュー |
| 59 | `test_views_pos.py` | POSビュー |
| 60 | `test_views_property.py` | 物件ビュー |
| 61 | `test_views_restaurant_dashboard.py` | レストランダッシュボードビュー |
| 62 | `test_views_restaurant.py` | レストランビュー |
| 63 | `test_views_shift_manager.py` | シフト管理ビュー |
| 64 | `test_views_shift.py` | シフトビュー |
| 65 | `test_views_shop_ec.py` | ECショップビュー |
| 66 | `test_wifi_manager.py` | WiFiマネージャー |

### テストカテゴリ別

| カテゴリ | テストファイル数 | 概要 |
|---------|----------------|------|
| モデル | 9 | core, cms, order, payroll, property, security, shift, shift_extended, table |
| ビュー | 14 | analytics, attendance_qr, booking_flow, chat, dashboard, debug, mypage, pos, property, restaurant_dashboard, restaurant, shift_manager, shift, shop_ec |
| API | 4 | comprehensive, order, stock, table_order |
| サービス | 8 | ai_chat, ai_recommend, attendance, payroll, qr, shift_notifications, shift_scheduler, totp, zengin_export |
| 設定・インフラ | 12 | ci_pipeline, config_manager, config_sources, csrf, database, django, git_branch, health, large_file, middleware_security, server, staging |
| コマンド | 4 | bootstrap_admin, cancel_temp, check_aws_costs, cleanup_logs |
| IoT・物件 | 8 | iot_integration, property_config_persistence, property_config_priority, property_dummy_detection, property_file_operations, property_logging, property_macos_filtering, property_setup_activation, property_wifi_server_isolation |
| その他 | 4 | insight_engine, security_audit, setup_ap, tasks, wifi_manager |

---

## 手動テスト項目一覧

**HANDTEST.md** — 27セクション、200+チェック項目

| # | セクション | サブ項目数 | 概要 |
|---|-----------|-----------|------|
| 1 | LINE OAuth フロー | 3 | LINEログイン、プロフィール取得、エッジケース |
| 2 | IoTデバイス通信 | 4 | センサー送信、設定取得、IR学習・送信、APIキー認証 |
| 3 | ガスアラート E2E | 4 | 閾値超過アラート、解決、換気扇自動制御、物件監視タスク |
| 4 | Coiney 決済 | 3 | 予約決済、Webhook署名検証、テーブル注文決済 |
| 5 | QR コードスキャン | 3 | 予約チェックイン、テーブル注文、入庫 |
| 6 | Email OTP 認証 | 2 | メール予約フロー、エッジケース |
| 7 | 管理画面 UI 基本 | 3 | ロール別メニュー、AIチャット、テーマカスタマイズ |
| 8 | 売上ダッシュボード | 19 | KPI表示、予約/売上/スタッフ/シフト/在庫API、レイアウト、メニューエンジニアリング、ABC分析、売上予測、ヒートマップ、AOV、コホート、RFM、バスケット、インサイト、KPIスコアカード、NPS、チュートリアル |
| 9 | 来客分析ダッシュボード | 4 | KPI、来客推移、ヒートマップ、店舗切替 |
| 10 | AI推薦ダッシュボード | 5 | モデル情報、特徴量重要度、推薦テーブル、再学習、API |
| 11 | シフトカレンダー | 6 | 週間グリッド、シフト操作、テンプレート、公開、自動スケジュール、希望カレンダーUI |
| 12 | POS システム | 5 | 画面表示、注文作成、送信、会計、一覧 |
| 13 | キッチンディスプレイ | 3 | 画面表示、ステータス更新、自動更新 |
| 14 | 出退勤管理 | 3 | PIN打刻、QR打刻、出退勤ボード |
| 15 | 給与管理 | 5 | 期間一覧、計算、明細、ZENGIN CSV、支払処理 |
| 16 | IoTセンサーダッシュボード | 4 | MQ-9グラフ、PIRイベント、PIRステータス、自動更新 |
| 17 | 在庫管理 | 4 | 商品一覧、在庫アクション、不足アラート、EC商品表示 |
| 18 | テーブル注文フロー | 4 | テーブルQR、注文フロー、キッチン連携、お会計 |
| 19 | ECショップ | 3 | 商品表示、カート操作、チェックアウト |
| 20 | 多言語対応 (i18n) | 2 | 言語切替、翻訳データ |
| 21 | Celery タスク | 3 | 定期タスク、手動実行、エラーハンドリング |
| 22 | ブラウザ互換性 | 3 | モバイル、デスクトップ、レスポンシブ |
| 23 | 本番デプロイ検証 | 7 | SSL、systemd、UFW、Fail2ban、Nginx、S3バックアップ、ヘルスチェック |
| 24 | IoT 本番通信テスト | 4 | デバイス設定、センサー送信、設定取得、アラート |
| 25 | AWS Security Group | 1 | インバウンド/アウトバウンドルール |
| 26 | デバッグパネル | 3 | パネル表示、ログレベル、IoTデバイスデバッグ |
| 27 | セキュリティ機能 | 3 | SecurityAudit、SecurityLog、CostReport |
| 付録A | 全API一覧 | - | 全エンドポイントと期待レスポンス |
| 付録B | モックデータ投入 | - | seed_mock_data コマンド |
| 付録C | 営業デモ用チェックリスト | - | デモ映えする10画面 |

---

## マイグレーション履歴

全64件 (`booking/migrations/`)

| 範囲 | 主要な変更 |
|------|-----------|
| 0001 | 初期モデル (Store, Staff, Schedule, Timer, etc.) |
| 0002-0010 | Company, Notice, Media, IoTDevice, IoTEvent, Category, Product, Order |
| 0011-0020 | SystemConfig, Property, StoreScheduleConfig, CMS (SiteSettings, etc.) |
| 0021-0030 | TableSeat, PaymentMethod, ShiftPeriod/Request/Assignment/Template |
| 0031-0040 | IoT拡張 (IRCode, PropertyDevice, PropertyAlert), AdminTheme |
| 0041-0050 | EmploymentContract, WorkAttendance, Payroll, AdminMenuConfig |
| 0051-0055 | AttendanceTOTPConfig, AttendanceStamp, POSTransaction |
| 0056-0060 | VisitorCount, VisitorAnalyticsConfig, SecurityAudit/Log, AI推薦, CostReport |
| 0061 | StaffRecommendationResult |
| 0062 | BusinessInsight |
| 0063 | CustomerFeedback |
| 0064 | SwitchBot クレデンシャル暗号化 (switchbot_token/secret max_length拡張) |

---

## ダッシュボード APIView クラス一覧

`booking/views_restaurant_dashboard.py` — 20クラス

| # | クラス | API パス | 説明 |
|---|--------|---------|------|
| 1 | AdminSidebarMixin | - | 認証・店舗スコープの共通Mixin |
| 2 | RestaurantDashboardView | /admin/dashboard/sales/ | テンプレートビュー |
| 3 | DashboardLayoutAPIView | /api/dashboard/layout/ | レイアウト保存・取得 |
| 4 | ReservationStatsAPIView | /api/dashboard/reservations/ | 予約統計 |
| 5 | SalesStatsAPIView | /api/dashboard/sales/ | 売上統計 |
| 6 | StaffPerformanceAPIView | /api/dashboard/staff-performance/ | スタッフ評価 |
| 7 | ShiftSummaryAPIView | /api/dashboard/shift-summary/ | シフトサマリー |
| 8 | LowStockAlertAPIView | /api/dashboard/low-stock/ | 在庫不足 |
| 9 | MenuEngineeringAPIView | /api/dashboard/menu-engineering/ | メニュー分析 |
| 10 | ABCAnalysisAPIView | /api/dashboard/abc-analysis/ | ABC分析 |
| 11 | SalesForecastAPIView | /api/dashboard/forecast/ | 売上予測 |
| 12 | SalesHeatmapAPIView | /api/dashboard/sales-heatmap/ | 時間帯ヒートマップ |
| 13 | AOVTrendAPIView | /api/dashboard/aov-trend/ | 客単価推移 |
| 14 | CohortAnalysisAPIView | /api/dashboard/cohort/ | コホート分析 |
| 15 | RFMAnalysisAPIView | /api/dashboard/rfm/ | RFMセグメンテーション |
| 16 | BasketAnalysisAPIView | /api/dashboard/basket/ | バスケット分析 |
| 17 | InsightsAPIView | /api/dashboard/insights/ | ビジネスインサイト |
| 18 | KPIScoreCardAPIView | /api/dashboard/kpi-scorecard/ | KPIスコアカード |
| 19 | CustomerFeedbackAPIView | /api/dashboard/feedback/ | 顧客フィードバック |
| 20 | NPSStatsAPIView | /api/dashboard/nps/ | NPS統計 |
