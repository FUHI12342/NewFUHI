#!/bin/bash
# deploy_to_circuitpy.sh
# FAT12-safe deployment script for CIRCUITPY
# Supports: --dry-run, --force-secrets, --danger-delete

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }

# Default options
DRY_RUN=false
FORCE_SECRETS=false
DANGER_DELETE=false
MOUNT_POINT="/Volumes/CIRCUITPY"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run|-n)
            DRY_RUN=true
            shift
            ;;
        --force-secrets)
            FORCE_SECRETS=true
            shift
            ;;
        --danger-delete)
            DANGER_DELETE=true
            shift
            ;;
        *)
            log_error "Unknown argument: $1"
            echo "Usage: $0 [--dry-run] [--force-secrets] [--danger-delete]"
            echo ""
            echo "Options:"
            echo "  --dry-run          Show what would be deployed without making changes"
            echo "  --force-secrets    Overwrite existing secrets.py on device"
            echo "  --danger-delete    Enable rsync --delete (DANGEROUS on FAT12!)"
            exit 1
            ;;
    esac
done

log_info "CIRCUITPY Deployment (FAT12-safe)"
if [ "$DRY_RUN" = true ]; then
    log_warn "DRY RUN MODE - No changes will be made"
fi
echo ""

# Check if CIRCUITPY is mounted
if [ ! -d "$MOUNT_POINT" ]; then
    log_error "CIRCUITPY not mounted at $MOUNT_POINT"
    log_info "Please connect your Pico 2 W device"
    exit 1
fi

log_success "CIRCUITPY mounted at $MOUNT_POINT"

# Display device info
if command -v diskutil &> /dev/null; then
    DEVICE_NODE=$(diskutil info "$MOUNT_POINT" 2>/dev/null | grep "Device Node" | awk '{print $3}')
    FILE_SYSTEM=$(diskutil info "$MOUNT_POINT" 2>/dev/null | grep "Type (Bundle)" | awk -F': ' '{print $2}')
    log_info "Device: $DEVICE_NODE ($FILE_SYSTEM)"
fi

# Determine source directory
if [ -f "$PROJECT_ROOT/code.py" ] && [ -d "$PROJECT_ROOT/lib" ]; then
    SOURCE_DIR="$PROJECT_ROOT"
    log_info "Source: $SOURCE_DIR"
else
    log_error "Cannot find code.py and lib/ in $PROJECT_ROOT"
    exit 1
fi

# Secrets protection check
if [ -f "$MOUNT_POINT/secrets.py" ] && [ "$FORCE_SECRETS" = false ]; then
    log_warn "secrets.py exists on device and will NOT be overwritten"
    log_info "  (Use --force-secrets to overwrite)"
    EXCLUDE_SECRETS="--exclude=secrets.py"
else
    EXCLUDE_SECRETS=""
    if [ "$FORCE_SECRETS" = true ]; then
        log_warn "secrets.py will be OVERWRITTEN (--force-secrets enabled)"
    fi
fi

# Danger delete warning
RSYNC_DELETE=""
if [ "$DANGER_DELETE" = true ]; then
    log_warn "⚠️  --danger-delete ENABLED: Files not in source will be DELETED"
    log_warn "⚠️  This is DANGEROUS on FAT12 and may cause corruption!"
    if [ "$DRY_RUN" = false ]; then
        echo ""
        read -p "Type 'DELETE' to confirm: " CONFIRM
        if [ "$CONFIRM" != "DELETE" ]; then
            log_info "Cancelled"
            exit 0
        fi
    fi
    RSYNC_DELETE="--delete"
fi

# Build rsync command
RSYNC_OPTS="-av"
if [ "$DRY_RUN" = true ]; then
    RSYNC_OPTS="$RSYNC_OPTS -n"
fi

echo ""
log_info "Starting deployment..."

# Execute rsync with FAT12-safe options
if rsync $RSYNC_OPTS \
    --inplace \
    --omit-dir-times \
    --no-perms \
    --no-owner \
    --no-group \
    $RSYNC_DELETE \
    --exclude='.Trashes/' \
    --exclude='.Trashes' \
    --exclude='.fseventsd/' \
    --exclude='.fseventsd' \
    --exclude='.Spotlight-V100/' \
    --exclude='.Spotlight-V100' \
    --exclude='.vscode/' \
    --exclude='._*' \
    --exclude='.DS_Store' \
    --exclude='__pycache__/' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git/' \
    --exclude='.gitignore' \
    --exclude='scripts/' \
    --exclude='docs/' \
    --exclude='*.md' \
    --exclude='*.sh' \
    --exclude='*.bak' \
    --exclude='*.disabled' \
    --exclude='*.disabled.py' \
    --exclude='*.example.py' \
    --exclude='*.sample' \
    --exclude='MB_IoT.code-workspace' \
    --exclude='*.uf2' \
    $EXCLUDE_SECRETS \
    "$SOURCE_DIR/" "$MOUNT_POINT/"; then
    log_success "Rsync completed"
else
    log_error "Rsync failed"
    echo ""
    log_info "Common causes:"
    log_info "  - USB connection interrupted"
    log_info "  - Device rebooted mid-transfer (disable AutoReload)"
    log_info "  - Filesystem corruption (try: ./scripts/format_circuitpy.sh)"
    exit 1
fi

# Skip post-deployment steps in dry-run mode
if [ "$DRY_RUN" = true ]; then
    echo ""
    log_info "Dry run complete. No changes were made."
    log_info "Run without --dry-run to perform actual deployment."
    exit 0
fi

# Post-deployment: Clean macOS metadata
echo ""
log_info "Running metadata cleanup..."
if [ -f "$SCRIPT_DIR/clean_macos_metadata.sh" ]; then
    if "$SCRIPT_DIR/clean_macos_metadata.sh"; then
        log_success "Metadata cleanup completed"
    else
        log_warn "Metadata cleanup had warnings (non-fatal)"
    fi
else
    log_warn "clean_macos_metadata.sh not found (skipping)"
fi

# Post-deployment: Sync filesystem
log_info "Syncing filesystem..."
sync
log_success "Filesystem synced"

# Post-deployment: Health check
echo ""
log_info "Running health check..."
if [ -f "$SCRIPT_DIR/healthcheck_circuitpy.sh" ]; then
    if "$SCRIPT_DIR/healthcheck_circuitpy.sh"; then
        echo ""
        log_success "╔════════════════════════════════════╗"
        log_success "║  DEPLOYMENT SUCCESSFUL ✓           ║"
        log_success "╚════════════════════════════════════╝"
        echo ""
        log_info "Next steps:"
        log_info "  1. Eject device: diskutil unmount $MOUNT_POINT"
        log_info "  2. Device will reboot automatically"
        log_info "  3. Monitor serial output for errors"
        exit 0
    else
        echo ""
        log_error "╔════════════════════════════════════╗"
        log_error "║  HEALTH CHECK FAILED ✗             ║"
        log_error "╚════════════════════════════════════╝"
        exit 1
    fi
else
    log_warn "healthcheck_circuitpy.sh not found (skipping)"
    log_success "Deployment completed (health check skipped)"
    exit 0
fi
