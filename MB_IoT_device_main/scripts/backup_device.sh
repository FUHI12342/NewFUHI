#!/bin/bash
# backup_device.sh - Picoのバックアップを ~/backups/ に日時付きで作成

set -euo pipefail

# AppleDouble混入を抑制
export COPYFILE_DISABLE=1

BACKUP_DIR=~/backups/CIRCUITPY_backup_$(date +%Y%m%d-%H%M%S)

echo "Creating backup: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# CIRCUITPY マウント確認
if [ ! -d "/Volumes/CIRCUITPY" ]; then
    echo "ERROR: CIRCUITPY not mounted at /Volumes/CIRCUITPY"
    exit 1
fi

# メタファイルと権限問題ファイルを除外してバックアップ
if rsync -av \
    --exclude='._*' \
    --exclude='.DS_Store' \
    --exclude='.fseventsd/' \
    --exclude='.Trash-*' \
    --exclude='.Trashes/' \
    /Volumes/CIRCUITPY/ "$BACKUP_DIR/"; then
    echo "Backup completed successfully: $BACKUP_DIR"
    ls -la "$BACKUP_DIR" | head -10
else
    echo "ERROR: rsync failed during backup"
    exit 1
fi