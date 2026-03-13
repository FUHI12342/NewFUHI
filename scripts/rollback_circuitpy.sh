#!/bin/bash
# rollback_circuitpy.sh
# Mac-side script to restore CIRCUITPY from a backup

set -e  # Exit on error

# Configuration
CIRCUITPY_MOUNT="/Volumes/CIRCUITPY"
BACKUP_ROOT="$HOME/NewFUHI/_backups"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================"
echo "  CIRCUITPY Rollback Script"
echo "========================================"
echo ""

# Check if CIRCUITPY is mounted
if [ ! -d "$CIRCUITPY_MOUNT" ]; then
    echo -e "${RED}ERROR: CIRCUITPY drive not found at $CIRCUITPY_MOUNT${NC}"
    echo "Please connect your Pico 2W and ensure CIRCUITPY is mounted."
    exit 1
fi

echo -e "${GREEN}✓${NC} CIRCUITPY drive found at $CIRCUITPY_MOUNT"

# Check if backup directory exists
if [ ! -d "$BACKUP_ROOT" ]; then
    echo -e "${RED}ERROR: Backup directory not found at $BACKUP_ROOT${NC}"
    echo "No backups available. Run backup_circuitpy.sh first."
    exit 1
fi

# List available backups
echo ""
echo "Available CIRCUITPY backups:"
echo "========================================="
BACKUPS=($(ls -1dt "$BACKUP_ROOT"/CIRCUITPY_[0-9]*/ 2>/dev/null | head -n 10))

if [ ${#BACKUPS[@]} -eq 0 ]; then
    echo -e "${RED}ERROR: No CIRCUITPY backups found in $BACKUP_ROOT${NC}"
    exit 1
fi

# Display backups with numbers
for i in "${!BACKUPS[@]}"; do
    BACKUP_NAME=$(basename "${BACKUPS[$i]}")
    BACKUP_SIZE=$(du -sh "${BACKUPS[$i]}" | cut -f1)
    BACKUP_DATE=$(echo "$BACKUP_NAME" | sed 's/CIRCUITPY_//' | sed 's/_/ /')
    echo -e "${BLUE}[$((i+1))]${NC} $BACKUP_DATE (Size: $BACKUP_SIZE)"
done

echo ""
echo -e "${YELLOW}WARNING: This will REPLACE all files on CIRCUITPY!${NC}"
echo ""

# Prompt user to select a backup
read -p "Select backup number to restore (1-${#BACKUPS[@]}) or 'q' to quit: " SELECTION

if [ "$SELECTION" = "q" ] || [ "$SELECTION" = "Q" ]; then
    echo "Rollback cancelled."
    exit 0
fi

# Validate selection
if ! [[ "$SELECTION" =~ ^[0-9]+$ ]] || [ "$SELECTION" -lt 1 ] || [ "$SELECTION" -gt ${#BACKUPS[@]} ]; then
    echo -e "${RED}ERROR: Invalid selection${NC}"
    exit 1
fi

# Get selected backup
SELECTED_BACKUP="${BACKUPS[$((SELECTION-1))]}"
BACKUP_NAME=$(basename "$SELECTED_BACKUP")

echo ""
echo "Selected backup: $BACKUP_NAME"
echo "Backup location: $SELECTED_BACKUP"
echo ""

# Final confirmation
read -p "Are you sure you want to restore from this backup? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Rollback cancelled."
    exit 0
fi

# Perform restoration
echo ""
echo "Restoring CIRCUITPY from backup..."
echo ""

rsync -a --delete \
  --exclude '.Trashes/**' --exclude '.Trashes' \
  --exclude '.fseventsd/**' --exclude '.fseventsd' \
  --exclude '.Spotlight-V100/**' --exclude '.Spotlight-V100' \
  --exclude '.TemporaryItems/**' --exclude '.TemporaryItems' \
  --progress \
  "$SELECTED_BACKUP/" "$CIRCUITPY_MOUNT/"

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✓${NC} Restoration completed successfully"
else
    echo -e "\n${RED}ERROR: Restoration failed${NC}"
    exit 1
fi

# Sync filesystem
echo ""
echo "Syncing filesystem..."
sync

echo -e "${GREEN}✓${NC} Filesystem synced"

echo ""
echo "========================================="
echo -e "${GREEN}✓ Rollback complete!${NC}"
echo "========================================="
echo ""
echo "CIRCUITPY has been restored from backup: $BACKUP_NAME"
echo ""
echo "You can now safely eject the CIRCUITPY drive and reset your Pico 2W."
