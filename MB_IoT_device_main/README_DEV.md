# CircuitPython IoT Device - 開発運用ガイド

## プロジェクト構成

- **本体ディレクトリ**: `~/MB_IoT_device_main` （ソースオブトゥルース）
- **デバイス**: `/Volumes/CIRCUITPY` （Pico 2 W）
- **バックアップ**: `~/backups/CIRCUITPY_backup_YYYYMMDD-HHMMSS/`

## 基本運用フロー

### 1. 通常の開発作業
```bash
# 本体ディレクトリで編集
cd ~/MB_IoT_device_main
# ファイルを編集...

# デバイスに反映（衝突自動掃除付き）
./scripts/sync_to_device.sh
```

### 2. デバイスからの緊急退避
```bash
# デバイス→本体へ吸い上げ
./scripts/sync_from_device.sh
```

### 3. バックアップ作成
```bash
# デバイスの現状をバックアップ
./scripts/backup_device.sh
```

## 同期トラブルシューティング

### 典型的な問題と対処

#### FAT filesystem 衝突エラー
- **症状**: `rsync: error: Not a directory` / `Is a directory`
- **原因**: 同名のファイル⇔ディレクトリ衝突（FAT特有）
- **対処**: `sync_to_device.sh` に自動掃除機能を内蔵済み

#### 権限エラー
- **症状**: `Permission denied` on `.Trashes`
- **対処**: 除外リストに追加済み（警告は無害）

### 成功判定
```bash
# sync_to_device.sh が exit 0 で完了
echo $?  # 0 なら成功

# 主要ファイルのハッシュ一致確認
shasum ~/MB_IoT_device_main/code.py /Volumes/CIRCUITPY/code.py
shasum ~/MB_IoT_device_main/django_api.py /Volumes/CIRCUITPY/django_api.py
```

## 秘匿情報管理

### Git管理外ファイル
- `secrets.py` - Wi-Fi認証情報、API設定
- `wifi_config.json` - Wi-Fi設定
- `certs/` - 証明書ディレクトリ
- `*.pem`, `*.key`, `*.crt` - 証明書・秘密鍵

### 設定手順
```bash
# テンプレートから作成
cp secrets.example.py secrets.py
# secrets.py を編集...
```

**重要**: `secrets.py` は追跡しない（.gitignore設定済み）

## Wi-Fi自動接続の確認手順

### ファイル参照関係
- `code.py` → メインエントリーポイント
- `wifi_provisioning.py` → Wi-Fi接続管理
- `secrets.py` → Wi-Fi認証情報（Git管理外）
- `config.py` → 設定管理
- `force_ap.flag` → 強制APモードフラグ

### 実機確認手順

1. **Pico再起動**
   ```bash
   # Picoの電源を入れ直すか、RESETボタンを押す
   ```

2. **ログ確認**
   ```bash
   # boot_out.txt でCircuitPythonの起動を確認
   cat /Volumes/CIRCUITPY/boot_out.txt
   
   # Wi-Fi接続状況をシリアルコンソールで確認
   # または、デバイスのLED状態で判断
   ```

3. **Wi-Fi接続状態の確認**
   - 正常: デバイスがWi-Fiに接続し、設定されたIPアドレスを取得
   - APモード: `force_ap.flag` が存在する場合、アクセスポイントモードで起動
   - エラー: `secrets.py` の設定不備やWi-Fi環境の問題

## 実機動作確認テスト

### テスト目的
Pico 2 W が電源ON → Wi-Fi自動接続 → Django予約システムへ送信/反映の一連の流れを確認

### 事前準備
1. Django予約システムが起動していること
2. `secrets.py` にWi-Fi認証情報とDjango API設定が正しく記載されていること
3. `config.py` の接続先設定が正しいこと

### テスト手順

#### 1. Pico側の動作確認

