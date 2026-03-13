#!/bin/bash
# sync_to_device.sh - 本体→Picoへ反映（通常運用）

set -euo pipefail

# AppleDouble混入を抑制
export COPYFILE_DISABLE=1

MAIN_DIR=~/MB_IoT_device_main

echo "Syncing from main directory to device..."
echo "Source: $MAIN_DIR"
echo "Target: /Volumes/CIRCUITPY/"

# CIRCUITPY マウント確認
if [ ! -d "/Volumes/CIRCUITPY" ]; then
    echo "ERROR: CIRCUITPY not mounted at /Volumes/CIRCUITPY"
    exit 1
fi

# 本体ディレクトリ存在確認
if [ ! -d "$MAIN_DIR" ]; then
    echo "ERROR: Main directory not found: $MAIN_DIR"
    exit 1
fi

echo "Phase 1: Cleaning up file/directory conflicts..."

# ディレクトリとして必要なパスがファイルとして存在する場合を修正
REQUIRED_DIRS=(
    "/Volumes/CIRCUITPY/lib"
    "/Volumes/CIRCUITPY/lib/adafruit_character_lcd"
    "/Volumes/CIRCUITPY/lib/adafruit_mcp230xx"
    "/Volumes/CIRCUITPY/lib/adafruit_minimqtt"
    "/Volumes/CIRCUITPY/sensors"
    "/Volumes/CIRCUITPY/actuators"
    "/Volumes/CIRCUITPY/sd"
    "/Volumes/CIRCUITPY/certs"
)

for dir_path in "${REQUIRED_DIRS[@]}"; do
    if [ -f "$dir_path" ]; then
        echo "Conflict detected: $dir_path is a file but should be directory. Removing..."
        rm -f "$dir_path"
    fi
done

# ファイルとして必要なパスがディレクトリとして存在する場合を修正
REQUIRED_FILES=(
    "/Volumes/CIRCUITPY/sd/placeholder.txt"
    "/Volumes/CIRCUITPY/code.py"
    "/Volumes/CIRCUITPY/django_api.py"
    "/Volumes/CIRCUITPY/config.py"
    "/Volumes/CIRCUITPY/secrets.py"
)

for file_path in "${REQUIRED_FILES[@]}"; do
    if [ -d "$file_path" ]; then
        echo "Conflict detected: $file_path is a directory but should be file. Removing..."
        rmdir "$file_path" 2>/dev/null || rm -rf "$file_path"
    fi
done

echo "Phase 2: Deploying files using deploy script..."

# 本体ディレクトリから実行
cd "$MAIN_DIR"

# デプロイスクリプトを使用（FAT filesystem対応済み）
if [ -f "./deploy_circuitpython.sh" ]; then
    if ./deploy_circuitpython.sh sync; then
        echo "Deploy script completed successfully."
    else
        echo "ERROR: deploy_circuitpython.sh failed"
        exit 1
    fi
else
    echo "ERROR: deploy_circuitpython.sh not found in $MAIN_DIR"
    exit 1
fi

echo "Phase 3: Verifying sync completion..."

# 主要ファイルのハッシュ値確認
VERIFY_FILES=("code.py" "django_api.py")
VERIFY_FAILED=0

for file in "${VERIFY_FILES[@]}"; do
    if [ -f "$MAIN_DIR/$file" ] && [ -f "/Volumes/CIRCUITPY/$file" ]; then
        MAIN_HASH=$(shasum "$MAIN_DIR/$file" | cut -d' ' -f1)
        DEVICE_HASH=$(shasum "/Volumes/CIRCUITPY/$file" | cut -d' ' -f1)
        
        if [ "$MAIN_HASH" = "$DEVICE_HASH" ]; then
            echo "✓ $file: Hash verified"
        else
            echo "✗ $file: Hash mismatch (main: $MAIN_HASH, device: $DEVICE_HASH)"
            VERIFY_FAILED=1
        fi
    else
        echo "✗ $file: File missing"
        VERIFY_FAILED=1
    fi
done

if [ $VERIFY_FAILED -eq 1 ]; then
    echo "ERROR: Verification failed"
    exit 1
fi

echo "Sync to device completed successfully."