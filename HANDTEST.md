# HANDTEST.md — NewFUHI 手動テスト手順書

> 自動テストではカバーできない外部連携・実機操作・ブラウザ操作を対象とした手動テスト手順書。
> 各テスト項目に [PASS] / [FAIL] を記録し、実施日とテスターを記入してください。

---

## 実施記録

| 実施日 | テスター | 対象セクション | 結果 |
|--------|---------|---------------|------|
|        |         |               |      |

---

## 前提条件

```bash
# 開発サーバー起動
cd /home/ubuntu/NewFUHI
source .venv/bin/activate
python manage.py runserver 0.0.0.0:8000

# Celeryワーカー起動（タスクテスト用）
celery -A project worker -l info &
celery -A project beat -l info &

# Redis起動確認
redis-cli ping  # → PONG
```

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

### 3.3 物件監視タスク (check_property_alerts)
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

## 7. 管理画面 UI

**テストURL**: `/admin/`

### 7.1 ロール別メニュー表示
- [ ] **superuser**: 全モデル表示
- [ ] **developer** (is_developer=True): 全モデル + デバッグパネル
- [ ] **manager** (is_store_manager=True): シフト管理 + 給与 + 在庫
- [ ] **staff**: 自分のシフト・予約のみ

### 7.2 ダッシュボード
- [ ] 予約KPI（本日/今週/今月の予約数）表示
- [ ] 予約グラフ表示
- [ ] 売上トレンド表示
- [ ] ダッシュボードレイアウトのドラッグ&ドロップ
- [ ] ダークモード切り替え

### 7.3 AIチャットアシスタント
- [ ] 管理画面にAIチャットウィジェット表示 (SiteSettings.show_ai_chat=True)
- [ ] 質問入力 → Gemini API経由で回答取得
- [ ] ナレッジベースに基づく回答であることを確認
- [ ] 会話履歴の保持（最大10ターン）

### 7.4 テーマカスタマイズ
- [ ] AdminTheme でメインカラー変更 → 管理画面に反映
- [ ] ヘッダー画像アップロード → 表示確認

---

## 8. Celery タスク動作確認

**前提**: Celery ワーカー + Beat 稼働中

### 8.1 定期タスク
| タスク | スケジュール | 確認方法 |
|-------|------------|---------|
| `delete_temporary_schedules` | 毎分 | 10分超の仮予約が削除される |
| `check_low_stock_and_notify` | 1時間ごと | 在庫閾値割れ商品のLINE通知 |
| `check_property_alerts` | 5分ごと | 物件アラート自動生成 |
| `run_security_audit` | 毎日03:00 | SecurityAudit レコード作成 |
| `cleanup_security_logs` | 毎週日曜04:00 | 90日超ログ削除 |
| `check_aws_costs` | 毎日06:00 | CostReport レコード作成 |

### 8.2 手動タスク実行
```bash
# Django シェルから手動実行
python manage.py shell
>>> from booking.tasks import check_property_alerts
>>> check_property_alerts()
```

### 8.3 タスクエラーハンドリング
- [ ] 外部サービス障害時にタスクがクラッシュしないことを確認
- [ ] ログにエラー詳細が記録されることを確認

---

## 9. ブラウザ互換性

### 9.1 モバイルブラウザ
| ブラウザ | テスト項目 | 結果 |
|---------|-----------|------|
| iOS Safari | トップページ表示 | [ ] |
| iOS Safari | 予約フロー（カレンダー→LINE） | [ ] |
| iOS Safari | テーブル注文（QR→注文→決済） | [ ] |
| iOS Safari | ECショップ（商品一覧→カート→決済） | [ ] |
| iOS Chrome | 同上 | [ ] |
| Android Chrome | 同上 | [ ] |

### 9.2 デスクトップブラウザ
| ブラウザ | テスト項目 | 結果 |
|---------|-----------|------|
| Chrome (最新) | 管理画面全機能 | [ ] |
| Firefox (最新) | 管理画面全機能 | [ ] |
| Safari (最新) | 管理画面全機能 | [ ] |
| Edge (最新) | 管理画面全機能 | [ ] |

### 9.3 レスポンシブデザイン
- [ ] 375px (iPhone SE) でレイアウト崩れなし
- [ ] 768px (iPad) でレイアウト崩れなし
- [ ] 1920px (デスクトップ) でレイアウト崩れなし

---

## 10. 多言語対応 (i18n)

### 10.1 言語切り替え
対応言語: ja, en, zh-hant, zh-hans, ko, es, pt

- [ ] `?lang=en` パラメータで英語表示に切り替わる
- [ ] `?lang=zh-hant` で繁体字中国語表示
- [ ] 店舗のデフォルト言語設定が反映される
- [ ] 商品名・説明が `ProductTranslation` から取得される

### 10.2 翻訳データ確認
- [ ] 翻訳が存在しない言語 → デフォルト (ja) にフォールバック
- [ ] 全言語で商品メニューが正しく表示される

---

## 付録: テスト用データ作成

```bash
# 管理者ユーザー作成
python manage.py bootstrap_admin_staff --username admin --store_id 1 --manager --developer

# テストデータ作成 (Django shell)
python manage.py shell <<EOF
from booking.models import *
store = Store.objects.first()

# カテゴリ・商品作成
cat = Category.objects.create(store=store, name="ドリンク")
Product.objects.create(store=store, category=cat, sku="DRK-001", name="コーヒー", price=400, stock=50, is_active=True, is_ec_visible=True)

# テーブル席作成
TableSeat.objects.create(store=store, label="A1")

# IoTデバイス作成
device = IoTDevice(name="テストセンサー", store=store, external_id="pico-001", mq9_threshold=300, alert_enabled=True)
device.set_api_key("my-secret-key-12345678")
device.save()

print("テストデータ作成完了")
EOF
```
