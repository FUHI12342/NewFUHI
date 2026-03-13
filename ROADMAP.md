# NewFUHI 機能拡張ロードマップ

> 作成日: 2026-03-12 | 最終更新: 2026-03-14
> 対象: timebaibai.com (シーシャ屋 + 占い予約 管理システム)

---

## Phase 1: シフト希望カレンダーUI刷新 ✅ 完了 (Task #26)

### 背景
現状のシフト希望提出は1日1件ずつフォーム入力（20〜30回の繰り返し操作）。
業界標準（ジョブカン、7shifts、シフオプ）に合わせ、カレンダー式マルチ選択UIに刷新する。

### 変更内容

#### 1-1. 新テンプレート: `staff_shift_calendar_v2.html`
- **月間カレンダーグリッド** (Alpine.js)
- テンプレートチップ（早番/遅番/フル/休）をタップ → セルをタップで適用
- 複数日バッチ選択（長押し → マルチ選択モード）
- 「前週コピー」ボタン
- セル色分け: 希望(緑) / 出勤可(青) / 不可(赤) / 未入力(グレー)
- モバイルファースト（44px以上タッチターゲット、スワイプ週移動）

#### 1-2. 新API: `ShiftRequestBulkAPIView`
- `POST /api/shift/requests/bulk/` — 複数ShiftRequestを一括作成/更新
- リクエスト例:
  ```json
  {
    "period_id": 1,
    "requests": [
      {"date": "2026-04-01", "start_hour": 9, "end_hour": 14, "preference": "preferred"},
      {"date": "2026-04-02", "start_hour": 14, "end_hour": 21, "preference": "available"},
      {"date": "2026-04-03", "preference": "unavailable"}
    ]
  }
  ```
- `POST /api/shift/requests/copy-week/` — 前週の希望を翌週にコピー

#### 1-3. ShiftTemplate 初期データ追加
- seed_mock_data に早番(9-14)/遅番(14-21)/フル(9-21)/休みテンプレート追加

#### 1-4. 締切リマインダー
- Celeryタスク: 締切3日前 + 当日にLINE通知
- 未提出スタッフリスト表示（マネージャー画面）

### 修正ファイル
| ファイル | 変更 |
|---------|------|
| `booking/templates/booking/staff_shift_calendar_v2.html` | 新規: カレンダーUI |
| `booking/views.py` | StaffShiftCalendarView を v2 テンプレートに切替 |
| `booking/shift_api_urls.py` | bulk, copy-week エンドポイント追加 |
| `booking/views_shift_manager.py` | ShiftRequestBulkAPIView, CopyWeekAPIView 追加 |
| `booking/tasks.py` | shift_deadline_reminder タスク追加 |
| `booking/management/commands/seed_mock_data.py` | ShiftTemplate 初期データ |

### モデル変更: なし（既存ShiftRequest/ShiftTemplateで対応可能）

---

## Phase 2: 売上ダッシュボード強化 ✅ 全5機能 完了

### 現状
6タブ構成（概要/売上/スタッフ/シフト/勤怠/運営）で基本KPIは表示済み。
~~**記述的分析（何が起きた）** のみで、**診断・予測・処方的分析**が欠けている。~~ → Phase 2-5 で全て実装済み。

### 追加機能

#### 2-1. メニューエンジニアリング・マトリクス (Stars/Plowhorses/Puzzles/Dogs) ✅ Task #27
**概要**: 各商品を「利益率 × 人気度」の4象限に分類し、メニュー戦略を提案

| 象限 | 利益率 | 人気 | アクション |
|------|--------|------|-----------|
| Stars | 高 | 高 | 目立つ位置に配置、価格維持 |
| Plowhorses | 低 | 高 | 原価見直し、高利益商品とセット化 |
| Puzzles | 高 | 低 | プロモーション強化、メニュー配置改善 |
| Dogs | 低 | 低 | メニューから削除検討、リニューアル |

**実装**:
- 新API: `GET /api/dashboard/menu-engineering/`
- 計算: `OrderItem` から商品別の売上数量 + `Product.price - Product.cost` で利益率
- Product モデルに `cost` (原価) フィールド追加
- Chart.js scatter chart で4象限マッピング表示
- 各商品に推奨アクションを自動表示

#### 2-2. ABC分析（在庫/売上パレート） ✅ Task #28
**概要**: 売上貢献度で商品をA/B/Cランク分類（パレート原則）

