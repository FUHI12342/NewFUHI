# NewFUHI システム取り扱いマニュアル

**システム名:** NewFUHI（占いサロン予約＋IoTモニタリングシステム）
**本番URL:** https://timebaibai.com
**バージョン:** 2026-03-08

---

## 目次

1. [システム概要](#1-システム概要)
2. [IoTデバイス（Pico 2W）](#2-iotデバイスpico-2w)
3. [Web管理画面](#3-web管理画面)
4. [センサーダッシュボード](#4-センサーダッシュボード)
5. [サーバー管理](#5-サーバー管理)
6. [バックアップ](#6-バックアップ)
7. [トラブルシューティング](#7-トラブルシューティング)
8. [API仕様](#8-api仕様)

---

## 1. システム概要

### 構成図

```
┌──────────────┐     WiFi      ┌──────────────────┐     HTTPS     ┌─────────────────┐
│  Pico 2W     │──────────────▶│  WiFiルーター     │──────────────▶│  AWS EC2        │
│  IoTデバイス  │  センサーデータ │  (aterm/KEMURIBA) │              │  52.198.72.13   │
│              │  10秒間隔     │                  │              │  timebaibai.com │
└──────────────┘              └──────────────────┘              └─────────────────┘
   MQ-9 (CO)                                                      │ Nginx + SSL
   Sound                                                          │ Gunicorn
   PIR (人感)                                                      │ Django
   Button                                                         │ Celery + Redis
   IR TX/RX                                                       │ SQLite
                                                                  │
                                              ┌───────────────────┘
                                              ▼
                                    ┌──────────────────┐
                                    │  S3バックアップ    │
                                    │  mee-newfuhi-    │
                                    │  backups         │
                                    └──────────────────┘
```

### 主要機能

| 機能 | 説明 |
|------|------|
| 予約管理 | 占い師のスケジュール・予約受付（LINE/メール） |
| IoTモニタリング | ガス濃度・音・人感センサーのリアルタイム監視 |
| ガス警報 | MQ-9センサーがCO閾値超過でアラーム＋LINE通知 |
| IR学習/送信 | 赤外線リモコンの学習・再生（エアコン等） |
| EC決済 | Coiney連携によるオンライン決済 |
| QRチェックイン | 予約QRコード生成＋店頭読取 |
| シフト管理 | スタッフのシフト希望提出・管理 |

---

## 2. IoTデバイス（Pico 2W）

### 2.1 ハードウェア構成

| 部品 | ピン | 機能 |
|------|------|------|
| MQ-9 ガスセンサー | GP26 (A0) | CO（一酸化炭素）濃度測定 |
| マイク（Sound） | GP28 (A2) | 環境音レベル測定 |
| PIR 人感センサー | GP18 (D18) | 動体検知 |
| ボタン | GP16 (D16) | 手動操作（長押しでIR学習モード） |
| ブザー | GP20 (D20) | ガス警報音 |
| IR送信 | GP0 (UART0 TX) | 赤外線送信 |
| IR受信 | GP5 (UART1 RX) | 赤外線受信（学習用） |
| LED | 内蔵LED | 状態表示 |

> **注意:** Light（照度）センサーは未接続のため無効化されています（`FEATURE_LIGHT = False`）。

### 2.2 電源投入と起動

1. **USB-C電源アダプター**（5V/1A以上）をPico 2Wに接続
2. 自動的に`code.py`が実行開始
3. WiFi接続を試行（成功でLED点灯）
4. サーバーから設定取得 → センサー読取開始

### 2.3 LED状態表示

| LED状態 | 意味 |
|---------|------|
| 常時点灯 | WiFi接続済み・正常動作中 |
| 0.5秒間隔で点滅 | セットアップモード（AP起動中） |
| ゆっくり点滅 | WiFi切断・再接続試行中 |
| 消灯 | 初期化中またはエラー |

### 2.4 動作サイクル

```
起動
  ↓
WiFi接続 (secrets.pyの認証情報使用)
  ↓
サーバーから設定取得 (閾値・アラート設定)
  ↓
┌─────── メインループ ───────┐
│                            │
│  10秒ごと:                  │
│    MQ-9読取 → 閾値比較      │
│    Sound読取                │
│    → Django APIへPOST       │
│                            │
│  5秒ごと:                   │
│    PIR状態チェック           │
│    → 変化時にイベントPOST    │
│                            │
│  0.2秒ごと:                 │
│    IR受信チェック            │
│                            │
│  30秒ごと:                  │
│    WiFi健全性チェック        │
│    サーバー設定同期          │
│                            │
└────────────────────────────┘
```

### 2.5 ガス警報

MQ-9センサー値が閾値（デフォルト: **500**）を超えた場合:

1. ブザーが警報メロディを再生
2. `mq9_alarm`イベントをサーバーに送信
3. サーバー側でLINE/メール通知（設定済みの場合）

> **通常値:** 120〜300（空気清浄時）。調理時等は一時的に上昇します。

### 2.6 IR学習モード

1. デバイスのボタンを**10秒以上長押し**
2. LEDが高速点滅 → 学習モード突入
3. リモコンをIR受信部に向けてボタンを押す
4. 学習完了 → `ir_learned`イベントがサーバーに送信
5. 管理画面から学習したIRコードを確認・送信可能

### 2.7 セットアップモード

WiFi接続に3回連続失敗すると自動でセットアップモードに入ります。

**手動でセットアップモードに入る方法:**
- ボタン長押し（WiFi切断時）
- CIRCUITPY上に `force_setup.txt`（内容: `FORCE_SETUP`）を作成

**セットアップモードでの操作:**
1. デバイスがAPを起動（SSID: `PICO-SETUP-*`）
2. スマホ/PCからそのSSIDに接続
3. ブラウザで`http://192.168.4.1`にアクセス
4. WiFi SSID/パスワード、サーバーURL等を入力
5. 保存後、デバイスが再起動

### 2.8 デバイス認証情報

デバイスの認証情報は `/Volumes/CIRCUITPY/secrets.py` に保存:

```python
secrets = {
    "ssid": "WiFi名",
    "password": "WiFiパスワード",
    "api_key": "APIキー",
    "device": "デバイスID (例: pico2w_001)",
    "server_base": "https://timebaibai.com",
    "events_endpoint": "/api/iot/events/",
    "config_endpoint": "/api/iot/config/",
}
```

> **変更時:** PCにUSB接続 → CIRCUITPYドライブが表示 → `secrets.py`を編集 → 保存後自動再起動

### 2.9 デバイスのファームウェア更新

1. PCにUSB接続
2. `/Volumes/CIRCUITPY/`に表示されるファイルを編集
3. 保存すると自動的に再起動・反映

主要ファイル:
| ファイル | 用途 |
|----------|------|
| `code.py` | メインプログラム |
| `secrets.py` | WiFi・API認証情報 |
| `config.py` | GPIO設定・タイミング |
| `django_api.py` | サーバー通信モジュール |

---

## 3. Web管理画面

### 3.1 アクセス方法

| 画面 | URL |
|------|-----|
| 管理者ログイン | https://timebaibai.com/admin/ |
| 予約トップ | https://timebaibai.com/booking/ |
| LINEログイン | https://timebaibai.com/booking/line_enter/ |

### 3.2 Django管理画面（/admin/）

管理者アカウントでログイン後、以下の操作が可能:

**IoT関連:**
- **IoT Devices** — デバイスの追加・編集・API キー管理
- **IoT Events** — 全センサーイベントの閲覧・検索
- **IR Codes** — 学習済みIRコードの管理
- **Properties** — 物件・設置場所の管理
- **Property Alerts** — アラート設定（ガス漏れ・無人検知等）

**予約関連:**
- **Stores** — 店舗情報の管理
- **Staffs** — 占い師（スタッフ）の管理
- **Schedules** — スケジュール・予約枠の管理
- **Reservations** — 予約一覧・キャンセル処理

### 3.3 IoTデバイス設定（管理画面）

`Admin > IoT Devices` からデバイスを選択:

| フィールド | 説明 |
|------------|------|
| name | デバイス表示名 |
| external_id | デバイスID（`pico2w_001`等） |
| device_type | `multi`（マルチセンサー）/ `door` / `other` |
| mq9_threshold | MQ-9警報閾値（デフォルト: 500） |
| alert_enabled | ガスアラート有効/無効 |
| alert_email | 警報メール送信先 |
| alert_line_user_id | LINE通知先ユーザーID |
| is_active | デバイス有効/無効 |

### 3.4 主要URL一覧

**お客様向け:**
| 機能 | URL |
|------|-----|
| 予約カレンダー | `/booking/date-calendar/` |
| 占い師一覧 | `/booking/fortune-tellers/` |
| 店舗一覧 | `/booking/stores/` |
| マイページ | `/booking/mypage/` |
| ショップ | `/booking/shop/` |
| ヘルプ | `/booking/help/` |
| プライバシーポリシー | `/booking/privacy/` |

**管理者向け:**
| 機能 | URL |
|------|-----|
| センサーダッシュボード | `/dashboard/sensors/` |
| MQ-9グラフ | `/dashboard/mq9/` |
| 物件一覧 | `/booking/properties/` |
| シフト管理 | `/booking/shift/` |
| チェックイン | `/booking/checkin/` |

---

## 4. センサーダッシュボード

### 4.1 リアルタイムダッシュボード

**URL:** `https://timebaibai.com/dashboard/sensors/`

Chart.jsベースのグラフでセンサーデータを可視化:

- **MQ-9 (CO):** 一酸化炭素濃度の時系列推移
- **Sound:** 環境音レベルの時系列推移
- **PIR:** 人感検知イベントの時間別集計

**表示範囲:** 1時間 / 6時間 / 24時間 / 7日

### 4.2 MQ-9専用グラフ

**URL:** `https://timebaibai.com/dashboard/mq9/`（要ログイン）

MQ-9ガスセンサーの詳細グラフ。閾値ラインの表示付き。

### 4.3 センサー値の見方

**MQ-9 (CO):**
| 範囲 | 状態 |
|------|------|
| 100〜300 | 正常（清浄な空気） |
| 300〜500 | やや上昇（調理・換気不足の可能性） |
| 500以上 | 警報閾値超過（換気を確認してください） |

**Sound（環境音）:**
| 範囲 | 状態 |
|------|------|
| 0〜5,000 | 静か |
| 5,000〜15,000 | 通常の室内環境音 |
| 15,000以上 | 大きな音（会話・音楽等） |

**PIR（人感）:**
- `triggered = True` → センサー前で動きを検知
- `triggered = False` → 動きなし

### 4.4 API経由でのデータ取得

```bash
# センサーデータ取得
curl "https://timebaibai.com/api/iot/sensors/data/?device_id=pico2w_001&sensor=mq9&range=24h"

# PIRステータス（直近60秒の人感検知）
curl "https://timebaibai.com/api/iot/sensors/pir-status/?device_id=pico2w_001"

# PIRイベント集計
curl "https://timebaibai.com/api/iot/sensors/pir-events/?device_id=pico2w_001&range=24h"

# デバイス一覧
curl "https://timebaibai.com/api/iot/sensors/data/?list_devices=1"
```

---

## 5. サーバー管理

### 5.1 サーバー情報

| 項目 | 値 |
|------|-----|
| インスタンス | i-0808c1fd30b1c0437 (t3.micro) |
| OS | Ubuntu 24.04 LTS |
| パブリックIP | 52.198.72.13 |
| ドメイン | timebaibai.com |
| アプリパス | /home/ubuntu/NewFUHI |
| Python仮想環境 | /home/ubuntu/NewFUHI/venv |

### 5.2 SSH接続

```bash
ssh -i ~/NewFUHI/newfuhi-key.pem ubuntu@52.198.72.13
```

### 5.3 systemdサービス

| サービス | 説明 | 設定ファイル |
|----------|------|------------|
| newfuhi | Gunicorn (Djangoアプリ) | /etc/systemd/system/newfuhi.service |
| newfuhi-celery | Celeryワーカー | /etc/systemd/system/newfuhi-celery.service |
| newfuhi-celerybeat | Celery定期タスク | /etc/systemd/system/newfuhi-celerybeat.service |
| nginx | Webサーバー/リバースプロキシ | /etc/nginx/ |
| redis-server | メッセージブローカー | systemd default |

**サービス管理コマンド:**

```bash
# 全サービスの状態確認
sudo systemctl status newfuhi newfuhi-celery newfuhi-celerybeat nginx redis

# 再起動
sudo systemctl restart newfuhi
sudo systemctl restart newfuhi-celery newfuhi-celerybeat

# ログ確認
sudo journalctl -u newfuhi -f              # Gunicornログ（リアルタイム）
sudo journalctl -u newfuhi-celery -f       # Celeryログ
tail -f /var/log/newfuhi/gunicorn-error.log # Gunicornエラーログ
tail -f /var/log/nginx/error.log            # Nginxエラーログ
```

### 5.4 デプロイ手順

**ローカルからのデプロイ（推奨）:**

```bash
cd ~/NewFUHI
# 1. 変更をコミット＆プッシュ
git add <files>
git commit -m "変更内容"
git push origin main

# 2. デプロイスクリプト実行
bash scripts/deploy_to_ec2.sh
```

スクリプトが自動で以下を実行:
1. EC2で`git pull`
2. `pip install -r requirements.txt`
3. `python manage.py migrate`
4. `python manage.py collectstatic`
5. `systemctl restart newfuhi newfuhi-celery newfuhi-celerybeat`
6. ヘルスチェック（HTTP応答確認）

**手動デプロイ（EC2上）:**

```bash
cd /home/ubuntu/NewFUHI
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart newfuhi newfuhi-celery newfuhi-celerybeat
```

### 5.5 SSL証明書

Let's Encrypt（自動更新）:

```bash
# 証明書の状態確認
sudo certbot certificates

# 手動更新（通常は自動）
sudo certbot renew
```

### 5.6 ファイアウォール

```bash
# UFW状態確認
sudo ufw status

# 開放ポート: 22(SSH), 80(HTTP→HTTPS redirect), 443(HTTPS)
```

### 5.7 セキュリティ設定

| 対策 | 状態 |
|------|------|
| SSL/HTTPS | Let's Encrypt（自動更新） |
| HSTS | 有効（1年） |
| UFW | SSH/HTTP/HTTPS のみ許可 |
| Fail2ban | SSH ブルートフォース防止 |
| Django CSRF | 有効 |
| Secure Cookies | 有効 |
| X-Frame-Options | DENY |

---

## 6. バックアップ

### 6.1 自動バックアップ（S3）

**スケジュール:** 毎日 AM 2:00（cron）

```bash
# cron設定確認
crontab -l
# 期待される出力:
# 0 2 * * * /bin/bash -lc '/home/ubuntu/NewFUHI/scripts/backup_to_s3.sh'
```

**バックアップ内容:**
| 対象 | S3パス | 保持期間 |
|------|--------|---------|
| DB (SQLite) | s3://mee-newfuhi-backups/db/ | S3: 90日, ローカル: 30日 |
| Media | s3://mee-newfuhi-backups/media/ | 常時同期 |

**手動バックアップ:**

```bash
cd /home/ubuntu/NewFUHI
bash scripts/backup_to_s3.sh
```

### 6.2 バックアップ確認

```bash
# S3上のバックアップ一覧
aws s3 ls s3://mee-newfuhi-backups/db/ | tail -5

# ローカルバックアップ
ls -la /home/ubuntu/NewFUHI/backups/
```

### 6.3 復元手順

```bash
# 1. S3からDBバックアップをダウンロード
aws s3 cp s3://mee-newfuhi-backups/db/newfuhi_db_20260308_020000.sqlite3 /tmp/restore.sqlite3

# 2. 現在のDBをバックアップ
cp /home/ubuntu/NewFUHI/db.sqlite3 /home/ubuntu/NewFUHI/db.sqlite3.bak

# 3. 復元
cp /tmp/restore.sqlite3 /home/ubuntu/NewFUHI/db.sqlite3

# 4. サービス再起動
sudo systemctl restart newfuhi
```

---

## 7. トラブルシューティング

### 7.1 IoTデバイスがデータを送信しない

**確認手順:**

1. **電源確認** — USB-Cケーブルが接続されているか、LEDが点灯/点滅しているか
2. **WiFi確認** — LEDが常時点灯（=WiFi接続済み）か
3. **シリアルモニター確認:**
   ```bash
   # macOSの場合
   screen /dev/tty.usbmodem* 115200
   # または
   ls /dev/tty.usbmodem*
   ```
4. **サーバー側確認:**
   ```bash
   ssh -i ~/NewFUHI/newfuhi-key.pem ubuntu@52.198.72.13
   cd /home/ubuntu/NewFUHI && source venv/bin/activate
   python manage.py shell -c "
   from booking.models import IoTEvent
   from django.utils import timezone
   from datetime import timedelta
   latest = IoTEvent.objects.order_by('-created_at')[:5]
   for e in latest:
       print(f'{e.created_at} | {e.event_type} | mq9={e.mq9_value}')
   "
   ```

**よくある原因:**
| 症状 | 原因 | 対処 |
|------|------|------|
| LEDが点滅 | WiFi切断 | ルーター確認、secrets.pyのSSID/パスワード確認 |
| LED消灯 | 電源断またはエラー | USB接続しシリアルログ確認 |
| LED点灯だがデータなし | API通信エラー | サーバーのNginx/Gunicornログ確認 |
| セットアップモード | WiFi 3回失敗 | 正しいWiFi情報でセットアップ |

### 7.2 サーバーがダウンしている

```bash
# 1. サービス状態確認
ssh -i ~/NewFUHI/newfuhi-key.pem ubuntu@52.198.72.13
sudo systemctl status newfuhi nginx

# 2. エラーログ確認
sudo journalctl -u newfuhi --since "1 hour ago"
tail -50 /var/log/nginx/error.log

# 3. サービス再起動
sudo systemctl restart newfuhi nginx

# 4. ヘルスチェック
curl -I https://timebaibai.com/booking/
```

### 7.3 ダッシュボードにデータが表示されない

1. デバイスがデータを送信しているか確認（7.1参照）
2. ブラウザのURLが正しいか確認: `https://timebaibai.com/dashboard/sensors/`
3. デバイスIDがAPIリクエストに含まれているか確認
4. ブラウザの開発者ツール（F12）→ Networkタブでエラー確認

### 7.4 MQ-9のアラームが鳴り続ける

1. 換気を行い、CO濃度が下がるか確認
2. センサー周辺に煙・ガス源がないか確認
3. 管理画面で閾値を一時的に上げて確認（誤報の場合）:
   - Admin > IoT Devices > 対象デバイス > `mq9_threshold` を調整
4. 閾値変更後、デバイスは30秒以内に新しい設定を取得

### 7.5 SSL証明書エラー

```bash
# 証明書の有効期限確認
sudo certbot certificates

# 期限切れの場合は手動更新
sudo certbot renew
sudo systemctl reload nginx
```

### 7.6 ディスク容量不足

```bash
# 容量確認
df -h

# ログのクリーンアップ
sudo journalctl --vacuum-time=7d
sudo find /var/log -name "*.gz" -mtime +30 -delete

# 古いバックアップの削除
find /home/ubuntu/NewFUHI/backups -mtime +30 -delete
```

### 7.7 デバイスのWiFi設定変更

1. PCにUSBで接続
2. CIRCUITPYドライブを開く
3. `secrets.py`を編集:
   ```python
   secrets = {
       "ssid": "新しいSSID",
       "password": "新しいパスワード",
       ...
   }
   ```
4. 保存 → デバイスが自動再起動

---

## 8. API仕様

### 8.1 IoTイベント受信

```
POST /api/iot/events/
Header: X-API-KEY: <デバイスAPIキー>
Content-Type: application/json
```

**リクエストボディ:**
```json
{
  "device": "pico2w_001",
  "event_type": "sensor",
  "mq9": 245,
  "sound": 8500,
  "payload": {
    "pir": false,
    "button": false
  }
}
```

**イベントタイプ:**
| event_type | 説明 |
|------------|------|
| `sensor` | 定期センサーデータ（10秒間隔） |
| `pir_motion` | PIR状態変化（False→True） |
| `mq9_alarm` | MQ-9閾値超過アラーム |
| `button_press` | ボタン押下 |
| `ir_rx` | IR信号受信 |
| `ir_learned` | IR学習完了 |

### 8.2 デバイス設定取得

```
GET /api/iot/config/?device=pico2w_001
Header: X-API-KEY: <デバイスAPIキー>
```

**レスポンス:**
```json
{
  "mq9_threshold": 500,
  "alert_enabled": true,
  "ir_command": null
}
```

### 8.3 センサーデータ取得

```
GET /api/iot/sensors/data/?device_id=pico2w_001&sensor=mq9&range=24h
```

**パラメータ:**
| パラメータ | 値 | 説明 |
|------------|-----|------|
| device_id | デバイスIDまたはDB ID | 必須 |
| sensor | `mq9` / `light` / `sound` | センサー種別（デフォルト: mq9） |
| range | `1h` / `6h` / `24h` / `7d` | 表示範囲（デフォルト: 1h） |

---

## 付録

### 環境変数一覧（.env.production）

| 変数 | 説明 | 例 |
|------|------|-----|
| SECRET_KEY | Djangoシークレットキー | ランダム文字列 |
| ALLOWED_HOSTS | 許可ホスト | timebaibai.com,52.198.72.13 |
| DB_NAME | DBファイルパス | /home/ubuntu/NewFUHI/db.sqlite3 |
| LINE_CHANNEL_ID | LINE OAuth ID | 数字 |
| LINE_CHANNEL_SECRET | LINE OAuthシークレット | 英数字 |
| LINE_ACCESS_TOKEN | LINE Messaging Token | 英数字 |
| CELERY_BROKER_URL | Redisブローカー | redis://localhost:6379/0 |

### 重要ファイルパス（EC2）

| パス | 用途 |
|------|------|
| /home/ubuntu/NewFUHI/ | アプリケーションルート |
| /home/ubuntu/NewFUHI/db.sqlite3 | データベース |
| /home/ubuntu/NewFUHI/media/ | アップロードファイル |
| /home/ubuntu/NewFUHI/staticfiles/ | 静的ファイル |
| /home/ubuntu/NewFUHI/.env.production | 環境変数 |
| /var/log/newfuhi/ | アプリケーションログ |
| /var/log/nginx/ | Webサーバーログ |
| /etc/nginx/sites-enabled/ | Nginx設定 |
| /etc/systemd/system/newfuhi*.service | systemd設定 |

### 緊急連絡先・参考情報

| 項目 | 情報 |
|------|------|
| AWSコンソール | ap-northeast-1（東京リージョン） |
| ドメイン管理 | Route 53（timebaibai.com） |
| S3バケット | mee-newfuhi-backups |
| GitHubリポジトリ | 要確認 |
| SSL認証局 | Let's Encrypt |
