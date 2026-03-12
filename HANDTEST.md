# HANDTEST.md — NewFUHI 手動テスト手順書

> 自動テストではカバーできない外部連携・実機操作・ブラウザ操作・ダッシュボードUI を対象とした手動テスト手順書。
> 各テスト項目に [PASS] / [FAIL] を記録し、実施日とテスターを記入してください。
>
> **自動テスト**: `pytest` (776テスト) でモデル・ビュー・API・タスク・セキュリティをカバー済み。
> 本書はそれ以外の手動確認が必要な項目をカバーします。

---

## 実施記録

| 実施日 | テスター | 対象セクション | 結果 |
|--------|---------|---------------|------|
|        |         |               |      |

---

## 環境情報

| 環境 | URL | アクセス方法 |
|------|-----|-------------|
| **本番 (EC2)** | `https://timebaibai.com/` | ブラウザ / curl |
| **開発 (Mac)** | `http://localhost:8000/` | `python manage.py runserver 0.0.0.0:8000` |
| **EC2 SSH** | `ubuntu@57.181.0.55` | Instance Connect + SSH |

## 前提条件

### モックデータ投入
```bash
# 開発環境
python manage.py seed_mock_data

# 本番環境 (SSH後)
cd ~/NewFUHI && source .venv/bin/activate
python manage.py seed_mock_data --reset
```

### 開発環境
```bash
cd ~/NewFUHI
python manage.py runserver 0.0.0.0:8000

# Celeryワーカー起動（タスクテスト用）
celery -A celery_config worker -l info &
celery -A celery_config beat -l info &

# Redis起動確認
redis-cli ping  # → PONG
```

### 本番環境 (EC2)
```bash
# SSH接続
ssh -i newfuhi-key.pem ubuntu@57.181.0.55

# サービス状態確認
sudo systemctl status newfuhi newfuhi-celery newfuhi-celerybeat

# ログ確認
sudo journalctl -u newfuhi -f
sudo tail -f /var/log/newfuhi/gunicorn-error.log
```

### 管理画面ログイン
- URL: `/admin/`
- ユーザー: `admin` / 設定済みパスワード
- モックデータ投入後、sidebar に全グループが表示されること

---

## 1. LINE OAuth フロー

**必要環境**: LINE Developersコンソール設定済み、LINE実機アプリ

### 1.1 LINE ログイン → 仮予約作成
- [ ] 1. トップページ (`/`) にアクセス
- [ ] 2. 店舗一覧から店舗を選択
- [ ] 3. 占い師を選択 → カレンダーを表示
- [ ] 4. 空きコマをクリック → 予約確認画面
- [ ] 5. 「LINEで予約」を選択 → LINE OAuth画面にリダイレクト
- [ ] 6. LINEアプリで認証（QRコードまたはメール/パスワード）
- [ ] 7. コールバックURL (`/booking/login/line/success/`) に戻る
- [ ] 8. 仮予約が作成されることを確認 (DB: `Schedule.is_temporary=True`)
- [ ] 9. 有料予約の場合: Coiney決済URLがLINEメッセージで送信される
- [ ] 10. 無料予約の場合: 即座に確定 (`is_temporary=False`) + LINE通知

### 1.2 LINE プロフィール取得
- [ ] LINE user_id が暗号化保存されることを確認 (`line_user_enc` 非空、`line_user_hash` 非空)
- [ ] `get_line_user_id()` で復号できることを管理シェルで確認

### 1.3 エッジケース
- [ ] LINEアプリで認証拒否 → エラーハンドリング
- [ ] state パラメータ不一致 → 400エラー
- [ ] LINE Bot未フレンド → 友だち追加メッセージ

---

## 2. IoTデバイス通信

**必要環境**: Raspberry Pi Pico W + MQ-9/PIR/照度センサー、Wi-Fi接続

### 2.1 センサーデータ送信
- [ ] 1. Pico W をネットワークに接続
- [ ] 2. `POST /api/iot/event/` に以下のペイロードを送信:
  ```json
  {
    "device": "test-device-001",
    "event_type": "sensor",
    "payload": {"mq9": 120.5, "light": 500, "sound": 30, "pir": false}
  }
  ```
  ヘッダー: `X-API-KEY: <生APIキー>`
- [ ] 3. レスポンス 201 を確認
- [ ] 4. `IoTEvent` レコードが作成されることを確認
- [ ] 5. `last_seen_at` が更新されることを確認

### 2.2 デバイス設定取得
- [ ] `GET /api/iot/config/?device=test-device-001` (X-API-KEY ヘッダー付き)
- [ ] レスポンスに `wifi`, `mq9_threshold`, `alert_enabled` が含まれる
- [ ] `pending_ir_command` がある場合、レスポンスに含まれ、送信後クリアされる

### 2.3 IR コード学習・送信
- [ ] event_type="ir_learned" のイベント送信 → `IRCode` レコード自動作成
- [ ] `POST /api/iot/ir/send/` で IR コードキュー → `pending_ir_command` に設定
- [ ] Pico W が次回 config 取得時に IR コマンドを受け取る

### 2.4 APIキー認証
- [ ] 不正な API キー → 404 レスポンス
- [ ] API キー未設定 → 400 レスポンス
- [ ] デバイス名不一致 → 404 レスポンス

---

## 3. ガスアラート E2E フロー

**必要環境**: MQ-9センサー付きPico W、メール送信可能な環境

### 3.1 閾値超過 → アラート生成
- [ ] 1. IoTDevice の `mq9_threshold` を 300 に設定
- [ ] 2. MQ-9 値 350 以上のセンサーデータを送信
- [ ] 3. `event_type="mq9_alarm"` の場合: LINE プッシュ通知が送信される
- [ ] 4. `alert_email` 設定済みの場合: `trigger_gas_alert` タスクでメール送信
- [ ] 5. `PropertyAlert` が作成されることを確認 (alert_type='gas_leak', severity='critical')

### 3.2 アラート解決
- [ ] 管理画面から `PropertyAlert.is_resolved=True` に更新
- [ ] 再度閾値超過 → 新しいアラートが作成される（重複防止解除）

### 3.3 換気扇自動制御 (VentilationAutoControl)
- [ ] 1. 管理画面で VentilationAutoControl ルールを作成（IoTDevice、閾値、SwitchBotクレデンシャル設定）
- [ ] 2. MQ-9 値を ON閾値以上で連続送信 (consecutive_count回)
- [ ] 3. SwitchBot API で turnOn が呼ばれることを確認（Djangoログ）
- [ ] 4. fan_state が 'on' に更新されること
- [ ] 5. MQ-9 値を OFF閾値以下に送信 → turnOff が呼ばれ fan_state='off'
- [ ] 6. クールダウン期間中は切り替えが発生しないこと