- A: 上位20%（売上の80%） → 重点管理
- B: 次の30%（売上の15%） → 標準管理
- C: 残り50%（売上の5%） → 簡易管理

**実装**:
- 新API: `GET /api/dashboard/abc-analysis/`
- 累積売上比率を計算し自動分類
- パレート図（棒グラフ + 累積折れ線）で可視化

#### 2-3. 売上予測 (Time Series Forecasting) ✅ Task #29
**概要**: 過去データから今後7〜30日の売上を予測

**実装**:
- `booking/services/sales_forecast.py` 新規作成
- 手法: Prophet（Meta製。季節性・休日・トレンド自動検出）
  - フォールバック: 移動平均 + 曜日係数（Prophet未インストール時）
- 特徴量: 曜日、月、祝日フラグ、天気（将来拡張）、イベント
- 新API: `GET /api/dashboard/forecast/?days=14`
- Chart.js で実績線 + 予測線（信頼区間付き）表示

#### 2-4. 時間帯別売上ヒートマップ ✅ Task #30
**概要**: 曜日×時間帯の売上ヒートマップ（来客分析と同形式）

- 売上額ベースのヒートマップ
- ピークタイム / オフピーク可視化
- オフピーク施策提案（ハッピーアワー等）

#### 2-5. 客単価トレンド ✅ Task #30
**概要**: Average Order Value (AOV) の推移

- 日別/週別/月別の客単価チャート
- 前期比較（前月比、前年同月比）
- セット販売・アップセルの効果測定

---

## Phase 3: 来客分析の高度化 ✅ 全5機能 完了

### 現状
PIRセンサーベースの来客数推定 + 曜日×時間ヒートマップ + コンバージョン率。
コホート/RFM/バスケット分析は実装済み。来客予測・CLVは未着手。

### 追加機能

#### 3-1. コホート分析（顧客リテンション） ✅ Task #31
**概要**: 初回来店月ごとのグループで、再来店率を時系列追跡

**実装**:
- 新API: `GET /api/analytics/cohort/`
- Schedule の `line_user_hash` または `customer_email_hash` でユニーク顧客識別
- 月別コホートテーブル（行=初来店月、列=経過月数、値=リテンション率）
- 色付きヒートマップ表示

**アクション提案**:
- リテンション率が急落する月を特定 → 再来店促進施策の提案
- 「初来店から2ヶ月後にリテンション率が50%に低下 → 1ヶ月後にLINEクーポン送信を推奨」

#### 3-2. RFM分析（顧客セグメンテーション） ✅ Task #31
**概要**: 顧客を Recency(最終来店) × Frequency(来店頻度) × Monetary(利用金額) でスコアリング

**実装**:
- 新API: `GET /api/analytics/rfm/`
- 新サービス: `booking/services/rfm_analysis.py`
- Schedule + Order データからRFMスコア(各1-5)を算出
- セグメント自動分類:

| セグメント | R | F | M | 推奨アクション |
|-----------|---|---|---|-------------|
| Champions | 5 | 5 | 5 | VIP特典、口コミ依頼 |
| Loyal | 4+ | 4+ | 4+ | ロイヤルティプログラム |
| Potential Loyalists | 5 | 1-2 | 1-2 | 初回来店フォロー、次回クーポン |
| At Risk | 2-3 | 3+ | 3+ | 再来店促進LINE通知 |
| Lost | 1 | 1-2 | 1-2 | 復帰キャンペーン |

- バブルチャート可視化（X=Frequency、Y=Monetary、サイズ=Recency、色=セグメント）

#### 3-3. マーケットバスケット分析（併買分析） ✅ Task #32
**概要**: 「Aを注文した人はBも注文する」パターンを発見

**実装**:
- 新API: `GET /api/analytics/basket/`
- 新サービス: `booking/services/basket_analysis.py`
- Aprioriアルゴリズム（mlxtend ライブラリ）
- OrderItem のトランザクションデータから関連ルール抽出
- Support, Confidence, Lift を計算
- 結果例: 「シーシャ(ミント) → チャイ (Confidence: 72%, Lift: 2.3)」
- **アクション**: セット割引提案、メニュー配置最適化、レコメンド表示

#### 3-4. 来客予測 ✅ 実装済
**概要**: 過去の来客パターンから今後の来客数を予測

- 売上予測と同じProphetベース
- 天気API連携（将来: OpenWeatherMap）
- 予測値に基づくスタッフ配置推奨

#### 3-5. 顧客生涯価値 (CLV) ✅ 実装済
**概要**: 各顧客セグメントのライフタイムバリューを計算

