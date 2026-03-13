#!/bin/bash
# sync_from_device.sh - Pico→本体へ吸い上げ（緊急退避用）

set -euo pipefail

# AppleDouble混入を抑制
export COPYFILE_DISABLE=1

MAIN_DIR=~/MB_IoT_device_main

echo "Syncing from device to main directory..."
echo "Source: /Volumes/CIRCUITPY/"
echo "Target: $MAIN_DIR"

# CIRCUITPY マウント確認
if [ ! -d "/Volumes/CIRCUITPY" ]; then
    echo "ERROR: CIRCUITPY not mounted at /Volumes/CIRCUITPY"
    exit 1
fi

# 確認プロンプト
read -p "This will overwrite files in $MAIN_DIR. Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

# メタファイルと権限問題ファイルを除外して同期
if rsync -av \
    --exclude='._*' \
    --exclude='.DS_Store' \
    --exclude='.fseventsd/' \
    --exclude='.Trash-*' \
    --exclude='.Trashes/' \
    /Volumes/CIRCUITPY/ "$MAIN_DIR/"; then
    echo "Sync from device completed successfully."
else
    echo "ERROR: rsync failed during sync from device"
    exit 1
fi