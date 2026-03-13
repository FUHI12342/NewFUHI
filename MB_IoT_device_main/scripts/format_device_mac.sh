#!/bin/bash
# format_device_mac.sh
# Format CIRCUITPY device to FAT12 for clean deployment
# CAUTION: This will erase ALL data on the device!

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${YELLOW}╔════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║  ⚠ CIRCUITPY DEVICE FORMAT TOOL          ║${NC}"
echo -e "${YELLOW}║  This will ERASE ALL DATA on the device!  ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════╝${NC}"
echo ""

# Check if diskutil is available
if ! command -v diskutil &> /dev/null; then
    echo -e "${RED}ERROR: diskutil command not found${NC}"
    echo "This script requires macOS with diskutil"
    exit 1
fi

# Display current disk list
echo -e "${BLUE}Current disks:${NC}"
diskutil list
echo ""

# Check if CIRCUITPY is mounted
if [ -d "/Volumes/CIRCUITPY" ]; then
    echo -e "${GREEN}CIRCUITPY is currently mounted at /Volumes/CIRCUITPY${NC}"
    echo ""
    echo -e "${BLUE}Device information:${NC}"
    diskutil info /Volumes/CIRCUITPY | grep -E '(Device Node|Volume Name|File System|Total Size|Device Block Size)'
    echo ""
    
    # Extract device node
    DEVICE_NODE=$(diskutil info /Volumes/CIRCUITPY | grep "Device Node" | awk '{print $3}')
    
    if [ -n "$DEVICE_NODE" ]; then
        echo -e "${YELLOW}Auto-detected device node: $DEVICE_NODE${NC}"
        echo ""
    fi
else
    echo -e "${YELLOW}WARNING: CIRCUITPY is not currently mounted at /Volumes/CIRCUITPY${NC}"
    echo "Please connect your Pico 2 W device via USB"
    echo ""
fi

# Get device node from argument or prompt
if [ $# -eq 0 ]; then
    echo -e "${BLUE}Usage:${NC}"
    echo "  $0 <device_node>"
    echo ""
    echo -e "${BLUE}Example:${NC}"
    echo "  $0 /dev/disk4"
    echo ""
    echo "To find your device node:"
    echo "  1. Identify the CIRCUITPY disk from 'diskutil list' above"
    echo "  2. Look for the device identifier (e.g., disk4)"
    echo "  3. Use the full path: /dev/disk4"
    echo ""
    
    read -p "Enter device node (or press Ctrl+C to cancel): " DEVICE_INPUT
    DEVICE_NODE="$DEVICE_INPUT"
else
    DEVICE_NODE="$1"
fi

# Validate device node format
if [[ ! "$DEVICE_NODE" =~ ^/dev/disk[0-9]+$ ]]; then
    echo -e "${RED}ERROR: Invalid device node format: $DEVICE_NODE${NC}"
    echo "Expected format: /dev/diskN (e.g., /dev/disk4)"
    exit 1
fi

# Check if device exists
if [ ! -e "$DEVICE_NODE" ]; then
    echo -e "${RED}ERROR: Device not found: $DEVICE_NODE${NC}"
    echo "Please check 'diskutil list' for available devices"
    exit 1
fi

# Display selected device info
echo ""
echo -e "${BLUE}Selected device information:${NC}"
diskutil info "$DEVICE_NODE" 2>/dev/null || {
    echo -e "${RED}ERROR: Cannot get info for $DEVICE_NODE${NC}"
    exit 1
}
echo ""

# Safety confirmation
echo -e "${RED}⚠ WARNING: This will PERMANENTLY ERASE all data on $DEVICE_NODE ⚠${NC}"
echo ""
read -p "Type 'YES' in all caps to confirm: " CONFIRMATION

if [ "$CONFIRMATION" != "YES" ]; then
    echo "Format cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}Formatting $DEVICE_NODE as MS-DOS (FAT) with name CIRCUITPY...${NC}"

# Unmount if mounted
diskutil unmountDisk "$DEVICE_NODE" 2>/dev/null || true

# Format the device
# MS-DOS = FAT32 (diskutil will choose FAT12 for small volumes automatically)
if diskutil eraseDisk MS-DOS CIRCUITPY MBRFormat "$DEVICE_NODE"; then
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ FORMAT SUCCESSFUL               ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════╝${NC}"
    echo ""
    echo "Device formatted as FAT filesystem with label CIRCUITPY"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Wait for CIRCUITPY to mount (should appear automatically)"
    echo "  2. Verify: ls -la /Volumes/CIRCUITPY"
    echo "  3. Deploy code: ./scripts/deploy_mac.sh"
    echo ""
    echo -e "${YELLOW}Note: You may need to reinstall CircuitPython firmware if the device doesn't boot.${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}╔════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ✗ FORMAT FAILED                   ║${NC}"
    echo -e "${RED}╚════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo "  - Ensure device is not in use by another application"
    echo "  - Try disconnecting and reconnecting the USB cable"
    echo "  - Check if the device is write-protected"
    echo "  - Verify correct device node with 'diskutil list'"
    exit 1
fi