### 3.4 物件監視タスク (check_property_alerts)
- [ ] Celery Beat で5分ごと実行確認
- [ ] ガス漏れ検知: 直近5分の高MQ-9 → critical アラート
- [ ] 長期不在検知: PIR 3日以上未検知 → warning アラート
- [ ] デバイスオフライン: last_seen_at 30分超過 → info アラート

---

## 4. Coiney 決済

**必要環境**: Coineyサンドボックスアカウント、テストカード番号

### 4.1 予約決済フロー
- [ ] 1. 有料占い師の予約を作成（price >= 100）
- [ ] 2. LINE または メール経由で決済URL受信
- [ ] 3. 決済URL にアクセス → Coiney 決済画面表示
- [ ] 4. テストカード番号で決済
  - Visa: `4242 4242 4242 4242`
  - 期限: 将来の日付、CVV: 任意3桁
- [ ] 5. Webhook `POST /coiney_webhook/<orderId>/` が受信される
- [ ] 6. `Schedule.is_temporary` が `False` に更新
- [ ] 7. QRコード画像が生成される (`checkin_qr`)
- [ ] 8. スタッフ・顧客にLINE通知送信

### 4.2 Webhook 署名検証
- [ ] `COINEY_WEBHOOK_SECRET` 設定時: 署名不一致 → 403
- [ ] 正しい署名 → 200 (決済処理実行)

### 4.3 テーブル注文決済
- [ ] テーブル注文のお会計 → Coiney 決済画面
- [ ] 決済成功 → 注文ステータス CLOSED
- [ ] 現金選択 → 即座に CLOSED

---

## 5. QR コードスキャン

### 5.1 予約チェックイン QR
- [ ] 1. 確定済み予約の QR コード画像を表示 (`/booking/reservation/<reservation_number>/`)
- [ ] 2. スタッフがスキャン画面 (`/booking/checkin/scan/`) を開く
- [ ] 3. QR コードをスキャン
- [ ] 4. `POST /booking/api/checkin/` で `reservation_number` 送信
- [ ] 5. `Schedule.is_checked_in=True`, `checked_in_at` が記録
- [ ] 6. 2回目のスキャン → 「すでにチェックイン済み」メッセージ

### 5.2 テーブル注文 QR
- [ ] 1. 管理画面でテーブル/席を作成 → QR コード生成
- [ ] 2. QR コードをスキャン → テーブル注文メニュー (`/t/<table_uuid>/`)
- [ ] 3. 商品をカートに追加 → 注文確定
- [ ] 4. 注文がキッチン画面に表示される

### 5.3 入庫 QR
- [ ] スタッフが入庫 QR 画面 (`/booking/stock/inbound/`) を開く
- [ ] 商品コード (SKU) をスキャンまたは入力
- [ ] 数量を入力 → 在庫が加算される

---

## 6. Email OTP 認証

### 6.1 メール予約フロー
- [ ] 1. 予約確認画面で「メールで予約」を選択
- [ ] 2. 名前とメールアドレスを入力
- [ ] 3. 6桁の OTP がメールで送信される（10分有効）
- [ ] 4. OTP を入力 → 認証成功
- [ ] 5. 仮予約が作成される
- [ ] 6. 決済URLがメールで送信される

### 6.2 エッジケース
- [ ] 誤った OTP → エラーメッセージ
- [ ] 期限切れ OTP → 「有効期限が切れています」
- [ ] メール送信失敗 → エラーメッセージ表示

---

## 7. 管理画面 UI 基本

**テストURL**: `/admin/`

### 7.1 ロール別メニュー表示
- [ ] **superuser**: 全モデル表示（16グループ）
- [ ] **developer** (is_developer=True): 全モデル + デバッグパネル
- [ ] **manager** (is_store_manager=True): シフト管理 + 給与 + 在庫 (31モデル)
- [ ] **staff**: 自分のシフト・予約のみ (6モデル)
- [ ] **IoTメニュー非表示**: サイドバーに「IoT管理」グループが表示されないこと（Bug #25 修正済み）

### 7.2 AIチャットアシスタント
- [ ] 管理画面にAIチャットウィジェット表示 (SiteSettings.show_ai_chat=True)
- [ ] 質問入力 → Gemini API経由で回答取得
- [ ] ナレッジベースに基づく回答であることを確認
- [ ] 会話履歴の保持（最大10ターン）

### 7.3 テーマカスタマイズ
- [ ] AdminTheme でメインカラー変更 → 管理画面に反映
- [ ] ヘッダー画像アップロード → 表示確認
- [ ] ダークモード切り替え

---

## 8. 売上ダッシュボード

**テストURL**: `/admin/dashboard/sales/`

**前提**: モックデータ投入済み（90日分の注文・予約データ）

### 8.1 KPI表示
- [ ] 「本日の売上」が表示される（金額が0でないこと）
- [ ] 「本日の注文数」が表示される
- [ ] 「本日の予約数」が表示される
- [ ] 「本日のキャンセル数」が表示される

### 8.2 予約統計API (`/api/dashboard/reservations/`)
- [ ] レスポンス200、JSON形式
- [ ] `today_count`, `week_count`, `month_count` が含まれる
- [ ] `cancel_rate` がパーセンテージで表示される
- [ ] **期待値**: 90日分の予約データ（約508件）に基づく数値

### 8.3 売上統計API (`/api/dashboard/sales/`)
- [ ] `today_revenue`, `week_revenue`, `month_revenue` が含まれる
- [ ] グラフ用データ（日別売上推移）が返される
- [ ] **期待値**: 90日分の注文（約516件）の売上集計

### 8.4 スタッフパフォーマンスAPI (`/api/dashboard/staff-performance/`)
- [ ] 各スタッフの予約数・売上が表示される
- [ ] ランキング順に並んでいること

### 8.5 シフトサマリーAPI (`/api/dashboard/shift-summary/`)
- [ ] 今日のシフト割当数が表示される
- [ ] 空きシフト数が表示される

### 8.6 在庫アラートAPI (`/api/dashboard/low-stock/`)
- [ ] 在庫閾値割れ商品リストが返される
- [ ] **期待値**: 4商品（モックデータで意図的に在庫不足に設定）
- [ ] 商品名・現在庫数・閾値が含まれる

### 8.7 ダッシュボードレイアウト
- [ ] ウィジェットのドラッグ&ドロップで位置変更可能
- [ ] レイアウト変更がDB (`DashboardLayout`) に保存される
- [ ] ページリロード後もレイアウトが保持される

