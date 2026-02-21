# Pico デバイス接続テスト手順

実機 Pico W とローカル Django サーバーを接続して動作確認する手順です。

---

## 前提条件

- Mac と Pico W が同じ Wi-Fi ネットワークに接続されていること
- Python venv が `/Users/adon/NewFUHI/venv` に存在すること
- Django プロジェクトがマイグレーション済みであること

---

## Step 1: Mac の IP アドレスを確認

```bash
ifconfig | grep "inet "
```

Wi-Fi (en0) の行から IPv4 アドレスを確認する。例:

```
inet 192.168.0.108 netmask 0xffffff00 broadcast 192.168.0.255
```

または、以下のコマンドでも確認可能:

```bash
ipconfig getifaddr en0
```

---

## Step 2: Pico の config.py を更新

`MB_IoT_device_main/config.py` の `DJANGO_EVENTS_URL` を Mac の IP に合わせる:

```python
# Mac の現在 IP に合わせる（Step 1 の結果）
DJANGO_EVENTS_URL = "http://192.168.0.108:8000/booking/api/iot/events/"
DJANGO_API_KEY = "test-api-key-123"   # Django 側 IoTDevice.api_key_hash と一致
```

**注意**: `DEVICE_ID` がDjango側の `IoTDevice.external_id` と一致していることを確認する。デフォルト値は `"Ace1"`。

---

## Step 3: Django サーバーを起動

ローカルネットワークからアクセスできるよう `0.0.0.0:8000` でバインドする:

```bash
cd /Users/adon/NewFUHI
./venv/bin/python manage.py runserver 0.0.0.0:8000
```

起動後、ブラウザで `http://127.0.0.1:8000/booking/admin/` にアクセスできることを確認する。

---

## Step 4: Pico を USB 接続しシリアルモニターを開く

1. Pico W を Mac に USB で接続する
2. Thonny または `screen` コマンドでシリアルモニターを開く:

```bash
# デバイスパスを確認
ls /dev/tty.usb*

# シリアルモニター接続（例）
screen /dev/tty.usbmodem1101 115200
```

3. Pico のコンソールに以下のようなログが表示されることを確認:
   - Wi-Fi 接続成功
   - Django API への送信開始
   - HTTP 201 レスポンス

---

## Step 5: Django admin で IoTDevice を登録

1. `http://127.0.0.1:8000/booking/admin/` にログイン
2. 「IoTデバイス」を開き、新規作成:
   - **デバイス名**: `Pico Sensor Node`（任意）
   - **店舗**: テスト用の Store を選択
   - **デバイスID（AWS側）**: `Ace1`（config.py の `DEVICE_ID` と一致させる）
   - **APIキーハッシュ**: 以下のコマンドで生成した値を貼り付ける
   - **有効**: チェックを入れる

APIキーハッシュの生成:

```bash
python3 -c "import hashlib; print(hashlib.sha256(b'test-api-key-123').hexdigest())"
```

あるいは Django shell で:

```bash
./venv/bin/python manage.py shell -c "from booking.models import IoTDevice; print(IoTDevice.hash_api_key('test-api-key-123'))"
```

---

## Step 6: デバッグパネルでオンライン状態を確認

1. Django admin のデバッグパネル (`/booking/admin/debug/`) にアクセス
2. IoTDevice 一覧で以下を確認:
   - **最終通信日時** (`last_seen_at`) が更新されている
   - デバイスがオンライン表示になっている

---

## Step 7: センサーダッシュボードでグラフデータを確認

1. `http://127.0.0.1:8000/booking/iot/sensors/dashboard/` にアクセス
2. 対象デバイスを選択
3. 以下のグラフが表示されることを確認:
   - **MQ-9 (ガス)**: 値の推移
   - **照度 (Light)**: 値の推移
   - **音量 (Sound)**: 値の推移
   - **PIR (人感)**: モーション検知イベントのカウント

API を直接確認する場合:

```bash
# センサーデータ（時系列）
curl -s "http://127.0.0.1:8000/booking/api/iot/sensors/data/?device_id=1&range=1h&sensor=mq9" | python3 -m json.tool

# PIR イベント
curl -s "http://127.0.0.1:8000/booking/api/iot/sensors/pir-events/?device_id=1&range=24h" | python3 -m json.tool
```

---

## トラブルシューティング

### Pico が Wi-Fi に接続できない

- `config.py` の `WIFI_SSID` / `WIFI_PASSWORD` を確認
- Mac と同じ 2.4GHz ネットワークを使っているか確認（Pico W は 5GHz 非対応）
- ルーターの MAC フィルタリングを確認

### Django サーバーに接続できない（Connection refused）

- Django を `0.0.0.0:8000` で起動しているか確認
- Mac のファイアウォール設定を確認:
  - 「システム設定 > ネットワーク > ファイアウォール」で Python を許可
- `config.py` の IP アドレスが最新か確認（DHCP でIP が変わることがある）

### HTTP 404 が返る

- `IoTDevice.external_id` が `config.py` の `DEVICE_ID` と一致しているか確認
- `IoTDevice.api_key_hash` が `config.py` の `DJANGO_API_KEY` のハッシュ値と一致しているか確認:

```bash
python3 -c "import hashlib; print(hashlib.sha256(b'test-api-key-123').hexdigest())"
```

### HTTP 400 が返る

- POST ボディに `"device"` フィールドが含まれているか確認
- `X-API-KEY` ヘッダーが送信されているか確認
- Pico 側のリクエストログでペイロード内容を確認

### センサーデータが保存されない

- Django のコンソールログで 201 レスポンスが返っているか確認
- Django admin の「IoTイベントログ」に新しいレコードが作成されているか確認
- `mq9_value`, `light_value`, `sound_value` が NULL でないか確認

### グラフにデータが表示されない

- `/booking/api/iot/sensors/data/?device_id=<ID>&range=1h` で `labels` / `values` が空でないか確認
- `device_id` パラメータにデバイスの **主キー (PK)** を渡しているか確認（`external_id` ではない）
- 時間範囲 (`range`) を `24h` や `7d` に広げて確認
