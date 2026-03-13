#!/bin/bash
# backup_circuitpy.sh
# Mac-side script to backup CIRCUITPY drive with timestamp and compression

set -e  # Exit on error

# Configuration
CIRCUITPY_MOUNT="/Volumes/CIRCUITPY"
BACKUP_ROOT="$HOME/NewFUHI/_backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/CIRCUITPY_$TIMESTAMP"
TARBALL="$BACKUP_ROOT/CIRCUITPY_$TIMESTAMP.tgz"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "========================================"
echo "  CIRCUITPY Backup Script"
echo "  Timestamp: $TIMESTAMP"
echo "========================================"
echo ""

# Check if CIRCUITPY is mounted
if [ ! -d "$CIRCUITPY_MOUNT" ]; then
    echo -e "${RED}ERROR: CIRCUITPY drive not found at $CIRCUITPY_MOUNT${NC}"
    echo "Please connect your Pico 2W and ensure CIRCUITPY is mounted."
    exit 1
fi

echo -e "${GREEN}✓${NC} CIRCUITPY drive found at $CIRCUITPY_MOUNT"

# Create backup root directory if it doesn't exist
mkdir -p "$BACKUP_ROOT"
echo -e "${GREEN}✓${NC} Backup directory: $BACKUP_ROOT"

# Perform rsync backup with exclusions
echo ""
echo "Backing up CIRCUITPY to $BACKUP_DIR..."
echo ""

rsync -a --delete \
  --exclude '.Trashes/**' --exclude '.Trashes' \
  --exclude '.fseventsd/**' --exclude '.fseventsd' \
  --exclude '.Spotlight-V100/**' --exclude '.Spotlight-V100' \
  --exclude '.TemporaryItems/**' --exclude '.TemporaryItems' \
  --exclude '.vscode/**' --exclude '.vscode' \
  --exclude '._*' --exclude '.DS_Store' \
  --exclude '*.pyc' --exclude '__pycache__' \
  --progress \
  "$CIRCUITPY_MOUNT/" "$BACKUP_DIR/"

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✓${NC} Rsync backup completed successfully"
else
    echo -e "\n${RED}ERROR: Rsync backup failed${NC}"
    exit 1
fi

# Calculate backup size
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo "Backup size: $BACKUP_SIZE"

# Create compressed tarball
echo ""
echo "Creating compressed tarball..."
( cd "$BACKUP_ROOT" && tar -czf "$(basename "$TARBALL")" "$(basename "$BACKUP_DIR")" )

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Tarball created: $TARBALL"
    TARBALL_SIZE=$(du -sh "$TARBALL" | cut -f1)
    echo "Compressed size: $TARBALL_SIZE"
else
    echo -e "${RED}ERROR: Tarball creation failed${NC}"
    exit 1
fi

# List recent backups
echo ""
echo "========================================="
echo "Recent CIRCUITPY backups:"
echo "========================================="
ls -lht "$BACKUP_ROOT" | grep -E "(CIRCUITPY_|total)" | head -n 11

echo ""
echo -e "${GREEN}✓ Backup complete!${NC}"
echo ""
echo "Backup location: $BACKUP_DIR"
echo "Tarball: $TARBALL"
echo ""
echo "To restore from this backup, use: ./scripts/rollback_circuitpy.sh"