- CLV = 平均注文額 × 月間来店頻度 × 平均継続月数
- セグメント別CLVを表示
- 顧客獲得コスト(CAC)との比較（将来: 広告連携）

---

## Phase 4: 処方的分析 — AI経営アドバイザー ✅ 全4機能 完了

### コンセプト
データを見せるだけでなく、**具体的なアクション**を提案する。
Square AI のような「聞けば答える」ではなく、**プロアクティブに提案**する。

### 4-1. 自動インサイトエンジン ✅ Task #33
**概要**: 毎日/毎週の定期分析で、注目すべき変化を自動検出して通知

**検出パターン**:
| パターン | 条件 | アクション提案 |
|---------|------|-------------|
| 売上急落 | 前週比-20%以上 | 原因分析（天気/イベント/競合）を表示 |
| 在庫危機 | A商品が在庫3日分以下 | 発注推奨量を表示 |
| スタッフ過剰 | 来客予測 < 配置人数 | シフト削減候補を表示 |
| スタッフ不足 | 来客予測 > 配置人数×1.5 | 追加シフト募集を推奨 |
| 人気商品の利益率低下 | Star→Plowhorse移行 | 原価見直し/値上げ検討を提案 |
| 新規客の再来店率低下 | コホート2ヶ月目が前期比-10% | LINEクーポン施策を推奨 |
| ピーク時間シフト | ピーク時間帯の変化検出 | 営業時間/スタッフ配置の見直し提案 |

**実装**:
- 新サービス: `booking/services/insight_engine.py`
- 新モデル: `BusinessInsight`
  ```python
  class BusinessInsight(models.Model):
      store = ForeignKey(Store)
      insight_type = CharField(max_length=50)  # sales_drop, low_stock, overstaffed, etc.
      severity = CharField(max_length=20)  # info, warning, critical
      title = CharField(max_length=200)
      description = TextField()
      recommended_action = TextField()
      data_json = JSONField()  # 根拠データ
      is_read = BooleanField(default=False)
      is_actioned = BooleanField(default=False)
      created_at = DateTimeField(auto_now_add=True)
      expires_at = DateTimeField(null=True)
  ```
- Celeryタスク: `generate_daily_insights` (毎朝6:00実行)
- ダッシュボードにインサイトカード表示（重要度順）
- LINE通知連携（criticalのみ）

### 4-2. 経営KPIスコアカード ✅ Task #34
**概要**: 主要経営指標を1画面でスコア化

| KPI | 計算方法 | 業界ベンチマーク | 目標 |
|-----|---------|-------------|------|
| 原価率 | COGS / 売上 | 28-35% | < 30% |
| 人件費率 | 人件費 / 売上 | 30-40% | < 35% |
| プライムコスト | (原価+人件費) / 売上 | < 65% | < 60% |
| 客単価 | 売上 / 注文数 | 店舗依存 | 前月比+5% |
| テーブル回転率 | 来客数 / 席数 / 営業時間 | 3-4回転 | > 3 |
| リピート率 | 再来店客 / 全客 | 55-70% | > 60% |
| NPS | Promoter% - Detractor% | 30-50 | > 40 |

**実装**:
- 新タブ「経営スコア」を売上ダッシュボードに追加
- ゲージチャート（Chart.js doughnut）で各KPIを表示
- 赤/黄/緑のインジケーター
- 業界ベンチマークとの比較ライン

### 4-3. 顧客満足度トラッキング ✅ Task #35
**概要**: NPS + サービス品質メトリクスの統合管理

**実装**:
- 新モデル: `CustomerFeedback`
  ```python
  class CustomerFeedback(models.Model):
      store = ForeignKey(Store)
      schedule = ForeignKey(Schedule, null=True)  # 予約紐づけ
      order = ForeignKey(Order, null=True)
      nps_score = IntegerField(null=True)  # 0-10
      food_rating = IntegerField(null=True)  # 1-5
      service_rating = IntegerField(null=True)  # 1-5
      ambiance_rating = IntegerField(null=True)  # 1-5
      comment = TextField(blank=True)
      sentiment = CharField(max_length=20, blank=True)  # positive/neutral/negative (自動判定)
      source = CharField(max_length=20)  # qr_survey, line, google_review
      created_at = DateTimeField(auto_now_add=True)
  ```
- QR決済完了後にLINEでアンケート送信（NPS 1問 + 5段階評価3問）
- 感情分析: Gemini API（既存のAIチャットと同じ基盤）でコメント自動分類
- NPS推移チャート + カテゴリ別レーダーチャート