```bash
# 1-1. Picoを電源ON（USB挿し直し）
# USBケーブルを抜き差しして再起動

# 1-2. 起動ログ確認
cat /Volumes/CIRCUITPY/boot_out.txt

# 1-3. Wi-Fi接続確認
# シリアルコンソール（screen, minicom等）でログ監視
# または、プロジェクト固有のLED/LCD表示で接続状態確認

# 期待される挙動:
# - CircuitPython起動メッセージ
# - Wi-Fi接続成功メッセージ
# - IPアドレス取得確認
# - Django APIへの接続試行ログ
```

#### 2. Django側の受信確認

```bash
# 2-1. Django開発サーバーのログ監視
# runserver使用時:
python manage.py runserver

# 2-2. APIエンドポイントへのリクエスト確認
# ログで以下を確認:
# - Picoからのリクエスト受信
# - 認証成功/失敗
# - データベースへの書き込み

# 2-3. 管理画面での反映確認
# Django admin または独自管理画面で:
# - 予約データの新規作成/更新
# - センサーデータの記録
# - イベントログの記録
```

#### 3. 設定値確認（機密値は表示しない）

```bash
# 3-1. 接続先設定の確認
# config.py の以下の変数を確認:
# - API_BASE_URL
# - API_TIMEOUT
# - RETRY_COUNT

# 3-2. 認証設定の確認
# secrets.py の以下の変数を確認（値は表示しない）:
# - WIFI_SSID
# - WIFI_PASSWORD  
# - API_KEY
# - DEVICE_ID

# 3-3. Django側設定の確認
# django_api.py の接続ロジック確認:
# - エンドポイントURL構築
# - ヘッダー設定
# - エラーハンドリング
```

### 期待される結果

#### 成功時
- Pico: Wi-Fi接続成功、Django APIへのリクエスト送信成功
- Django: リクエスト受信、データベース反映、レスポンス返却
- ログ: エラーなし、正常な通信フロー

#### 失敗時の典型パターン
- **Wi-Fi接続失敗**: `secrets.py` の認証情報確認
- **API接続失敗**: Django側の起動状態、ファイアウォール確認
- **認証失敗**: API_KEY、エンドポイントURL確認
- **データ形式エラー**: Django側のシリアライザー、バリデーション確認

### トラブルシューティング

#### Wi-Fi接続失敗時
1. `secrets.py` の設定確認
2. `force_ap.flag` の存在確認（削除でWi-Fi接続モードに戻る）
3. `config.py` の設定確認

#### Django API接続失敗時
1. Django側の起動確認
2. ネットワーク疎通確認
3. API認証設定確認
4. エンドポイントURL確認

#### ファイル破損時
```bash
# バックアップから復旧
cp ~/backups/CIRCUITPY_backup_YYYYMMDD-HHMMSS/code.py ~/MB_IoT_device_main/
./scripts/sync_to_device.sh
```

## ファイルサイズ・更新時刻確認

### 本体とデバイスの同期確認
```bash
# 主要ファイルのサイズ・更新時刻比較
echo "=== Main Directory ==="
ls -la ~/MB_IoT_device_main/code.py ~/MB_IoT_device_main/django_api.py

echo "=== Device ==="
ls -la /Volumes/CIRCUITPY/code.py /Volumes/CIRCUITPY/django_api.py

# ハッシュ値での厳密な比較
echo "=== Hash Comparison ==="
shasum ~/MB_IoT_device_main/code.py /Volumes/CIRCUITPY/code.py
shasum ~/MB_IoT_device_main/django_api.py /Volumes/CIRCUITPY/django_api.py
```

### 期待値（正常時）
- `code.py`: 17486 bytes
- `django_api.py`: 12913 bytes
- ハッシュ値が本体とデバイスで一致

## 注意事項

- **編集対象**: `~/MB_IoT_device_main` のみ
- **Git管理外**: `secrets.py`, `*.pem`, `certs/` ディレクトリ
- **メタファイル**: `._*`, `.DS_Store` は自動除外
- **Safe Mode**: デプロイ前にPicoをSafe Mode（RESET 2回）にすることを推奨
- **衝突掃除**: `sync_to_device.sh` が自動でFAT衝突を解決