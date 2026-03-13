#!/bin/bash
# complete_deployment.sh
# Complete deployment and verification workflow
# Orchestrates server + Pico 2W deployment with verification

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "  Complete IoT Diagnostics Deployment"
echo "  $(date)"
echo "========================================"
echo ""

# Function to mask secrets
mask_secret() {
    local value="$1"
    local len=${#value}
    if [ $len -le 4 ]; then
        echo "****"
    else
        echo "${value:0:2}***${value: -2}"
    fi
}

# Phase 1: Mac-side backup
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}Phase 1: Mac-Side Backup${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ -d "/Volumes/CIRCUITPY" ]; then
    echo -e "${BLUE}Running CIRCUITPY backup...${NC}"
    if [ -f "$SCRIPT_DIR/backup_circuitpy.sh" ]; then
        "$SCRIPT_DIR/backup_circuitpy.sh"
    else
        echo -e "${YELLOW}⚠ backup_circuitpy.sh not found, skipping${NC}"
    fi
else
    echo -e "${YELLOW}⚠ CIRCUITPY not mounted, skipping backup${NC}"
    echo "  If you want to deploy to Pico, please connect it first"
fi

echo ""

# Phase 2: Server-side deployment instructions
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}Phase 2: Server-Side Configuration${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo "To configure Nginx on timebaibai.com server:"
echo ""
echo "1. Copy the script to server:"
echo -e "   ${GREEN}scp -i newfuhi-key.pem scripts/apply_nginx_iot_config.sh ubuntu@<server-ip>:~/${NC}"
echo ""
echo "2. SSH to server:"
echo -e "   ${GREEN}ssh -i newfuhi-key.pem ubuntu@<server-ip>${NC}"
echo ""
echo "3. Run configuration script:"
echo -e "   ${GREEN}sudo bash apply_nginx_iot_config.sh${NC}"
echo ""
echo "4. Verify (from Mac):"
echo -e "   ${GREEN}curl -i -H \"X-API-KEY: <key>\" \"https://timebaibai.com/booking/api/iot/config/\"${NC}"
echo ""

read -p "Have you completed server configuration? (y/n): " SERVER_DONE

if [ "$SERVER_DONE" != "y" ] && [ "$SERVER_DONE" != "Y" ]; then
    echo -e "${YELLOW}⚠ Server configuration pending${NC}"
    echo "Please complete server setup and re-run this script"
    exit 0
fi

echo ""

# Phase 3: Pico 2W deployment
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}Phase 3: Pico 2W Deployment${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ ! -d "/Volumes/CIRCUITPY" ]; then
    echo -e "${YELLOW}⚠ CIRCUITPY not mounted${NC}"
    echo "Please connect Pico 2W and press Enter..."
    read
fi

if [ -d "/Volumes/CIRCUITPY" ]; then
    echo -e "${BLUE}Deploying diagnostics to Pico 2W...${NC}"
    
    if [ -f "$SCRIPT_DIR/deploy_diagnostics_to_pico.sh" ]; then
        "$SCRIPT_DIR/deploy_diagnostics_to_pico.sh"
        
        echo ""
        echo "Enable diagnostic mode? (y/n): "
        read ENABLE_DIAG
        
        if [ "$ENABLE_DIAG" = "y" ] || [ "$ENABLE_DIAG" = "Y" ]; then
            "$SCRIPT_DIR/deploy_diagnostics_to_pico.sh" --enable-diag
        fi
    else
        echo -e "${RED}ERROR: deploy_diagnostics_to_pico.sh not found${NC}"
        exit 1
    fi
else
    echo -e "${RED}ERROR: CIRCUITPY still not available${NC}"
    exit 1
fi

echo ""

# Phase 4: Verification instructions
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}Phase 4: Verification${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo "Complete the following verification steps:"
echo ""
echo "A. Server Verification:"
echo "   Test that IoT API no longer requires Basic auth:"
echo ""
echo -e "   ${GREEN}curl -i \\"
echo "     -H \"X-API-KEY: <your-api-key>\" \\"
echo "     \"https://timebaibai.com/booking/api/iot/config/?device=pico2w_001\" \\"
echo -e "     | head -n 30${NC}"
echo ""
echo "   Expected: NO 'WWW-Authenticate: Basic' header"
echo "   Status should be 200/403/404, NOT 401"
echo ""

echo "B. Root Path Still Protected:"
echo -e "   ${GREEN}curl -i \"https://timebaibai.com/\" | head -n 20${NC}"
echo ""
echo "   Expected: 401 Unauthorized with 'WWW-Authenticate: Basic'"
echo ""

echo "C. Pico 2W Diagnostics:"
echo "   1. Safely eject CIRCUITPY"
echo "   2. Press RESET button on Pico 2W"
echo "   3. Connect serial monitor (screen /dev/tty.usbmodem* 115200)"
echo "   4. Watch diagnostic output"
echo "   5. Respond to interactive tests (button, PIR, light sensor)"
echo "   6. After completion, check /Volumes/CIRCUITPY/diag_report.json"
echo ""

echo "D. Django Integration:"
echo "   SSH to server and check for diagnostic report:"
echo -e "   ${GREEN}sudo journalctl -u gunicorn -n 100 --no-pager | grep -i diagnostic${NC}"
echo ""

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ Deployment orchestration complete!${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Next: Execute verification commands above"
echo ""
