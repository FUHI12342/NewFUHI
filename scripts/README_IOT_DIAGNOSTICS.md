# IoT Diagnostics System - Quick Start Guide

## Overview

This system provides comprehensive hardware diagnostics for Pico 2W IoT devices and secure API access configuration for Django backend integration.

## Components

### 1. Backup & Rollback Scripts (`/scripts`)

| Script | Purpose |
|--------|---------|
| `backup_circuitpy.sh` | Backup CIRCUITPY drive to `~/NewFUHI/_backups/` |
| `rollback_circuitpy.sh` | Restore CIRCUITPY from backup (interactive) |
| `backup_server.sh` | Backup Nginx configuration to `/var/backups/` |
| `rollback_server.sh` | Restore Nginx configuration (interactive) |

### 2. Pico 2W Diagnostics (`/MB_IoT_device_main`)

| File | Purpose |
|------|---------|
| `diagnostics.py` | Comprehensive hardware diagnostic system (WiFi + 11 hardware tests) |
| `code.py` | Main firmware (modified to support `DIAGNOSTIC_MODE`) |
| `DIAGNOSTICS_GUIDE.md` | User operational guide |

### 3. Server Configuration (`/scripts`)

| File | Purpose |
|------|---------|
| `NGINX_CONFIG_GUIDE.md` | Step-by-step Nginx configuration for IoT API Basic auth bypass |

## Quick Start

### Run CIRCUITPY Backup

```bash
cd /Users/adon/NewFUHI
./scripts/backup_circuitpy.sh
```

### Run Pico 2W Diagnostics

1. Ensure hardware properly connected (see `MB_IoT_device_main/DIAGNOSTICS_GUIDE.md`)
2. Edit `/Volumes/CIRCUITPY/secrets.py`:
   ```python
   "DIAGNOSTIC_MODE": True,
   ```
3. Reset Pico 2W
4. Follow LCD prompts and respond to interactive tests
5. Review results in `/Volumes/CIRCUITPY/diag_report.json`
6. Set `DIAGNOSTIC_MODE = False` and reset to return to normal mode

### Configure Nginx (Server)

1. SSH to server
2. Run backup:
   ```bash
   sudo ./scripts/backup_server.sh
   ```
3. Follow `scripts/NGINX_CONFIG_GUIDE.md` to add IoT API location block
4. Verify with curl:
   ```bash
   curl -i -H "X-API-KEY: <key>" "https://timebaibai.com/booking/api/iot/config/"
   ```

## Documentation

- **[walkthrough.md](file:///.gemini/antigravity/brain/ccd5ece6-6e4e-47db-a5dc-9396f123f836/walkthrough.md)** - Complete implementation walkthrough
- **[MB_IoT_device_main/DIAGNOSTICS_GUIDE.md](file:///Users/adon/NewFUHI/MB_IoT_device_main/DIAGNOSTICS_GUIDE.md)** - Pico 2W diagnostics operational guide
- **[scripts/NGINX_CONFIG_GUIDE.md](file:///Users/adon/NewFUHI/scripts/NGINX_CONFIG_GUIDE.md)** - Nginx configuration guide

## Diagnostic Tests

The system validates:
1. ✅ Configuration validation (detects dummy values)
2. ✅ WiFi auto-connect (3 retry attempts, RSSI logging)
3. ✅ LCD Display (I2C)
4. ✅ Button (GPIO5, user-interactive)
5. ✅ Buzzer (GPIO20, PWM)
6. ✅ Speaker (GPIO18, PWM)
7. ✅ MQ-9 Gas Sensor (GPIO26, ADC)
8. ✅ Light Sensor (GPIO27, ADC, user-interactive)
9. ✅ PIR Motion Sensor (GPIO22, user-interactive)
10. ✅ Temperature/Humidity (I2C)
11. ✅ IR TX/RX Loopback (requires TX/RX positioned facing each other)

Results: **PASS** / **WARN** / **FAIL** with detailed metadata in JSON report.

## Rollback

### CIRCUITPY
```bash
./scripts/rollback_circuitpy.sh
# Select backup from menu
```

### Server
```bash
sudo ./scripts/rollback_server.sh
# Select backup from menu
```

## Security Notes

- After Nginx configuration, `/booking/api/iot/*` endpoints bypass Basic auth
- Security relies on Django validating `X-API-KEY` header
- Ensure Django API has proper authentication and rate limiting

## Next Steps

1. ✅ **Implementation Complete** - All code and documentation ready
2. ⏳ **Server Configuration** - Apply Nginx changes (requires SSH)
3. ⏳ **Testing** - Run diagnostics on Pico 2W hardware
4. ⏳ **Production Deployment** - Set `DIAGNOSTIC_MODE = False` after validation

For detailed instructions, see [walkthrough.md](file:///.gemini/antigravity/brain/ccd5ece6-6e4e-47db-a5dc-9396f123f836/walkthrough.md).