### 8.8 メニューエンジニアリング マトリクス（Task #27 新規）

**テストURL**: `/admin/dashboard/sales/` → 売上タブ → 「メニュー分析」サブタブ

**API**: `GET /api/dashboard/menu-engineering/?days=90`

- [ ] 売上タブに「メニュー分析」サブタブが表示される
- [ ] サブタブクリックでScatter chart（散布図）が表示される
- [ ] X軸=販売数量（人気度）、Y軸=利益率(%)
- [ ] 4象限の色分け: Star(緑)、Plowhorse(青)、Puzzle(橙)、Dog(赤)
- [ ] 凡例にStar/Plowhorse/Puzzle/Dogが表示される
- [ ] ホバーで商品名・販売数・利益率がツールチップ表示
- [ ] 散布図の下に商品一覧テーブルが表示される
- [ ] テーブル列: 商品名、販売数、利益率、売上、分類（バッジ付き）
- [ ] APIレスポンスに `avg_popularity`, `avg_margin` が含まれる
- [ ] データ無し時はデモデータで表示される

### 8.9 ABC分析（パレート）（Task #28 新規）（パレート）（Task #28 新規）

**テストURL**: `/admin/dashboard/sales/` → 売上タブ → 「ABC分析」サブタブ

**API**: `GET /api/dashboard/abc-analysis/?days=90`

- [ ] 売上タブに「ABC分析」サブタブが表示される
- [ ] サブタブクリックでパレート図（棒グラフ+累積折れ線）が表示される
- [ ] 棒グラフ: 商品別売上（降順）、色分け A=緑, B=橙, C=灰
- [ ] 折れ線: 累積構成比（右軸 0-100%）
- [ ] 凡例に A(上位80%), B(80-95%), C(95-100%) が表示される
- [ ] グラフの下に商品一覧テーブルが表示される
- [ ] テーブル列: 商品名、売上、構成比、累積、ランク（バッジ付き）
- [ ] APIレスポンスに `total_revenue` が含まれる
- [ ] データ無し時はデモデータで表示される

### 8.10 売上予測（Task #29 新規）

**テストURL**: `/admin/dashboard/sales/` → 売上タブ → 「売上予測」サブタブ

**API**: `GET /api/dashboard/forecast/?days=14`

- [ ] 売上タブに「売上予測」サブタブが表示される
- [ ] サブタブクリックで折れ線グラフが表示される
- [ ] 実績線（緑）と予測線（紫・破線）が表示される
- [ ] 予測の信頼区間（薄紫の帯）が表示される
- [ ] 使用手法が右上にバッジ表示（移動平均+曜日係数 or Prophet）
- [ ] APIレスポンスに `historical`, `forecast`, `method` が含まれる
- [ ] forecast各要素に `date`, `predicted`, `lower`, `upper` が含まれる
- [ ] `lower <= predicted <= upper` が成り立つ
- [ ] データ無し時はデモデータで表示される

### 8.11 時間帯別売上ヒートマップ（Task #30 新規）

**テストURL**: `/admin/dashboard/sales/` → 売上タブ → 「時間帯別売上」サブタブ

**API**: `GET /api/dashboard/sales-heatmap/?days=90`

- [ ] 売上タブに「時間帯別売上」サブタブが表示される
- [ ] サブタブクリックでバブルチャート（ヒートマップ）が表示される
- [ ] X軸が時間帯（0時〜23時）、Y軸が曜日（日〜土）
- [ ] バブルサイズが売上に比例する
- [ ] バブルの色の濃さが売上額に応じて変化する
- [ ] ツールチップに「曜日 時間帯 — 売上金額 / 注文件数」が表示される
- [ ] APIレスポンスの `heatmap` が168件（7曜日×24時間）
- [ ] 各セルに `weekday`, `hour`, `revenue`, `orders` が含まれる
- [ ] データ無し時はデモデータで表示される

### 8.12 客単価（AOV）推移（Task #30 新規）

**テストURL**: `/admin/dashboard/sales/` → 売上タブ → 「客単価推移」サブタブ

**API**: `GET /api/dashboard/aov-trend/?period=daily`

- [ ] 売上タブに「客単価推移」サブタブが表示される
- [ ] サブタブクリックで客単価の折れ線＋注文数の棒グラフが表示される
- [ ] 右上のセレクトで日別/週別/月別を切替できる
- [ ] 切替時にチャートが再描画される
- [ ] 左Y軸が客単価（円）、右Y軸が注文数
- [ ] APIレスポンスに `trend` と `period` が含まれる
- [ ] trend各要素に `date`, `order_count`, `total_revenue`, `aov` が含まれる
- [ ] `aov` = `total_revenue` / `order_count` （四捨五入）が成り立つ
- [ ] データ無し時はデモデータで表示される

### 8.13 コホート分析（Task #31 新規）

**テストURL**: `/admin/dashboard/sales/` → 顧客タブ → 「コホート分析」サブタブ

**API**: `GET /api/dashboard/cohort/?months=6`

- [ ] 顧客タブに「コホート分析」サブタブが表示される
- [ ] サブタブクリックでコホートリテンションテーブルが表示される
- [ ] 各行がコホート月（初回来店月）を表す
- [ ] 列ヘッダーに M+0, M+1, M+2... が表示される
- [ ] M+0 のセルが100%（全顧客がその月にアクティブ）
- [ ] セルの背景色がリテンション率に比例して濃くなる
- [ ] APIレスポンスに `cohorts` 配列が含まれる
- [ ] 各コホートに `cohort`, `size`, `retention` が含まれる
- [ ] データ無し時はデモデータで表示される

### 8.14 RFMセグメンテーション（Task #31 新規）

**テストURL**: `/admin/dashboard/sales/` → 顧客タブ → 「RFM分析」サブタブ

**API**: `GET /api/dashboard/rfm/?days=365`

- [ ] 顧客タブに「RFM分析」サブタブが表示される
- [ ] バブルチャートが表示される（X=Frequency, Y=Recency, サイズ=Monetary）
- [ ] セグメントごとに色分けされる（Champion=緑, Loyal=青, At Risk=黄, Lost=赤 等）
- [ ] 凡例にセグメント名が表示される
- [ ] チャート下にセグメント別カード（人数）が表示される
- [ ] APIレスポンスに `customers`, `segments`, `total_customers` が含まれる
- [ ] 各顧客に `r_score`, `f_score`, `m_score`, `rfm_score`, `segment` が含まれる
- [ ] RFMスコアが1-5の範囲内
- [ ] セグメントが定義済みの名前のいずれか（champion, loyal, new, potential, at_risk, cant_lose, lost, other）
- [ ] データ無し時はデモデータで表示される

