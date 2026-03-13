#!/bin/bash
# clean_macos_metadata.sh
# Removes macOS metadata files from CIRCUITPY volume
# Preserves system directories (.Trashes, .fseventsd)

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

MOUNT_POINT="/Volumes/CIRCUITPY"

log_info "Cleaning macOS metadata from CIRCUITPY..."

# Check if CIRCUITPY is mounted
if [ ! -d "$MOUNT_POINT" ]; then
    log_error "CIRCUITPY not mounted at $MOUNT_POINT"
    exit 1
fi

# Step 1: Run dot_clean to merge AppleDouble files
if command -v dot_clean &> /dev/null; then
    log_info "Running dot_clean to merge AppleDouble files..."
    if dot_clean -m "$MOUNT_POINT" 2>/dev/null; then
        log_success "dot_clean completed"
    else
        log_warn "dot_clean had warnings (non-fatal, continuing)"
    fi
else
    log_warn "dot_clean not found (skipping)"
fi

# Step 2: Remove ._* files (excluding .Trashes and .fseventsd)
log_info "Removing AppleDouble (._*) files..."
REMOVED_COUNT=0

# Use find with -prune to exclude system directories
while IFS= read -r -d '' file; do
    if rm -f "$file" 2>/dev/null; then
        ((REMOVED_COUNT++)) || true
    fi
done < <(find "$MOUNT_POINT" \( -path "$MOUNT_POINT/.Trashes*" -o -path "$MOUNT_POINT/.fseventsd*" \) -prune -o -name '._*' -type f -print0)

log_success "Removed $REMOVED_COUNT AppleDouble files"

# Step 3: Remove .DS_Store files (excluding .Trashes and .fseventsd)
log_info "Removing .DS_Store files..."
DS_STORE_COUNT=0

while IFS= read -r -d '' file; do
    if rm -f "$file" 2>/dev/null; then
        ((DS_STORE_COUNT++)) || true
    fi
done < <(find "$MOUNT_POINT" \( -path "$MOUNT_POINT/.Trashes*" -o -path "$MOUNT_POINT/.fseventsd*" \) -prune -o -name '.DS_Store' -type f -print0)

log_success "Removed $DS_STORE_COUNT .DS_Store files"

# Step 4: Verify cleanup
log_info "Verifying cleanup..."
REMAINING_METADATA=$(find "$MOUNT_POINT" \( -path "$MOUNT_POINT/.Trashes*" -o -path "$MOUNT_POINT/.fseventsd*" \) -prune -o \( -name '._*' -o -name '.DS_Store' \) -type f -print 2>/dev/null | wc -l | tr -d ' ')

if [ "$REMAINING_METADATA" -eq 0 ]; then
    log_success "No metadata pollution detected"
else
    log_warn "Found $REMAINING_METADATA remaining metadata files"
fi

log_success "Metadata cleanup complete"
