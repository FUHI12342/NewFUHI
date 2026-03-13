#!/bin/bash
# rollback_server.sh
# Server-side script to restore Nginx configuration from backup
# Run this on timebaibai.com server via SSH

set -e  # Exit on error

# Configuration
BACKUP_BASE="/var/backups"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================"
echo "  Server Rollback Script"
echo "========================================"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}ERROR: This script must be run with sudo${NC}"
    echo "Usage: sudo $0"
    exit 1
fi

# Check if backup directory exists
if [ ! -d "$BACKUP_BASE" ]; then
    echo -e "${RED}ERROR: Backup directory not found at $BACKUP_BASE${NC}"
    exit 1
fi

# List available backups
echo "Available server backups:"
echo "========================================="
BACKUPS=($(ls -1dt "$BACKUP_BASE"/timebaibai_[0-9]*/ 2>/dev/null | head -n 10))

if [ ${#BACKUPS[@]} -eq 0 ]; then
    echo -e "${RED}ERROR: No server backups found in $BACKUP_BASE${NC}"
    exit 1
fi

# Display backups with numbers
for i in "${!BACKUPS[@]}"; do
    BACKUP_NAME=$(basename "${BACKUPS[$i]}")
    BACKUP_DATE=$(echo "$BACKUP_NAME" | sed 's/timebaibai_//' | sed 's/_/ /')
    if [ -f "${BACKUPS[$i]}/backup_info.txt" ]; then
        echo -e "${BLUE}[$((i+1))]${NC} $BACKUP_DATE"
        echo "    $(grep 'Date:' "${BACKUPS[$i]}/backup_info.txt" | sed 's/Date: //')"
    else
        echo -e "${BLUE}[$((i+1))]${NC} $BACKUP_DATE"
    fi
    echo ""
done

echo -e "${YELLOW}WARNING: This will REPLACE the current Nginx configuration!${NC}"
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

# Check if Nginx backup exists
if [ ! -d "$SELECTED_BACKUP/nginx" ]; then
    echo -e "${RED}ERROR: Nginx configuration not found in selected backup${NC}"
    exit 1
fi

# Show what will be restored
echo "This backup contains:"
ls -lh "$SELECTED_BACKUP"
echo ""

# Final confirmation
read -p "Are you sure you want to restore from this backup? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Rollback cancelled."
    exit 0
fi

# Create a safety backup of current config
SAFETY_BACKUP="/var/backups/nginx_before_rollback_$(date +%Y%m%d_%H%M%S)"
echo ""
echo "Creating safety backup of current configuration..."
mkdir -p "$SAFETY_BACKUP"
cp -a /etc/nginx "$SAFETY_BACKUP/"
echo -e "${GREEN}✓${NC} Safety backup created at: $SAFETY_BACKUP"

# Perform restoration
echo ""
echo "Restoring Nginx configuration from backup..."
rm -rf /etc/nginx
cp -a "$SELECTED_BACKUP/nginx" /etc/nginx

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Configuration files restored"
else
    echo -e "${RED}ERROR: Failed to restore configuration${NC}"
    echo "Restoring from safety backup..."
    cp -a "$SAFETY_BACKUP/nginx" /etc/nginx
    exit 1
fi

# Test the restored configuration
echo ""
echo "Testing restored Nginx configuration..."
nginx -t

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Configuration test passed"
else
    echo -e "${RED}ERROR: Configuration test failed!${NC}"
    echo "Restoring from safety backup..."
    rm -rf /etc/nginx
    cp -a "$SAFETY_BACKUP/nginx" /etc/nginx
    echo "Original configuration restored. Rollback aborted."
    exit 1
fi

# Ask for reload confirmation
echo ""
echo -e "${YELLOW}Configuration test passed.${NC}"
read -p "Reload Nginx to apply changes? (yes/no): " RELOAD_CONFIRM

if [ "$RELOAD_CONFIRM" = "yes" ]; then
    echo "Reloading Nginx..."
    systemctl reload nginx
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Nginx reloaded successfully"
    else
        echo -e "${RED}ERROR: Nginx reload failed${NC}"
        exit 1
    fi
else
    echo "Nginx not reloaded. Configuration restored but not active."
    echo "Run 'sudo systemctl reload nginx' manually to apply changes."
fi

echo ""
echo "========================================="
echo -e "${GREEN}✓ Rollback complete!${NC}"
echo "========================================="
echo ""
echo "Nginx configuration restored from: $BACKUP_NAME"
echo "Safety backup kept at: $SAFETY_BACKUP"
echo ""