### 8.15 バスケット分析（Task #32 新規）

**テストURL**: `/admin/dashboard/sales/` → 顧客タブ → 「バスケット分析」サブタブ

**API**: `GET /api/dashboard/basket/?days=90`

- [ ] 顧客タブに「バスケット分析」サブタブが表示される
- [ ] サブタブクリックで併売ルールの表が表示される
- [ ] 各行に前提商品 → 結論商品 の形式で表示される
- [ ] Support（支持度）、Confidence（信頼度）、Lift（リフト値）が表示される
- [ ] Confidence列にバー表示がある
- [ ] Liftが高い順に並んでいる
- [ ] Lift >= 2.0 のルールが緑色のフォントで強調される
- [ ] 使用手法がバッジ表示される（Apriori or ペアワイズ分析）
- [ ] 対象トランザクション数が表示される
- [ ] データ無し時はデモデータで表示される

---

### 8.16 ビジネスインサイト（Task #33 新規）

**テストURL**: `/admin/dashboard/sales/` → 概要タブ → 「インサイト」サブタブ

**API**: `GET /api/dashboard/insights/`, `POST /api/dashboard/insights/`

- [ ] 概要タブに「インサイト」サブタブが表示される
- [ ] 未読インサイト数がバッジとして表示される
- [ ] サブタブクリックでインサイト一覧が表示される
- [ ] 各インサイトにカテゴリ（売上/在庫/スタッフ/顧客）が表示される
- [ ] 重要度バッジが表示される（重要=赤, 注意=黄, 情報=青）
- [ ] 「既読にする」ボタンで個別のインサイトを既読にできる
- [ ] 「すべて既読」ボタンですべてのインサイトを既読にできる
- [ ] 「分析実行」ボタンで新しいインサイトが生成される
- [ ] 既読インサイトは半透明で表示される
- [ ] ?unread=1 パラメータで未読のみフィルタされる
- [ ] 管理画面（/admin/booking/businessinsight/）でインサイト一覧が確認できる
- [ ] インサイトが作成日時の降順で表示される

### 8.17 KPIスコアカード（Task #34 新規）

**テストURL**: `/admin/dashboard/sales/` → 概要タブ → 「KPIスコアカード」サブタブ

**API**: `GET /api/dashboard/kpi-scorecard/`

- [ ] 概要タブに「KPIスコアカード」サブタブボタンが表示される
- [ ] サブタブクリックでKPIカード一覧が表示される
- [ ] 客単価（AOV）カードが表示される（円単位）
- [ ] 売上合計カードが表示される
- [ ] 注文数カードが表示される
- [ ] リピート率カードが表示される（%、ステータス色付き）
- [ ] キャンセル率カードが表示される（%、ステータス色付き）
- [ ] 回転率カードが表示される（回/日）
- [ ] 原価率カードが表示される（%）
- [ ] ステータス表示: 良好=緑, 注意=黄, 要改善=赤
- [ ] 基準値（ベンチマーク）が各カードに表示される
- [ ] ?days=7 パラメータで期間変更が反映される

### 8.18 NPS・顧客満足度（Task #35 新規）

**テストURL**: `/admin/dashboard/sales/` → 顧客分析タブ → 「NPS・満足度」サブタブ

**API**: `GET /api/dashboard/nps/`, `GET/POST /api/dashboard/feedback/`

- [ ] 顧客分析タブに「NPS・満足度」サブタブボタンが表示される
- [ ] NPSスコアが大きく表示される（色: 50以上=緑, 0以上=黄, マイナス=赤）
- [ ] 推奨者・中立者・批判者の人数が表示される
- [ ] 回答数が表示される
- [ ] カテゴリ別評価レーダーチャートが表示される（料理/サービス/雰囲気）
- [ ] NPS推移折れ線チャートが表示される
- [ ] 最新フィードバック一覧が表示される（NPS、評価、コメント）
- [ ] POST /api/dashboard/feedback/ で認証なしでフィードバック送信できる
- [ ] NPS 0-10範囲外の送信がバリデーションエラーになる
- [ ] 管理画面（/admin/booking/customerfeedback/）でフィードバック一覧が確認できる
- [ ] フィードバックの感情分析が自動設定される（NPS 9-10→positive, 7-8→neutral, 0-6→negative）

### 8.19 操作チュートリアル（Task #36 新規）

**テストURL**: `/admin/dashboard/sales/`

- [ ] 初回アクセス時にチュートリアルが自動表示される
- [ ] タブナビゲーションがハイライトされて説明が表示される
- [ ] 「次へ」ボタンで次のステップに進める
- [ ] 「戻る」ボタンで前のステップに戻れる
- [ ] 「閉じる」ボタンでチュートリアルを終了できる
- [ ] ステップ数が「N / 7」形式で表示される
- [ ] 各タブへの自動遷移（売上タブ、顧客タブなど）が動作する
- [ ] 「? ガイド」ボタンをクリックするといつでもチュートリアルを再開できる
- [ ] 2回目以降のアクセスではチュートリアルが自動表示されない（LocalStorage）
- [ ] LocalStorageの `dashboard_tour_seen` を削除するとチュートリアルが再表示される

---

## 9. 来客分析ダッシュボード

**テストURL**: `/admin/analytics/visitors/`

**前提**: モックデータ投入済み（90日分の来客データ、約1,350件）

### 9.1 KPI表示
- [ ] 「今日の来客数」が表示される
- [ ] 「今日の注文数」が表示される
- [ ] 数値が0でないこと（モックデータにより今日分のデータがある）

### 9.2 来客推移チャート
- [ ] 棒グラフが表示される（Chart.js）
- [ ] 期間切り替え: 1週間 / 2週間 / 1ヶ月 / 3ヶ月
- [ ] 「来客数」と「注文数」の2つのデータセットが表示される
- [ ] `/api/analytics/visitors/?range=7` でJSON取得確認

### 9.3 曜日×時間ヒートマップ
- [ ] 7行（月〜日）×13列（9時〜21時）のマトリックス表示
- [ ] 色の濃さが来客数に比例していること
- [ ] ホバーで「○人」のツールチップが表示される
- [ ] `/api/analytics/heatmap/` でJSON取得確認

### 9.4 店舗切り替え
- [ ] 店舗プルダウンで店舗切り替え → データが更新される
- [ ] URLに `?store_id=<id>` が付加される

---

## 10. AI推薦ダッシュボード

**テストURL**: `/admin/ai/recommendation/`

**前提**: モックデータ投入済み（学習済みモデル1件、推薦結果210件）