### 4-4. 需要予測ベースの自動発注推奨 ✅ 実装済
**概要**: 来客予測 × メニュー人気度 × 在庫から、発注推奨量を自動計算

- 商品別の日次消費量を予測
- 現在庫 ÷ 日次消費予測 = 在庫日数
- リードタイム（発注〜納品日数）を考慮した発注タイミング提案
- Product モデルに `lead_time_days`, `cost` フィールド追加

---

## Phase 5: データ基盤拡充

### 5-1. Product モデル拡張
```python
# 追加フィールド
cost = DecimalField('原価', max_digits=10, decimal_places=2, null=True, blank=True)
lead_time_days = IntegerField('発注リードタイム(日)', default=1)
food_cost_target = DecimalField('目標原価率(%)', max_digits=5, decimal_places=2, default=30.0)
```

### 5-2. BusinessInsight モデル（新規）
- 自動インサイトの保存・表示・アクション追跡

### 5-3. CustomerFeedback モデル（新規）
- NPS + 多次元評価 + 感情分析

### 5-4. 外部データ連携（将来）
| データソース | 用途 | API |
|------------|------|-----|
| OpenWeatherMap | 天気と売上相関 | 無料枠あり |
| Google Business Profile | レビュー・評価取込 | Google API |
| LINE公式 | 顧客セグメント配信 | LINE Messaging API |

---

## 実装優先順位

| 優先度 | Phase | 機能 | 工数目安 | 価値 | 状態 |
|--------|-------|------|---------|------|------|
| **P0** | 1 | シフト希望カレンダーUI | 中 | 日常業務の効率化 | ✅ Task #26 |
| **P0** | 2-1 | メニューエンジニアリング | 小 | 利益率向上に直結 | ✅ Task #27 |
| **P0** | 4-1 | 自動インサイトエンジン | 中 | 経営判断の自動化 | ✅ Task #33 |
| **P1** | 2-3 | 売上予測 | 中 | 仕入れ・人員計画の最適化 | ✅ Task #29 |
| **P1** | 3-2 | RFM分析 | 小 | リピーター施策の精度向上 | ✅ Task #31 |
| **P1** | 3-1 | コホート分析 | 小 | 離脱タイミング特定 | ✅ Task #31 |
| **P1** | 4-2 | 経営KPIスコアカード | 小 | 経営状態の一目把握 | ✅ Task #34 |
| **P2** | 2-2 | ABC分析 | 小 | 在庫管理効率化 | ✅ Task #28 |
| **P2** | 2-4 | 時間帯別売上ヒートマップ | 小 | ピーク最適化 | ✅ Task #30 |
| **P2** | 2-5 | 客単価トレンド | 小 | アップセル効果測定 | ✅ Task #30 |
| **P2** | 3-3 | マーケットバスケット分析 | 中 | セット提案・メニュー最適化 | ✅ Task #32 |
| **P2** | 4-3 | 顧客満足度 (NPS) | 中 | サービス品質の定量化 | ✅ Task #35 |
| **P3** | 3-4 | 来客予測 | 中 | スタッフ配置の精度向上 | ✅ 実装済 |
| **P3** | 3-5 | CLV | 小 | 長期顧客戦略 | ✅ 実装済 |
| **P3** | 4-4 | 自動発注推奨 | 大 | 食品ロス削減 | ✅ 実装済 |
| **P3** | 5-4 | 外部データ連携 | 大 | 分析精度向上 | ✅ スケルトン実装 |

> **進捗: 16/16 完了 (100%)** 🎉

---

## 分析成熟度モデル

```
現在地 (2026-03-13)
  ↓
Level 3-4 到達済み！

[Level 1] 記述的    ✅ 完了 (売上/来客/シフト/在庫の現状表示)
[Level 2] 診断的    ✅ 完了 (メニューエンジニアリング, ABC, RFM, コホート, バスケット)
[Level 3] 予測的    ✅ 完了 (売上予測, 来客予測 — 移動平均+信頼区間)
[Level 4] 処方的    ✅ 完了 (自動インサイト, KPIスコアカード, NPS, 自動発注推奨)
```

---

## 技術スタック（追加）

| 技術 | 用途 | 備考 |
|------|------|------|
| Prophet (Meta) | 時系列予測 | `pip install prophet` |
| mlxtend | バスケット分析 | `pip install mlxtend` |
| scikit-learn | RFM/クラスタリング | 既にインストール済み |
| Chart.js | 可視化 | 既に使用中 |
| Gemini API | 感情分析/インサイト生成 | ※公開チャット廃止済、管理者チャット一時停止中 |

