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

# デバイスに反映
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

### トラブルシューティング

#### Wi-Fi接続失敗時
1. `secrets.py` の設定確認
2. `force_ap.flag` の存在確認（削除でWi-Fi接続モードに戻る）
3. `config.py` の設定確認

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