### 10.1 モデル情報表示
- [ ] 「アクティブ」ステータス（緑ドット）が表示される
- [ ] モデル種別: `lightgbm` と表示
- [ ] MAE: `1.230` 付近の値
- [ ] 学習サンプル数: `500`
- [ ] 学習日時が表示される

### 10.2 特徴量重要度チャート
- [ ] 横棒グラフ (Chart.js) が表示される
- [ ] `/api/ai/recommendations/` から factors を取得して描画
- [ ] ラベル例: hour_of_day, day_of_week, is_holiday 等

### 10.3 今週の推薦テーブル
- [ ] 7日×12時間（9〜20時）のテーブルが表示される
- [ ] 各セルに推薦スタッフ数（1〜5）が表示される
- [ ] 推薦2未満のセルが赤背景、2以上が緑背景

### 10.4 モデル再学習
- [ ] 「モデル再学習」ボタンが表示される
- [ ] クリック → 確認ダイアログ
- [ ] `/api/ai/train/` にPOST送信される
- [ ] 完了後、モデル情報が更新される

### 10.5 モデル状態API (`/api/ai/model-status/`)
- [ ] `has_model: true` が返される
- [ ] `model_type`, `mae_score`, `training_samples` が含まれる

---

## 11. シフトカレンダー

**テストURL**: `/admin/shift/calendar/`

**前提**: モックデータ投入済み（ShiftPeriod、ShiftAssignment）

### 11.1 週間グリッド表示
- [ ] `/api/shift/week-grid/` でグリッドデータ取得
- [ ] 7日 × 各時間帯のシフト割当が表示される
- [ ] スタッフ名・時間帯が正しく表示される

### 11.2 シフト操作
- [ ] セルクリック → 詳細パネル表示
- [ ] `/api/shift/detail/<pk>/` で詳細取得
- [ ] シフト割当の追加（POST `/api/shift/assignments/`）
- [ ] シフト割当の削除（DELETE `/api/shift/assignments/<pk>/`）

### 11.3 テンプレート適用
- [ ] テンプレート一覧取得 (`/api/shift/templates/`)
- [ ] テンプレート適用 (`/api/shift/apply-template/`)
- [ ] 適用後、カレンダーに反映される

### 11.4 シフト公開
- [ ] 「公開」ボタン → `/api/shift/publish/` POST
- [ ] ShiftPublishHistory レコード作成確認
- [ ] 公開済みシフトの編集不可（または警告表示）

### 11.5 自動スケジュール
- [ ] 「自動割当」ボタン → `/api/shift/auto-schedule/` POST
- [ ] リクエスト・制約に基づいた割当が生成される

### 11.6 スタッフ向けシフト希望カレンダーUI（Task #26 新規）
**テストURL**: `/shift/<period_id>/submit/`
- [ ] 月間カレンダーグリッドが表示される
- [ ] テンプレートチップ（早番/遅番/フル/休み）が表示される
- [ ] テンプレート選択 → 日付セルクリック → 選択状態が視覚的に反映
- [ ] 複数日を連続クリックで一括選択可能
- [ ] 「一括保存」ボタン → `POST /api/shift/requests/<period_id>/bulk/`
- [ ] 保存後、カレンダー上に登録済みシフトが色付きで表示される
- [ ] 「前週コピー」ボタン → `POST /api/shift/requests/<period_id>/copy-week/`
- [ ] 「選択解除」ボタンで未保存の選択がクリアされる
- [ ] 既存の登録済みシフト希望がカレンダー上に正しく表示される
- [ ] 営業時間外のエントリがバリデーションエラーになる
- [ ] 締切済み期間では入力不可（400エラー）

---

## 12. POS システム

**テストURL**: `/admin/pos/`

**前提**: モックデータ投入済み（オープンオーダー3件: ORDERED/PREPARING/SERVED）

### 12.1 画面表示
- [ ] POS画面が正しく表示される
- [ ] 商品カテゴリ一覧が表示される
- [ ] 各カテゴリの商品が表示される（名前・価格）

### 12.2 注文作成
- [ ] 商品タップ → カートに追加
- [ ] 数量変更可能
- [ ] 合計金額が正しく計算される

### 12.3 注文送信
- [ ] 「注文」ボタン → `POST /api/pos/order-items/`
- [ ] Order レコード作成（status=ORDERED）
- [ ] キッチンディスプレイに即時反映

### 12.4 会計
- [ ] 「お会計」ボタン → `POST /api/pos/checkout/`
- [ ] 現金: Order.status → CLOSED
- [ ] カード: Coiney決済URL生成
- [ ] POSTransaction レコード作成確認

### 12.5 オーダー一覧
- [ ] `/api/pos/orders/` で本日のオーダー取得
- [ ] **期待値**: モックデータの3件オープンオーダー + 本日のクローズオーダー
- [ ] ステータス (ORDERED / PREPARING / SERVED / CLOSED) が正しく表示

---

## 13. キッチンディスプレイ

**テストURL**: `/admin/pos/kitchen/`

**前提**: モックデータ投入済み（オープンオーダー3件）

### 13.1 画面表示
- [ ] 未調理注文がカード形式で表示される
- [ ] **期待値**: 3件のオープンオーダー（ORDERED/PREPARING/SERVED 各1件）
- [ ] 各カードに注文番号・商品名・数量・テーブル名が表示される
- [ ] ステータスにより色分けされている

### 13.2 ステータス更新
- [ ] ORDERED → PREPARING: 「調理開始」ボタン → `PUT /api/pos/order-item/<pk>/status/`
- [ ] PREPARING → SERVED: 「提供済み」ボタン
- [ ] ステータス変更が即時反映（AJAX）

### 13.3 自動更新（Bug #24 修正済み）
- [ ] 5秒ごとに HTMX auto-refresh が実行される
- [ ] 自動更新後もカード形式の表示が維持される（JSON表示にならない）
- [ ] 新しい注文がPOSから入った場合、自動でキッチンに表示される
- [ ] ステータス変更ボタンが自動更新後も正常に動作する
- [ ] **確認方法**: 別タブでPOSから注文 → キッチン画面が5秒以内に更新される

---

## 14. 出退勤管理

### 14.1 PIN打刻 (`/admin/attendance/pin/`)
- [ ] PIN入力画面が表示される
- [ ] スタッフのPINコード（4桁）を入力
- [ ] 「出勤」ボタン → `POST /api/attendance/pin-stamp/` (type=clock_in)
- [ ] 「退勤」ボタン → `POST /api/attendance/pin-stamp/` (type=clock_out)
- [ ] 打刻成功メッセージ表示
- [ ] AttendanceStamp レコード作成確認
- [ ] **期待値**: モックデータにより本日3名分のclock_inスタンプが既存