---

## 参考文献・ベンチマーク

- **Square Analytics 2025**: 会話型AI分析、リアルタイムKPI、人件費最適化
- **Toast Analytics**: メニューパフォーマンス、客単価分析、daypart分析
- **Lightspeed**: メニュー4象限分析(Stars/Puzzles/Plowhorses/Dogs)、テーブル回転率
- **7shifts**: 週間グリッドUI、定期+一時上書きモデル
- **ジョブカン**: モバイルバッチ選択、シフトパターンドロップダウン
- **シフオプ**: 締切リマインダー、複数デバイス対応
- **RFM分析**: Starbucks, Domino's の事例。深層学習統合で解約予測精度99.7%
- **Apriori**: レストラン向けメニュー提案で66%の成功率（学術研究）
- **Prophet**: 12週間の食材需要予測でARIMA超え（Verma et al. 2023）
- **NPS**: レストラン業界平均30、体系的トラッキングで売上7-24%向上
- **CrunchTime 2026**: AIフォーキャスト99%精度、処方的調理指示

---

## セキュリティ・パフォーマンス改善 TODO

> 2026-03-13 コードベース解析で検出された残存課題

### Phase 2: IoTセキュリティ ✅ 完了 (2026-03-13)

| # | 課題 | 対応状況 |
|---|------|---------|
| 1 | Setup AP ハードコードパスワード | ✅ MAC/UID基づく動的生成 (`FUHI-XXXXXX`) |
| 2 | API通信 HTTP → HTTPS | ✅ HTTPS化 (サーバーTLS要設定) |
| 3 | WiFi credentials 平文コミット | ✅ `secrets_template.py` + `.gitignore` |
| 4 | attendance_pin 平文4桁PIN | ✅ `make_password`/`check_password` ハッシュ化 |
| 5 | Watchdogタイマー未実装 | ✅ WDT 60秒タイムアウト追加 |
| 6 | DHT22センサープレースホルダー | ✅ SHT31/DHT20 I2C自動検出実装 |

### Phase 3: パフォーマンス・信頼性 ✅ 完了 (2026-03-13)

| # | 課題 | 対応状況 |
|---|------|---------|
| 1 | N+1クエリ (ダッシュボードAPI) | ✅ `select_related` + annotate最適化 |
| 2 | LINE通知リトライなし | ✅ 指数バックオフ3回リトライ |
| 3 | IoT APIレート制限なし | ✅ `IoTDeviceThrottle` 10req/min |

### Phase 1 セキュリティ修正 ✅ 完了 (2026-03-13)

| # | 課題 | 対応状況 |
|---|------|---------|
| 1 | POS決済 race condition | ✅ `transaction.atomic()` + `select_for_update()` |
| 2 | ダッシュボード入力バリデーション | ✅ `_clamp_int()` 導入 (8箇所) |
| 3 | SwitchBotトークン平文保存 | ✅ Fernet暗号化 + 後方互換 |
| 4 | bare except 多用 | ✅ 30+箇所を具体的例外型に置換 |

### Phase 4: コスト対策 ✅ 完了 (2026-03-13)

| # | 課題 | 対応状況 |
|---|------|---------|
| 1 | GuideChatAPIView 認証なし公開チャット | ✅ 完全廃止 (Gemini APIコストリスク) |
| 2 | AdminChatAPIView レート制限なし | ✅ URL無効化 + レート制限20回/5分追加 (APIキー再発行まで停止) |

---

## 将来構想: SaaS化 (マルチテナント商用サービス)

> 詳細草案: [TODO_SAAS.md](./TODO_SAAS.md)

オンライン申込 → 審査承認 → AWS上にテナント環境自動生成 → `<店名>.timebaibai.com` で利用開始

| プラン | 月額 (税抜) | 対象 | 主要機能 |
|--------|-----------|------|---------|
| ライト | ¥9,800 | 小規模バー・カフェ | POS, 予約, 基本ダッシュボード |
| スタンダード | ¥19,800 | 一般飲食店 | 全機能 (POS/予約/シフト/勤怠/給与/分析) |
| プレミアム | ¥29,800 | 本格運用 | 全機能 + IoT + 高度分析 + EC |
| IoTレンタル | +¥2,980〜3,980 | IoT希望店 | センサーキット貸出 (プレミアムは込み) |
