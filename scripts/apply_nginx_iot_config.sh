#!/bin/bash
# apply_nginx_iot_config.sh
# Automatically apply Nginx configuration for IoT API Basic auth bypass
# Run this on the server (timebaibai.com) after SSH

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================"
echo "  Nginx IoT API Configuration"
echo "  $(date)"
echo "========================================"
echo ""

# Check if running as root/sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}ERROR: This script must be run with sudo${NC}"
    echo "Usage: sudo $0"
    exit 1
fi

# Step 1: Backup
echo -e "${BLUE}Step 1: Creating backup...${NC}"
TS=$(date +%Y%m%d_%H%M%S)
BK="/var/backups/timebaibai_$TS"
mkdir -p "$BK"
cp -a /etc/nginx "$BK/nginx"
nginx -T > "$BK/nginx_T.txt" 2>&1

echo -e "${GREEN}✓${NC} Backup created: $BK"
echo ""

# Step 2: Identify server block
echo -e "${BLUE}Step 2: Identifying server block for timebaibai.com...${NC}"

# Find config file containing timebaibai.com
CONFIG_FILE=$(nginx -T 2>/dev/null | grep -B 20 "server_name.*timebaibai.com" | grep "# configuration file" | head -n 1 | awk '{print $4}' | tr -d ':')

if [ -z "$CONFIG_FILE" ]; then
    echo -e "${RED}ERROR: Could not find config file with server_name timebaibai.com${NC}"
    echo "Checking common locations..."
    
    # Try common locations
    for f in /etc/nginx/sites-available/timebaibai /etc/nginx/sites-available/default /etc/nginx/conf.d/timebaibai.conf; do
        if [ -f "$f" ]; then
            if grep -q "server_name.*timebaibai.com" "$f"; then
                CONFIG_FILE="$f"
                echo -e "${YELLOW}Found in: $CONFIG_FILE${NC}"
                break
            fi
        fi
    done
    
    if [ -z "$CONFIG_FILE" ]; then
        echo -e "${RED}ERROR: Cannot locate configuration file${NC}"
        echo "Please manually specify the file and edit this script."
        exit 1
    fi
fi

echo -e "${GREEN}✓${NC} Config file: $CONFIG_FILE"
echo ""

# Step 3: Check if IoT location already exists
echo -e "${BLUE}Step 3: Checking for existing IoT location block...${NC}"

if grep -q "location.*\/booking\/api\/iot\/" "$CONFIG_FILE"; then
    echo -e "${YELLOW}⚠${NC} IoT API location block already exists in config"
    echo "Checking if auth_basic is already off..."
    
    if nginx -T 2>/dev/null | grep -A 5 "location.*\/booking\/api\/iot\/" | grep -q "auth_basic off"; then
        echo -e "${GREEN}✓${NC} Configuration already correct (auth_basic off)"
        echo ""
        echo "Nothing to do. Exiting."
        exit 0
    else
        echo -e "${YELLOW}⚠${NC} Location exists but auth_basic not off"
        echo "Manual intervention required - please review $CONFIG_FILE"
        exit 1
    fi
fi

echo -e "${GREEN}✓${NC} No existing IoT location block found"
echo ""

# Step 4: Determine proxy_pass target
echo -e "${BLUE}Step 4: Detecting Django backend target...${NC}"

# Extract proxy_pass from existing location blocks
PROXY_TARGET=$(nginx -T 2>/dev/null | grep -A 10 "server_name.*timebaibai.com" | grep "proxy_pass" | head -n 1 | awk '{print $2}' | tr -d ';')

if [ -z "$PROXY_TARGET" ]; then
    # Default fallback
    PROXY_TARGET="http://127.0.0.1:8000"
    echo -e "${YELLOW}⚠${NC} Could not detect proxy target, using default: $PROXY_TARGET"
else
    echo -e "${GREEN}✓${NC} Detected proxy target: $PROXY_TARGET"
fi

echo ""

# Step 5: Create location block
echo -e "${BLUE}Step 5: Preparing IoT API location block...${NC}"

IOT_LOCATION_BLOCK="
    # IoT API - Bypass Basic authentication
    location ^~ /booking/api/iot/ {
        auth_basic off;
        
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_pass $PROXY_TARGET;
    }
"

echo "Location block to be added:"
echo "$IOT_LOCATION_BLOCK"
echo ""

# Step 6: Insert location block into config
echo -e "${BLUE}Step 6: Modifying configuration file...${NC}"

# Create temp file with modification
TEMP_CONFIG=$(mktemp)

# Strategy: Insert IoT location block right after the first "server {" line for timebaibai.com
awk -v iot_block="$IOT_LOCATION_BLOCK" '
/server_name.*timebaibai\.com/ {
    in_server = 1
}
in_server && !inserted && /location/ {
    print iot_block
    inserted = 1
}
{print}
' "$CONFIG_FILE" > "$TEMP_CONFIG"

# Check if insertion worked
if ! grep -q "location.*\/booking\/api\/iot\/" "$TEMP_CONFIG"; then
    echo -e "${RED}ERROR: Failed to insert location block${NC}"
    echo "Trying alternative insertion method..."
    
    # Alternative: Insert after SSL certificate lines (common pattern)
    awk -v iot_block="$IOT_LOCATION_BLOCK" '
    /ssl_certificate/ {
        print
        ssl_seen = 1
        next
    }
    ssl_seen && !inserted && /location/ {
        print iot_block
        inserted = 1
    }
    {print}
    ' "$CONFIG_FILE" > "$TEMP_CONFIG"
fi

# Final check
if ! grep -q "location.*\/booking\/api\/iot\/" "$TEMP_CONFIG"; then
    echo -e "${RED}ERROR: Automatic insertion failed${NC}"
    echo "Please manually add the following to $CONFIG_FILE:"
    echo "$IOT_LOCATION_BLOCK"
    rm "$TEMP_CONFIG"
    exit 1
fi

# Backup original and replace
cp "$CONFIG_FILE" "$BK/original_config"
mv "$TEMP_CONFIG" "$CONFIG_FILE"

echo -e "${GREEN}✓${NC} Configuration file updated"
echo ""

# Step 7: Test configuration
echo -e "${BLUE}Step 7: Testing Nginx configuration...${NC}"
nginx -t

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Nginx configuration test failed!${NC}"
    echo "Restoring from backup..."
    cp "$BK/original_config" "$CONFIG_FILE"
    echo "Original configuration restored. No changes applied."
    exit 1
fi

echo -e "${GREEN}✓${NC} Configuration test passed"
echo ""

# Step 8: Reload Nginx
echo -e "${BLUE}Step 8: Reloading Nginx...${NC}"
systemctl reload nginx

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Nginx reloaded successfully"
else
    echo -e "${RED}ERROR: Nginx reload failed${NC}"
    exit 1
fi

echo ""
echo "========================================"
echo -e "${GREEN}✓ Configuration Applied Successfully!${NC}"
echo "========================================"
echo ""
echo "Backup location: $BK"
echo "Modified file: $CONFIG_FILE"
echo ""
echo "Next step: Verify with curl:"
echo "  curl -i -H \"X-API-KEY: <your-key>\" \"https://timebaibai.com/booking/api/iot/config/\""
echo ""
echo "To rollback: sudo cp $BK/original_config $CONFIG_FILE && sudo systemctl reload nginx"
echo ""
