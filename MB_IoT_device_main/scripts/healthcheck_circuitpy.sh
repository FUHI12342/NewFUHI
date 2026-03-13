#!/bin/bash
# healthcheck_circuitpy.sh
# Verifies CIRCUITPY deployment integrity
# Checks critical files and library structure

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
log_pass() { echo -e "${GREEN}[PASS]${NC} $*"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $*"; }

MOUNT_POINT="/Volumes/CIRCUITPY"
FAILED=0

log_info "CIRCUITPY Health Check"
echo ""

# Check 1: CIRCUITPY mounted
log_info "Check 1: CIRCUITPY mount status"
if [ -d "$MOUNT_POINT" ]; then
    log_pass "CIRCUITPY is mounted at $MOUNT_POINT"
else
    log_fail "CIRCUITPY is NOT mounted at $MOUNT_POINT"
    ((FAILED++))
fi

# Check 2: code.py exists
log_info "Check 2: code.py exists"
if [ -f "$MOUNT_POINT/code.py" ]; then
    SIZE=$(stat -f%z "$MOUNT_POINT/code.py" 2>/dev/null || echo "unknown")
    log_pass "code.py exists (size: $SIZE bytes)"
else
    log_fail "code.py is MISSING"
    ((FAILED++))
fi

# Check 3: lib/adafruit_character_lcd is a directory
log_info "Check 3: lib/adafruit_character_lcd integrity"
if [ -d "$MOUNT_POINT/lib/adafruit_character_lcd" ]; then
    FILE_COUNT=$(ls -1 "$MOUNT_POINT/lib/adafruit_character_lcd" 2>/dev/null | wc -l | tr -d ' ')
    log_pass "lib/adafruit_character_lcd is a directory ($FILE_COUNT files)"
elif [ -f "$MOUNT_POINT/lib/adafruit_character_lcd" ]; then
    log_fail "lib/adafruit_character_lcd is A FILE (metadata corruption!)"
    ((FAILED++))
else
    log_fail "lib/adafruit_character_lcd is MISSING"
    ((FAILED++))
fi

# Check 4: lib/adafruit_requests.mpy exists
log_info "Check 4: lib/adafruit_requests.mpy exists"
if [ -f "$MOUNT_POINT/lib/adafruit_requests.mpy" ]; then
    SIZE=$(stat -f%z "$MOUNT_POINT/lib/adafruit_requests.mpy" 2>/dev/null || echo "unknown")
    log_pass "adafruit_requests.mpy exists (size: $SIZE bytes)"
else
    log_fail "adafruit_requests.mpy is MISSING"
    ((FAILED++))
fi

# Check 5: lib/adafruit_connection_manager.mpy exists
log_info "Check 5: lib/adafruit_connection_manager.mpy exists"
if [ -f "$MOUNT_POINT/lib/adafruit_connection_manager.mpy" ]; then
    SIZE=$(stat -f%z "$MOUNT_POINT/lib/adafruit_connection_manager.mpy" 2>/dev/null || echo "unknown")
    log_pass "adafruit_connection_manager.mpy exists (size: $SIZE bytes)"
else
    log_fail "adafruit_connection_manager.mpy is MISSING"
    ((FAILED++))
fi

# Warning check: secrets.py
echo ""
log_info "Additional checks (WARN only):"
if [ -f "$MOUNT_POINT/secrets.py" ]; then
    log_pass "secrets.py exists"
else
    log_warn "secrets.py is MISSING (WiFi credentials required for operation)"
fi

# Metadata pollution check
METADATA_COUNT=$(find "$MOUNT_POINT" \( -path "$MOUNT_POINT/.Trashes*" -o -path "$MOUNT_POINT/.fseventsd*" \) -prune -o \( -name '._*' -o -name '.DS_Store' \) -type f -print 2>/dev/null | wc -l | tr -d ' ')
if [ "$METADATA_COUNT" -eq 0 ]; then
    log_pass "No metadata pollution detected"
else
    log_warn "Found $METADATA_COUNT metadata files (._* or .DS_Store)"
fi

# Summary
echo ""
if [ $FAILED -eq 0 ]; then
    log_success "╔════════════════════════════════════╗"
    log_success "║  ALL CHECKS PASSED ✓               ║"
    log_success "╚════════════════════════════════════╝"
    exit 0
else
    log_fail "╔════════════════════════════════════╗"
    log_fail "║  $FAILED CHECK(S) FAILED ✗            ║"
    log_fail "╚════════════════════════════════════╝"
    echo ""
    log_error "Deployment integrity compromised"
    log_info "Consider running: ./scripts/format_circuitpy.sh && ./scripts/deploy_to_circuitpy.sh"
    exit 1
fi