### 14.2 QR打刻 (`/admin/attendance/qr/`)
- [ ] TOTP QRコードが表示される
- [ ] 30秒ごとにコードが更新される
- [ ] `POST /api/attendance/stamp/` でTOTPコード送信
- [ ] 正しいTOTPコード → 打刻成功
- [ ] 不正なコード → エラー

### 14.3 出退勤ボード (`/admin/attendance/board/`)
- [ ] 本日のスタッフ出退勤状況が一覧表示される
- [ ] `/api/attendance/day-status/` でステータスJSON取得
- [ ] **期待値**: 3名が「出勤中」と表示される（モックデータ）
- [ ] 出勤時刻が正しく表示される
- [ ] 未出勤スタッフも表示される

---

## 15. 給与管理

**テストURL**: 管理画面 → 給与管理 → PayrollPeriod

**前提**: モックデータ投入済み（2期間: 先月confirmed、先々月paid）

### 15.1 給与期間一覧
- [ ] PayrollPeriod 一覧に2件表示される
- [ ] ステータス: 1件 `confirmed`、1件 `paid`
- [ ] 給与期間の開始・終了日が正しい

### 15.2 給与計算
- [ ] PayrollPeriod の「Run payroll calculation」アクション実行
- [ ] PayrollEntry が各スタッフ分生成される
- [ ] 基本給・残業代・控除額が計算される
- [ ] PayrollDeduction が雇用保険・所得税として作成される

### 15.3 給与明細 (PayrollEntry)
- [ ] 各エントリに基本時給 × 勤務時間 = 基本給 が表示
- [ ] 残業手当（1.25倍）が計算されている
- [ ] 控除一覧 (PayrollDeduction) がインラインで表示

### 15.4 ZENGIN CSV エクスポート
- [ ] 「Export ZENGIN CSV」アクション実行
- [ ] CSVファイルがダウンロードされる
- [ ] 銀行コード・支店コード・口座番号が正しいフォーマット

### 15.5 支払処理
- [ ] 「Mark as paid」アクション実行
- [ ] PayrollPeriod.status → 'paid'
- [ ] PayrollEntry.status → 'paid'
- [ ] paid_at に日時が記録される

---

## 16. IoTセンサーダッシュボード

**テストURL**: `/admin/iot/sensors/`

**前提**: モックデータ投入済み（IoTDevice + IoTEvent）

### 16.1 MQ-9グラフ
- [ ] CO（MQ-9）のリアルタイムグラフが表示される
- [ ] `/api/iot/sensors/data/` からデータ取得
- [ ] X軸: 時刻、Y軸: ADC値（0〜65535）
- [ ] 閾値ラインが表示される（赤の破線）

### 16.2 PIRイベント
- [ ] PIR検知イベント一覧が表示される
- [ ] `/api/iot/sensors/pir-events/` からデータ取得

### 16.3 PIRステータス
- [ ] `/api/iot/sensors/pir-status/` で最新ステータス取得
- [ ] 検知中/未検知の状態表示

### 16.4 自動更新
- [ ] IoTイベント一覧 (`/admin/booking/iotevent/`) が30秒ごとに自動リロード
- [ ] IoTEvent の一覧に mq9, light, pir の各値が表示される

---

## 17. 在庫管理

**テストURL**: 管理画面 → 在庫管理 → Product

**前提**: モックデータ投入済み（8カテゴリ、30+商品、4品が在庫不足）

### 17.1 商品一覧
- [ ] 全商品がカテゴリ別に表示される
- [ ] 在庫数・SKU・価格が正しく表示される
- [ ] EC表示フラグの表示確認

### 17.2 在庫アクション
- [ ] 「Stock in (+1)」アクション → 在庫+1
- [ ] 「Stock out (-1)」アクション → 在庫-1
- [ ] 「Stock adjust to zero」アクション → 在庫0
- [ ] 「Clear low stock notification」アクション実行

### 17.3 在庫不足アラート
- [ ] **期待値**: 4商品が在庫閾値割れ（low_stock_threshold設定済み）
- [ ] ダッシュボードの在庫アラートウィジェットに表示される
- [ ] Celeryタスク `check_low_stock_and_notify` でLINE通知（1時間ごと）

### 17.4 EC商品表示
- [ ] 「Enable EC visibility」アクション → is_ec_visible=True
- [ ] ECショップ (`/shop/`) に商品が表示される
- [ ] 「Disable EC visibility」アクション → ECから非表示

---

## 18. テーブル注文フロー

### 18.1 テーブルQR
- [ ] 管理画面 → テーブル席 → QRコード生成アクション
- [ ] QRコードZIPダウンロード
- [ ] QRをスキャン → `/t/<table_uuid>/` に遷移

### 18.2 注文フロー（顧客側）
- [ ] `/t/<table_uuid>/` でメニュー表示
- [ ] カテゴリ別商品一覧
- [ ] カートに追加 (`POST /api/table/<id>/cart/add/`)
- [ ] カート確認 → 注文確定 (`POST /api/table/<id>/order/create/`)
- [ ] 注文履歴表示 (`GET /t/<id>/history/`)

### 18.3 キッチン連携
- [ ] テーブル注文がキッチンディスプレイに即時表示
- [ ] テーブル番号が注文に紐づいている

### 18.4 お会計
- [ ] `/t/<table_uuid>/checkout/` で会計画面
- [ ] 合計金額が正しい
- [ ] 決済方法選択（現金/カード）

---

## 19. ECショップ

**テストURL**: `/shop/`

### 19.1 商品表示
- [ ] EC表示設定済み商品が一覧表示される
- [ ] 商品画像・名前・価格が表示される
- [ ] カテゴリフィルタが機能する

### 19.2 カート操作
- [ ] カートに追加 (`POST /api/shop/cart/add/`)
- [ ] カート更新 (`POST /api/shop/cart/update/`)
- [ ] カートから削除 (`POST /api/shop/cart/remove/`)
- [ ] カート画面で合計金額が正しい

### 19.3 チェックアウト
- [ ] `/shop/checkout/` で決済画面表示
- [ ] Coiney決済URL生成（カード）
- [ ] 決済完了 → Order.status=CLOSED

---

## 20. 多言語対応 (i18n)

対応言語: ja, en, zh-hant, zh-hans, ko, es, pt

### 20.1 言語切り替え
- [ ] `?lang=en` パラメータで英語表示に切り替わる
- [ ] `?lang=zh-hant` で繁体字中国語表示
- [ ] 店舗のデフォルト言語設定が反映される
- [ ] 商品名・説明が `ProductTranslation` から取得される

