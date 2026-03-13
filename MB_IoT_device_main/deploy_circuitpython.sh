#!/bin/bash
# deploy_circuitpython.sh
# Hardened deployment script for Pico 2 W
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Harden Deployment Starting ===${NC}"

# Find CIRCUITPY
MOUNT_POINT=""
if [ -d "/Volumes/CIRCUITPY" ]; then MOUNT_POINT="/Volumes/CIRCUITPY"
elif [ -d "/media/$USER/CIRCUITPY" ]; then MOUNT_POINT="/media/$USER/CIRCUITPY"
else
    M="/media/$(whoami)/CIRCUITPY"
    if [ -d "$M" ]; then MOUNT_POINT="$M"; else echo -e "${RED}ERROR: CIRCUITPY not found${NC}"; exit 1; fi
fi
echo "Target: ${MOUNT_POINT}"

# 1. Conflict Guard: dir must be dir
fix_dir() {
    local t="${MOUNT_POINT}/$1"
    if [ -f "$t" ]; then
        echo -e "${YELLOW}CONFLICT: $t is a file. Converting...${NC}"
        # FAT/CPY mount friendly: cp -> rm -> mkdir (avoid mv/rename)
        cp -a "$t" "${t}.FILE.bak" 2>/dev/null || true
        rm -f "$t" || exit 1
    fi
    mkdir -p "$t" || exit 1
}
fix_dir "sensors"
fix_dir "actuators"
fix_dir "lib"

# 2. Main Files
FILES=("code.py" "django_api.py" "provisioning.py")
for f in "${FILES[@]}"; do
    if [ -f "$f" ]; then cp -f "$f" "${MOUNT_POINT}/"; fi
done

# 3. Recursive Sync
sync_dir() {
    local s="$1"
    local d="${MOUNT_POINT}/$1"
    if [ -d "$s" ]; then
        echo "Syncing $s/ ..."
        case "$d" in "$MOUNT_POINT"/*) ;; *) echo "GUARD FAIL"; exit 1;; esac
        rm -rf "${d:?}/"*
        cp -Rf "$s"/* "$d"/
    fi
}
sync_dir "sensors"
sync_dir "actuators"
sync_dir "lib"

# 4. Secrets (Caution)
if [ -f "secrets.py" ]; then
    if [ ! -f "${MOUNT_POINT}/secrets.py" ]; then
        cp -f secrets.py "${MOUNT_POINT}/"
    else
        echo -e "${YELLOW}secrets.py exists on device. Use --force-secrets to overwrite (manual). Skipping.${NC}"
    fi
fi

sync

# 5. Verification Phase
echo -e "\n${GREEN}Verification Phase...${NC}"
FAIL=0

check_sha() {
    local f=$1
    if [ ! -f "$f" ]; then return 0; fi
    if [ ! -f "${MOUNT_POINT}/$f" ]; then
        echo -e "${RED}FAIL: $f missing on device!${NC}"
        FAIL=1
        return 0
    fi
    local hs=$(shasum "$f" | awk '{print $1}')
    local ds=$(shasum "${MOUNT_POINT}/$f" | awk '{print $1}')
    if [ "$hs" == "$ds" ]; then
        echo "OK: $f hash match"
    else
        echo -e "${RED}FAIL: $f hash mismatch!${NC}"
        FAIL=1
    fi
}

check_sha "code.py"
check_sha "django_api.py"
check_sha "provisioning.py"
check_sha "sensors/button.py"

# Grep Guard: No is_pressed in device code.py
if grep -q "is_pressed" "${MOUNT_POINT}/code.py"; then
    echo -e "${RED}CRITICAL: device code.py still contains 'is_pressed'!${NC}"
    FAIL=1
else
    echo "OK: device code.py grep clean"
fi

if [ $FAIL -eq 1 ]; then
    echo -e "${RED}\nDEPLOYMENT FAILED.${NC}"
    exit 1
fi

sync
echo -e "\n${GREEN}DONE. Verified.🚀${NC}"