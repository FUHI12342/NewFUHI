# Complete Implementation and Verification Guide

## 概要

このガイドでは、Nginx設定、Pico 2W診断システムの完全な実装と検証手順を説明します。

## 前提条件

- サーバーSSHアクセス（timebaibai.com）
- Pico 2WがMacにUSB接続されている
- `secrets.py`に実際の認証情報が設定されている（ダミー値でない）

## 自動実行スクリプト

すべての作業を自動化するスクリプトが用意されています：

### 1. 完全デプロイメント（推奨）

```bash
cd /Users/adon/NewFUHI
chmod +x scripts/*.sh
./scripts/complete_deployment.sh
```

このスクリプトは以下を実行します：
- CIRCUITPYバックアップ
- サーバー設定の指示
- Pico 2Wへのデプロイ
- 検証手順の表示

### 2. 個別実行（詳細制御が必要な場合）

#### A. Mac側バックアップ

```bash
./scripts/backup_circuitpy.sh
```

#### B. サーバー側設定

```bash
# 1. スクリプトをサーバーにコピー
scp -i newfuhi-key.pem scripts/apply_nginx_iot_config.sh ubuntu@<server-ip>:~/

# 2. SSHでサーバーに接続
ssh -i newfuhi-key.pem ubuntu@<server-ip>

# 3. Nginxバックアップとバックアップ
sudo bash apply_nginx_iot_config.sh

# スクリプトが自動的に以下を実行：
# - /var/backups/にバックアップ作成
# - timebaibai.com の server ブロックを検出
# - IoT API location ブロックを挿入
# - nginx -t でテスト
# - systemctl reload nginx で適用
```

#### C. Pico 2Wデプロイ

```bash
# 診断システムをデプロイ
./scripts/deploy_diagnostics_to_pico.sh

# 診断モードを有効化
./scripts/deploy_diagnostics_to_pico.sh --enable-diag

# （後で）診断モードを無効化
./scripts/deploy_diagnostics_to_pico.sh --disable-diag
```

## 検証手順

### サーバー検証

#### テスト1: IoT APIがBasic認証不要になったことを確認

```bash
curl -i \
  -H "X-API-KEY: <実際のAPIキー>" \
  "https://timebaibai.com/booking/api/iot/config/?device=pico2w_001" \
  | head -n 30
```

**期待される結果:**
- ✅ `WWW-Authenticate: Basic` ヘッダーが**出ない**
- ✅ ステータス: 200（成功）または403（APIキー無効）または404（エンドポイント未設定）
- ❌ ステータス: 401 = 失敗（Basic認証がまだ有効）

**実際の出力例（成功）:**
```
HTTP/2 200 
server: nginx
content-type: application/json
...
```

#### テスト2: 他のパスはBasic認証が維持されていることを確認

```bash
curl -i "https://timebaibai.com/" | head -n 20
```

**期待される結果:**
- ✅ `HTTP/1.1 401 Unauthorized`
- ✅ `WWW-Authenticate: Basic realm="Restricted"`

### Pico 2W診断実行

#### 手順

1. **CIRCUITPYの準備確認**
   ```bash
   # secrets.pyが正しく設定されているか確認（秘密情報はマスク）
   grep DIAGNOSTIC_MODE /Volumes/CIRCUITPY/secrets.py
   # 出力: "DIAGNOSTIC_MODE": True
   ```

2. **CIRCUITPYをアンマウント**
   - Finderで「CIRCUITPY」を右クリック→「取り出す」

3. **Pico 2Wをリセット**
   - RESETボタンを押す

4. **シリアルモニター接続**
   ```bash
   screen /dev/tty.usbmodem* 115200
   ```

5. **診断出力の確認**

   期待される出力:
   ```
   [DIAG] ===========================================================
   [DIAG]   PICO 2W COMPREHENSIVE DIAGNOSTICS
   [DIAG]   Device: pico2w_001
   [DIAG] ===========================================================
   
   [DIAG] Validating configuration...
   [DIAG] ✓ Configuration valid
   
   [DIAG] ===========================================================
   [DIAG] Testing LCD Display
   [DIAG] ===========================================================
   [DIAG] Trying LCD at I2C address 0x27...
   [DIAG] ✓ LCD initialized at 0x27
   
   [DIAG] ===========================================================
   [DIAG] Testing WiFi Auto-Connect
   [DIAG] ===========================================================
   [DIAG] Connection attempt 1/3
   [DIAG] ✓ WiFi connected!
   [DIAG]   SSID: aterm-***-g  (マスク済み)
   [DIAG]   IP: 192.168.x.x
   [DIAG]   RSSI: -52 dBm
   [DIAG] ✓ DNS resolution OK: timebaibai.com -> xx.xx.xx.xx
   
   ... (各テスト) ...
   
   [DIAG] ===========================================================
   [DIAG]   DIAGNOSTICS COMPLETE
   [DIAG] ===========================================================
   [DIAG] Results: 10 PASS, 1 WARN, 0 FAIL
   ```

6. **インタラクティブテストに応答**
   - **ボタンテスト**: 「Press button in 10s」→ ボタンを押す
   - **PIRテスト**: 「Move in 10s」→ センサー前で手を振る
   - **光センサーテスト**: 「Cover/uncover」→ センサーを覆う→外す

