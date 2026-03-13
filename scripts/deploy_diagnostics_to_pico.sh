#!/bin/bash
# deploy_diagnostics_to_pico.sh
# Deploy diagnostic mode to Pico 2W (CIRCUITPY)
# Usage: ./deploy_diagnostics_to_pico.sh [--enable-diag|--disable-diag]

set -e

# Configuration
CIRCUITPY="/Volumes/CIRCUITPY"
SOURCE_DIR="$(cd "$(dirname "$0")/.." && pwd)/MB_IoT_device_main"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

MODE="deploy"  # deploy, enable-diag, disable-diag

# Parse arguments
if [ "$1" = "--enable-diag" ]; then
    MODE="enable-diag"
elif [ "$1" = "--disable-diag" ]; then
    MODE="disable-diag"
fi

echo "========================================"
echo "  Pico 2W Diagnostics Deployment"
echo "  Mode: $MODE"
echo "========================================"
echo ""

# Check if CIRCUITPY is mounted
if [ ! -d "$CIRCUITPY" ]; then
    echo -e "${RED}ERROR: CIRCUITPY not found at $CIRCUITPY${NC}"
    echo "Please connect Pico 2W via USB and ensure CIRCUITPY is mounted"
    exit 1
fi

echo -e "${GREEN}✓${NC} CIRCUITPY found at $CIRCUITPY"

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo -e "${RED}ERROR: Source directory not found: $SOURCE_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Source directory: $SOURCE_DIR"
echo ""

if [ "$MODE" = "enable-diag" ] || [ "$MODE" = "disable-diag" ]; then
    # Just toggle DIAGNOSTIC_MODE in secrets.py
    SECRETS_FILE="$CIRCUITPY/secrets.py"
    
    if [ ! -f "$SECRETS_FILE" ]; then
        echo -e "${RED}ERROR: secrets.py not found on CIRCUITPY${NC}"
        exit 1
    fi
    
    if [ "$MODE" = "enable-diag" ]; then
        echo -e "${BLUE}Enabling DIAGNOSTIC_MODE in secrets.py...${NC}"
        sed -i '' 's/"DIAGNOSTIC_MODE"[[:space:]]*:[[:space:]]*False/"DIAGNOSTIC_MODE": True/' "$SECRETS_FILE"
        echo -e "${GREEN}✓${NC} DIAGNOSTIC_MODE = True"
    else
        echo -e "${BLUE}Disabling DIAGNOSTIC_MODE in secrets.py...${NC}"
        sed -i '' 's/"DIAGNOSTIC_MODE"[[:space:]]*:[[:space:]]*True/"DIAGNOSTIC_MODE": False/' "$SECRETS_FILE"
        echo -e "${GREEN}✓${NC} DIAGNOSTIC_MODE = False"
    fi
    
    echo ""
    echo "Current DIAGNOSTIC_MODE setting:"
    grep "DIAGNOSTIC_MODE" "$SECRETS_FILE"
    echo ""
    echo -e "${GREEN}✓ Done!${NC}"
    echo "Safely eject CIRCUITPY and reset Pico 2W to apply changes"
    exit 0
fi

# Full deployment mode
echo -e "${BLUE}Step 1: Backing up current CIRCUITPY...${NC}"

BACKUP_SCRIPT="$(dirname "$0")/backup_circuitpy.sh"
if [ -f "$BACKUP_SCRIPT" ]; then
    "$BACKUP_SCRIPT"
else
    echo -e "${YELLOW}⚠${NC} Backup script not found, skipping backup"
fi

echo ""
echo -e "${BLUE}Step 2: Copying files to CIRCUITPY...${NC}"

# Core files to deploy
FILES_TO_DEPLOY=(
    "diagnostics.py"
    "code.py"
)

# Optional: Copy all if doing full deployment
# For diagnostics, we just need diagnostics.py and updated code.py
for file in "${FILES_TO_DEPLOY[@]}"; do
    if [ -f "$SOURCE_DIR/$file" ]; then
        echo "  Copying $file..."
        cp "$SOURCE_DIR/$file" "$CIRCUITPY/"
    else
        echo -e "${YELLOW}  ⚠ $file not found in source, skipping${NC}"
    fi
done

# Copy essential libraries (if not already there)
echo ""
echo -e "${BLUE}Step 3: Checking essential libraries...${NC}"

LIBS_NEEDED=(
    "pico_device"
    "sensors"
    "actuators"
)

for lib in "${LIBS_NEEDED[@]}"; do
    if [ -d "$SOURCE_DIR/$lib" ] && [ ! -d "$CIRCUITPY/$lib" ]; then
        echo "  Copying library: $lib/"
        cp -r "$SOURCE_DIR/$lib" "$CIRCUITPY/"
    else
        echo "  ✓ $lib already present or not needed"
    fi
done

# Check if secrets.py exists on CIRCUITPY
echo ""
echo -e "${BLUE}Step 4: Checking secrets.py...${NC}"

if [ ! -f "$CIRCUITPY/secrets.py" ]; then
    echo -e "${YELLOW}⚠ secrets.py not found on CIRCUITPY${NC}"
    
    if [ -f "$SOURCE_DIR/secrets.example.py" ]; then
        echo "  Copying secrets.example.py as template..."
        cp "$SOURCE_DIR/secrets.example.py" "$CIRCUITPY/secrets.py"
        echo -e "${YELLOW}  ⚠ Please edit secrets.py with your WiFi and API credentials${NC}"
    fi
else
    echo -e "${GREEN}✓${NC} secrets.py exists"
    
    # Show current DIAGNOSTIC_MODE status (without revealing secrets)
    echo "  Current DIAGNOSTIC_MODE:"
    grep "DIAGNOSTIC_MODE" "$CIRCUITPY/secrets.py" || echo "  (not set)"
fi

echo ""
echo -e "${BLUE}Step 5: Syncing filesystem...${NC}"
sync

echo -e "${GREEN}✓${NC} Filesystem synced"

echo ""
echo "========================================"
echo -e "${GREEN}✓ Deployment Complete!${NC}"
echo "========================================"
echo ""
echo "Files deployed to: $CIRCUITPY"
echo ""
echo "Next steps:"
echo "1. Verify secrets.py has correct credentials (NOT dummy values)"
echo "2. To enable diagnostics:"
echo "   $0 --enable-diag"
echo "3. Safely eject CIRCUITPY"
echo "4. Press RESET button on Pico 2W"
echo "5. Connect serial monitor to see diagnostic output"
echo ""
echo "To disable diagnostics mode:"
echo "   $0 --disable-diag"
echo ""
