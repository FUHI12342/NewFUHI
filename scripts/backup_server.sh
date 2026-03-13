#!/bin/bash
# backup_server.sh
# Server-side script to backup Nginx configuration and service status
# Run this on timebaibai.com server via SSH

set -e  # Exit on error

# Configuration
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_BASE="/var/backups/timebaibai_$TIMESTAMP"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "========================================"
echo "  Server Backup Script"
echo "  Timestamp: $TIMESTAMP"
echo "========================================"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}ERROR: This script must be run with sudo${NC}"
    echo "Usage: sudo $0"
    exit 1
fi

# Create backup directory
echo "Creating backup directory: $BACKUP_BASE"
mkdir -p "$BACKUP_BASE"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Backup directory created"
else
    echo -e "${RED}ERROR: Failed to create backup directory${NC}"
    exit 1
fi

# Backup Nginx configuration directory
echo ""
echo "Backing up Nginx configuration..."
cp -a /etc/nginx "$BACKUP_BASE/nginx"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Nginx configuration backed up"
else
    echo -e "${RED}ERROR: Failed to backup Nginx configuration${NC}"
    exit 1
fi

# Capture full Nginx configuration test output
echo ""
echo "Capturing Nginx test output (nginx -T)..."
nginx -T > "$BACKUP_BASE/nginx_T.txt" 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Nginx test output saved"
else
    echo -e "${YELLOW}⚠${NC} Nginx test may have warnings (check nginx_T.txt)"
fi

# Capture Nginx service status
echo ""
echo "Capturing service status..."
systemctl status nginx > "$BACKUP_BASE/nginx_status.txt" 2>&1 || true
echo -e "${GREEN}✓${NC} Nginx service status saved"

# Capture Gunicorn service status (for Django)
systemctl status gunicorn > "$BACKUP_BASE/gunicorn_status.txt" 2>&1 || true
echo -e "${GREEN}✓${NC} Gunicorn service status saved"

# Create a backup metadata file
cat > "$BACKUP_BASE/backup_info.txt" <<EOF
Backup Information
==================
Timestamp: $TIMESTAMP
Hostname: $(hostname)
Date: $(date)
User: $(whoami)

Nginx Version:
$(nginx -v 2>&1)

Backed up:
- /etc/nginx/ -> $BACKUP_BASE/nginx/
- nginx -T output -> $BACKUP_BASE/nginx_T.txt
- nginx service status -> $BACKUP_BASE/nginx_status.txt
- gunicorn service status -> $BACKUP_BASE/gunicorn_status.txt
EOF

echo -e "${GREEN}✓${NC} Backup metadata saved"

# Set proper permissions (readable by backup user)
chmod -R u=rwX,go=rX "$BACKUP_BASE"

# List backup contents
echo ""
echo "========================================="
echo "Backup contents:"
echo "========================================="
ls -lah "$BACKUP_BASE"

echo ""
echo -e "${GREEN}✓ Server backup complete!${NC}"
echo ""
echo "Backup location: $BACKUP_BASE"
echo ""
echo "To restore from this backup, use: ./scripts/rollback_server.sh"