7. **診断レポートの確認**
   ```bash
   # screen を終了: Ctrl+A → K → Y
   
   # レポートを確認
   cat /Volumes/CIRCUITPY/diag_report.json | python3 -m json.tool
   ```

   期待される内容:
   ```json
   {
     "device": "pico2w_001",
     "wifi": {
       "status": "PASS",
       "ip": "192.168.x.x",
       "rssi": -55,
       "dns_ok": true
     },
     "tests": {
       "config_validation": {"status": "PASS"},
       "lcd_display": {"status": "PASS"},
       "wifi_autoconnect": {"status": "PASS"},
       "button": {"status": "PASS"},
       "buzzer": {"status": "PASS"},
       "mq9": {"status": "PASS", "avg_value": 12450},
       ...
     }
   }
   ```

### Django統合確認

サーバーで診断レポートが受信されたか確認:

```bash
ssh -i newfuhi-key.pem ubuntu@<server-ip>

# Gunicornログで診断イベントを検索
sudo journalctl -u gunicorn -n 200 --no-pager | grep -i "diagnostic"

# または、Djangoのdebug.logを確認
tail -n 100 /path/to/django/debug.log | grep -i "diagnostic"
```

**期待される出力:**
```
POST /booking/api/iot/events/ ... 200
# または
"type": "diagnostic_report", "device": "pico2w_001"
```

## トラブルシューティング

### サーバー側

#### 問題: curlでまだ401が返る

**原因**: Nginx設定が正しく適用されていない

**解決策:**
```bash
# サーバーで設定を確認
sudo nginx -T | grep -A 10 "/booking/api/iot/"

# location ブロックが存在し、auth_basic off が含まれているか確認

# 再読み込み
sudo systemctl reload nginx
```

#### 問題: Nginx reload が失敗

**原因**: 設定ファイルに構文エラー

**解決策:**
```bash
# エラーの詳細を確認
sudo nginx -t

# ロールバック
sudo cp /var/backups/timebaibai_<timestamp>/original_config /etc/nginx/sites-available/timebaibai
sudo systemctl reload nginx
```

### Pico 2W側

#### 問題: WiFi FAIL - "Failed to connect"

**原因1**: `secrets.py`にダミー値が残っている

**確認:**
```bash
cat /Volumes/CIRCUITPY/secrets.py | grep -E "api_key|server_base"
```

**修正:**
```python
"api_key": "実際のAPIキー",  # NOT "YOUR_API_KEY_HERE"
"server_base": "https://timebaibai.com",  # NOT "your-server.com"
```

**原因2**: WiFi SSID/パスワードが間違っている

**修正:** `secrets.py`のWiFi認証情報を確認

#### 問題: 診断が固まる

**原因**: インタラクティブテストでタイムアウト処理が動いていない

**解決策:**
- Ctrl+Cでシリアルモニターから抜ける
- Pico 2Wをリセット
- ログを確認してどのテストで止まったかを特定

#### 問題: "diagnostics.py not found"

**原因**: デプロイスクリプトが正しく実行されていない

**解決策:**
```bash
# 手動でコピー
cp MB_IoT_device_main/diagnostics.py /Volumes/CIRCUITPY/
cp MB_IoT_device_main/code.py /Volumes/CIRCUITPY/
```

## ロールバック手順

### サーバー側

```bash
# SSH to server
ssh -i newfuhi-key.pem ubuntu@<server-ip>

# スクリプトを使用
sudo ./scripts/rollback_server.sh
# または手動で
sudo cp /var/backups/timebaibai_<timestamp>/original_config /etc/nginx/sites-available/timebaibai
sudo nginx -t
sudo systemctl reload nginx
```

### Mac側（Pico 2W）

```bash
# スクリプトを使用
./scripts/rollback_circuitpy.sh
# バックアップを選択

# または診断モードだけ無効化
./scripts/deploy_diagnostics_to_pico.sh --disable-diag
```

## 成功確認チェックリスト

- [ ] サーバーバックアップ作成完了（`/var/backups/timebaibai_*`）
- [ ] CIRCUITPYバックアップ作成完了（`~/NewFUHI/_backups/CIRCUITPY_*`）
- [ ] Nginx設定適用完了（`nginx -t` 成功）
- [ ] IoT APIがBasic認証不要（curl確認）
- [ ] ルートパスはBasic認証維持（curl確認）
- [ ] Pico 2Wに`diagnostics.py`デプロイ完了
- [ ] 診断モード実行成功（シリアルログ確認）
- [ ] `diag_report.json`生成確認
- [ ] WiFi自動接続成功（ログ確認）
- [ ] 全ハードウェアテストPASS/WARN（FAILが配線問題でなければOK）
- [ ] Django診断レポート受信確認（サーバーログ）

## 通常運用に戻す

診断完了後、通常のIoTモードに戻す:

```bash
# 診断モードを無効化
./scripts/deploy_diagnostics_to_pico.sh --disable-diag

# CIRCUITPYをアンマウント
# Pico 2WをRESET

# 通常のセンサー監視が開始されることを確認
screen /dev/tty.usbmodem* 115200
# [MAIN] で始まるログが出ればOK
```

## まとめ

このシステムにより以下が実現されました：

1. **Nginx設定の自動化**: IoT APIのBasic認証除外が1コマンドで適用可能
2. **包括的診断**: WiFi + 11種類のハードウェアテストを自動実行
3. **完全なバックアップ/ロールバック**: 全ての変更が安全に元に戻せる
4. **オフライン対応**: WiFi不可でもローカルに診断結果を保存
5. **Django統合**: オンライン時は診断結果をサーバーに自動送信

すべてのスクリプトは実行可能で、エラーハンドリングとロールバック機能を備えています。