### 20.2 翻訳データ確認
- [ ] 翻訳が存在しない言語 → デフォルト (ja) にフォールバック
- [ ] 全言語で商品メニューが正しく表示される

---

## 21. Celery タスク動作確認

**前提**: Celery ワーカー + Beat 稼働中

### 21.1 定期タスク
| タスク | スケジュール | 確認方法 |
|-------|------------|---------|
| `delete_temporary_schedules` | 毎分 | 10分超の仮予約が削除される |
| `check_low_stock_and_notify` | 1時間ごと | 在庫閾値割れ商品のLINE通知 |
| `check_property_alerts` | 5分ごと | 物件アラート自動生成 |
| `run_security_audit` | 毎日03:00 | SecurityAudit レコード作成 |
| `cleanup_security_logs` | 毎週日曜04:00 | 90日超ログ削除 |
| `check_aws_costs` | 毎日06:00 | CostReport レコード作成 |

### 21.2 手動タスク実行
```bash
python manage.py shell
>>> from booking.tasks import check_property_alerts
>>> check_property_alerts()
```

### 21.3 タスクエラーハンドリング
- [ ] 外部サービス障害時にタスクがクラッシュしないことを確認
- [ ] ログにエラー詳細が記録されることを確認

---

## 22. ブラウザ互換性

### 22.1 モバイルブラウザ
| ブラウザ | トップページ | 予約フロー | テーブル注文 | ECショップ |
|---------|------------|-----------|------------|-----------|
| iOS Safari | [ ] | [ ] | [ ] | [ ] |
| iOS Chrome | [ ] | [ ] | [ ] | [ ] |
| Android Chrome | [ ] | [ ] | [ ] | [ ] |

### 22.2 デスクトップブラウザ
| ブラウザ | 管理画面 | ダッシュボード | POS | キッチン |
|---------|---------|-------------|-----|---------|
| Chrome (最新) | [ ] | [ ] | [ ] | [ ] |
| Firefox (最新) | [ ] | [ ] | [ ] | [ ] |
| Safari (最新) | [ ] | [ ] | [ ] | [ ] |
| Edge (最新) | [ ] | [ ] | [ ] | [ ] |

### 22.3 レスポンシブデザイン
- [ ] 375px (iPhone SE) でレイアウト崩れなし
- [ ] 768px (iPad) でレイアウト崩れなし
- [ ] 1920px (デスクトップ) でレイアウト崩れなし

---

## 23. 本番デプロイ検証

### 23.1 SSL/HTTPS
- [ ] `curl -I https://timebaibai.com/` → HTTP/2 200
- [ ] `http://timebaibai.com/` → HTTPS に自動リダイレクト (301)
- [ ] SSL証明書が有効期限内: `sudo certbot certificates`
- [ ] セキュリティヘッダー確認:
  ```bash
  curl -sI https://timebaibai.com/ | grep -E "X-Frame|X-Content|Strict-Transport"
  ```

### 23.2 systemd サービス
- [ ] Gunicorn: `sudo systemctl is-active newfuhi` → active
- [ ] Celery Worker: `sudo systemctl is-active newfuhi-celery` → active
- [ ] Celery Beat: `sudo systemctl is-active newfuhi-celerybeat` → active
- [ ] 自動復旧テスト: `sudo kill $(pgrep -f gunicorn)` → 5秒後に自動再起動
- [ ] OS再起動後の自動起動: `sudo reboot` → 全サービス自動開始

### 23.3 ファイアウォール (UFW)
- [ ] `sudo ufw status` → active
- [ ] SSH (22), HTTP (80), HTTPS (443) のみ許可
- [ ] その他のポート拒否

### 23.4 Fail2ban (SSH保護)
- [ ] `sudo fail2ban-client status sshd` → 稼働中
- [ ] 連続SSH失敗でIP自動BAN確認

### 23.5 Nginx
- [ ] `sudo nginx -t` → syntax is ok
- [ ] static ファイル配信確認
- [ ] IoT APIレート制限: 10r/s burst=20 が適用されている

### 23.6 S3バックアップ
- [ ] 手動バックアップ実行:
  ```bash
  /bin/bash -lc '/home/ubuntu/NewFUHI/scripts/backup_to_s3.sh'
  echo $?  # → 0
  ```
- [ ] S3にDBバックアップが保存される
- [ ] cron設定確認: `crontab -l | grep backup` → 毎日 AM 2:00

### 23.7 ヘルスチェック
- [ ] `curl https://timebaibai.com/healthz` → `ok`

---

## 24. IoT 本番通信テスト

**必要環境**: Pico 2W デバイス + 本番WiFi接続

### 24.1 デバイス設定確認
- [ ] `secrets.py` の `server_base` が `https://timebaibai.com` に設定
- [ ] `secrets.py` の `api_key` がDjango管理画面のIoTDevice.api_keyと一致
- [ ] `secrets.py` の `device` がDjango管理画面のIoTDevice.external_idと一致

### 24.2 センサーデータ送信 (本番)
- [ ] curl で本番APIテスト:
  ```bash
  curl -s -X POST https://timebaibai.com/api/iot/events/ \
    -H "X-API-KEY: <device-api-key>" \
    -H "Content-Type: application/json" \
    -d '{"device":"pico2w_001","event_type":"sensor","payload":{"mq9":120,"pir":false}}'
  ```
- [ ] レスポンス 201 確認
- [ ] 管理画面でIoTEventレコード確認

### 24.3 設定取得 (本番)
- [ ] `GET https://timebaibai.com/api/iot/config/?device=pico2w_001` → 200
- [ ] `mq9_threshold`, `alert_enabled` 等の設定値がレスポンスに含まれる

### 24.4 MQ-9 アラート (本番)
- [ ] 閾値超過データ送信 → LINE通知 / メール通知トリガー
- [ ] PropertyAlert レコード自動作成確認

---

## 25. AWS Security Group 確認

- [ ] EC2コンソールでInboundルール確認:
  - SSH (22): 管理者IPのみ (推奨)
  - HTTP (80): 0.0.0.0/0
  - HTTPS (443): 0.0.0.0/0
- [ ] Outbound: All traffic 許可
- [ ] 不要なポートが開いていないことを確認

---

## 26. デバッグパネル

**テストURL**: `/admin/debug/` (developer権限が必要)

### 26.1 パネル表示
- [ ] `/api/debug/panel/` でシステム情報JSON取得
- [ ] Python/Django/DB バージョン表示
- [ ] メモリ使用量表示
- [ ] Celery接続状態表示

### 26.2 ログレベル制御
- [ ] `POST /api/debug/log-level/` でログレベル変更
- [ ] 変更後のログ出力レベルが反映される

### 26.3 IoTデバイスデバッグ
- [ ] `/admin/debug/device/<device_id>/` で個別デバイス診断
- [ ] 最新イベント・接続状態・設定値が表示される

---

## 27. セキュリティ機能

### 27.1 SecurityAudit
- [ ] 管理画面 → セキュリティ → Security Audit 一覧
- [ ] 「Run security audit」アクション実行
- [ ] 監査結果がレコードとして保存される
- [ ] 読み取り専用（編集不可）

### 27.2 SecurityLog
- [ ] 管理画面アクセスログが記録される
- [ ] ログイン/ログアウトイベントが記録される
- [ ] 90日超の古いログがCleanupで削除される

### 27.3 CostReport
- [ ] 「Run AWS cost check」アクション実行
- [ ] AWS利用料が取得・保存される
- [ ] 読み取り専用

---

## 付録A: 全API一覧と期待レスポンス

### IoT
| エンドポイント | メソッド | 認証 | 期待レスポンス |
|--------------|--------|------|-------------|
| `/api/iot/events/` | POST | X-API-KEY | 201, IoTEvent作成 |
| `/api/iot/config/` | GET | X-API-KEY | 200, デバイス設定JSON |
| `/api/iot/ir/send/` | POST | X-API-KEY | 200, IRコマンドキュー |
| `/api/iot/sensors/data/` | GET | Session | 200, センサーデータ配列 |
| `/api/iot/sensors/pir-events/` | GET | Session | 200, PIRイベント配列 |
| `/api/iot/sensors/pir-status/` | GET | Session | 200, PIRステータス |

### ダッシュボード
| エンドポイント | メソッド | 期待レスポンス |
|--------------|--------|-------------|
| `/api/dashboard/reservations/` | GET | today_count, week_count, month_count, cancel_rate |
| `/api/dashboard/sales/` | GET | today_revenue, week_revenue, daily_trend[] |
| `/api/dashboard/staff-performance/` | GET | staff[]{ name, reservations, revenue } |
| `/api/dashboard/shift-summary/` | GET | today_shifts, open_shifts |
| `/api/dashboard/low-stock/` | GET | products[]{ name, stock, threshold } |
| `/api/dashboard/menu-engineering/` | GET | products[]{ name, qty_sold, margin_rate, quadrant }, avg_popularity, avg_margin |
| `/api/dashboard/abc-analysis/` | GET | products[]{ name, revenue, share_pct, cumulative_pct, rank }, total_revenue |
| `/api/dashboard/forecast/` | GET | historical[], forecast[]{ date, predicted, lower, upper }, method |
| `/api/dashboard/layout/` | GET | widgets[]{ type, position } |

### 分析
| エンドポイント | メソッド | 期待レスポンス |
|--------------|--------|-------------|
| `/api/analytics/visitors/` | GET | date, estimated_visitors, order_count |
| `/api/analytics/heatmap/` | GET | {0:{9:N,...},...,6:{9:N,...}} |
| `/api/analytics/conversion/` | GET | コンバージョンデータ |

### AI推薦
| エンドポイント | メソッド | 期待レスポンス |
|--------------|--------|-------------|
| `/api/ai/recommendations/` | GET | date, hour, recommended_staff_count, factors |
| `/api/ai/train/` | POST | 200, 学習開始 |
| `/api/ai/model-status/` | GET | has_model, model_type, mae_score |

### シフト
| エンドポイント | メソッド | 期待レスポンス |
|--------------|--------|-------------|
| `/api/shift/week-grid/` | GET | 週間グリッドデータ |
| `/api/shift/assignments/` | GET/POST | シフト割当一覧/作成 |
| `/api/shift/publish/` | POST | シフト公開 |
| `/api/shift/auto-schedule/` | POST | 自動割当実行 |

### 出退勤
| エンドポイント | メソッド | 期待レスポンス |
|--------------|--------|-------------|
| `/api/attendance/stamp/` | POST | TOTP打刻 |
| `/api/attendance/pin-stamp/` | POST | PIN打刻 |
| `/api/attendance/day-status/` | GET | 本日の出退勤状況 |
| `/api/attendance/totp/refresh/` | POST | TOTP更新 |

### POS
| エンドポイント | メソッド | 期待レスポンス |
|--------------|--------|-------------|
| `/api/pos/orders/` | GET | 本日のオーダー |
| `/api/pos/order-items/` | GET/POST | 注文アイテム取得/作成 |
| `/api/pos/checkout/` | POST | 会計処理 |
| `/api/pos/order-item/<pk>/status/` | PUT | ステータス更新 |

---

## 付録B: モックデータ投入コマンド

```bash
# 開発環境
python manage.py seed_mock_data

# 本番環境（既存データリセット）
python manage.py seed_mock_data --reset

# 投入されるデータ概要:
# - 店舗: 1件
# - スタッフ: 5名
# - 予約: ~508件（90日分、キャンセル率~8%）
# - 注文: ~516件（90日分）+ オープンオーダー3件
# - 来客数: ~1,350件（90日 × 15時間帯）
# - AI推薦モデル: 1件 + 推薦結果210件
# - 給与: 2期間分
# - 出退勤: 本日3名分
# - 商品: 30+品（4品が意図的に在庫不足）
# - IoTデバイス: 1台 + IoTイベント300件
```

---

## 付録C: テスト用チェックリスト（営業デモ用）

最低限確認すべき「デモ映え」する画面:

| # | 画面 | URL | チェック |
|---|------|-----|---------|
| 1 | 売上ダッシュボード | `/admin/dashboard/sales/` | [ ] KPI表示、グラフ描画 |
| 2 | 来客ヒートマップ | `/admin/analytics/visitors/` | [ ] チャート、ヒートマップ |
| 3 | AI推薦テーブル | `/admin/ai/recommendation/` | [ ] モデル情報、推薦表 |
| 4 | POS画面 | `/admin/pos/` | [ ] 商品一覧、カート |
| 5 | キッチンディスプレイ | `/admin/pos/kitchen/` | [ ] 注文カード表示 |
| 6 | シフトカレンダー | `/admin/shift/calendar/` | [ ] 週間グリッド |
| 7 | 出退勤ボード | `/admin/attendance/board/` | [ ] 出勤状況表示 |
| 8 | IoTセンサーグラフ | `/admin/iot/sensors/` | [ ] リアルタイムグラフ |
| 9 | テーブル注文（顧客側） | `/t/<table_uuid>/` | [ ] メニュー、カート |
| 10 | ECショップ | `/shop/` | [ ] 商品一覧、カート |
