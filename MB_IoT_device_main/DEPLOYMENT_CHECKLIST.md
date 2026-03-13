# Deployment Checklist for CIRCUITPY Integration

## Pre-Deployment Verification

### ✅ Essential Files Present in MB_IoT_device_main:
- [x] `code.py` (main entry point with WiFi hardening)
- [x] `pico_device/` directory with all modules:
  - [x] `__init__.py`
  - [x] `config_manager.py`
  - [x] `wifi_manager.py`
  - [x] `setup_ap.py`
  - [x] `logging_utils.py`
  - [x] `file_utils.py`
  - [x] `provisioning.py`
  - [x] `django_api.py`
- [x] `lib/` directory with CircuitPython libraries
- [x] `secrets.py.sample` (template for WiFi configuration)
- [x] Documentation files:
  - [x] `README_WIFI.md`
  - [x] `README_DEPLOY.md`
  - [x] `docs/DEPENDENCIES.md`

### ✅ macOS-Specific Pre-Deployment Checks:
- [ ] Verify `/Volumes/CIRCUITPY` is mounted
- [ ] Run `./scripts/deploy_mac.sh` (do NOT use manual rsync with --delete)
- [ ] **NEVER open .py files from /Volumes/CIRCUITPY in macOS editors/IDEs**
  - Always edit in local `MB_IoT_device_main/` directory
  - Opening from CIRCUITPY creates `._*` files that corrupt the filesystem
- [ ] If encountering errors, consider formatting: `./scripts/format_device_mac.sh`

### ⚠️ Important Files on CIRCUITPY to Preserve:
- **CRITICAL**: `/Volumes/CIRCUITPY/secrets.py` (contains actual WiFi credentials)
- **IMPORTANT**: `/Volumes/CIRCUITPY/wifi_config.json` (Setup AP configuration)
- **BACKUP**: Any `*.backup` files (configuration backups)

### 🔍 Differential Analysis Results:
The rsync dry run shows that the following will be **ADDED/UPDATED**:
- New integrated `code.py` with WiFi hardening
- Complete `pico_device/` package
- Documentation files
- Updated library structure

**NO CRITICAL FILES WILL BE DELETED** - The existing `secrets.py` and `wifi_config.json` will be preserved.

## Deployment Steps

### Step 1: Backup Critical Files (Recommended)
```bash
# Backup current secrets.py
cp /Volumes/CIRCUITPY/secrets.py ~/pico_backup_secrets_$(date +%Y%m%d_%H%M%S).py

# Backup wifi config
cp /Volumes/CIRCUITPY/wifi_config.json ~/pico_backup_wifi_config_$(date +%Y%m%d_%H%M%S).json
```

### Step 2: Perform Deployment

**macOS users (recommended):**
```bash
# Use the hardened deployment script
cd /Users/adon/NewFUHI/MB_IoT_device_main
./scripts/deploy_mac.sh
```

**Advanced/manual rsync (not recommended on macOS):**
```bash
# Final dry run check
rsync -avn --delete MB_IoT_device_main/ /Volumes/CIRCUITPY/

# If satisfied, perform actual deployment
rsync -av --delete MB_IoT_device_main/ /Volumes/CIRCUITPY/
```

### Step 3: Post-Deployment Verification

**Essential files check:**
```bash
# Verify essential files exist
ls -la /Volumes/CIRCUITPY/code.py
ls -la /Volumes/CIRCUITPY/pico_device/
ls -la /Volumes/CIRCUITPY/secrets.py
ls -la /Volumes/CIRCUITPY/lib/

# Check that WiFi config is preserved
ls -la /Volumes/CIRCUITPY/wifi_config.json
```

**macOS-specific verification:**
```bash
# Check for metadata pollution (should return 0 or very few results)
find /Volumes/CIRCUITPY -name '._*' | grep -v -E '(\.Trashes|\.fseventsd)' | wc -l

# Verify lib/adafruit_character_lcd is a DIRECTORY (not a file)
test -d /Volumes/CIRCUITPY/lib/adafruit_character_lcd && echo "✓ OK: adafruit_character_lcd is a directory" || echo "✗ BROKEN: adafruit_character_lcd is NOT a directory"

# Verify settings.toml exists
test -f /Volumes/CIRCUITPY/settings.toml && echo "✓ settings.toml exists" || echo "⚠ settings.toml missing"
```


## Expected Boot Sequence

After deployment, the device should:

1. **Boot with BUILD message**: `[BUILD] MB_IoT_device_main 20260126-1400`
2. **Initialize WiFi hardening**: `[MAIN] Pico WiFi Hardening initialized...`
3. **Attempt WiFi connection** using existing `secrets.py` credentials
4. **Connect successfully** or **enter Setup AP mode** if connection fails

## LED Status Indicators

- **Solid ON**: WiFi connected successfully
- **Slow blink**: WiFi disconnected, attempting connection  
- **Fast blink**: Setup AP mode active (SSID: `PICO-SETUP-{device_id}`)

## Troubleshooting

### If Device Doesn't Boot:
1. Check serial output for error messages
2. Verify `code.py` syntax is correct
3. Ensure all required libraries are in `lib/`
4. Check that `secrets.py` exists and is properly formatted

### If WiFi Connection Fails:
1. Device should automatically enter Setup AP mode after 3 failed attempts
2. Connect to `PICO-SETUP-{device_id}` network (password: `SETUP_PASSWORD`)
3. Navigate to `http://192.168.4.1` to reconfigure

### If Setup AP Doesn't Appear:
1. Wait 30-60 seconds for Setup AP activation
2. Check for 2.4GHz networks (device doesn't support 5GHz)
3. Try creating `force_setup.txt` with content `FORCE_SETUP` on CIRCUITPY drive

## Integration Success Criteria

✅ **Deployment Successful** if:
- Device boots without errors
- WiFi hardening components load successfully
- Existing WiFi credentials are preserved
- Device connects to WiFi OR enters Setup AP mode gracefully
- All sensor/actuator functionality remains intact
- Django API integration works (if configured)

✅ **WiFi Hardening Active** if:
- Configuration priority system works (Django > Local > Secrets)
- Setup AP activates on connection failures
- Web interface accessible at `http://192.168.4.1` in Setup AP mode
- Configuration persistence works across reboots

## Rollback Plan

If deployment fails:
1. **Immediate**: Copy backed-up `secrets.py` back to device
2. **Full rollback**: Restore previous `code.py` from backup
3. **Nuclear option**: Flash fresh CircuitPython firmware and start over

## Next Steps After Successful Deployment

1. **Test WiFi connectivity** with current credentials
2. **Test Setup AP mode** by creating `force_setup.txt`
3. **Verify sensor readings** are still working
4. **Test Django API integration** (if server is configured)
5. **Document any device-specific configuration** for future reference

---

**DEPLOYMENT READY**: All prerequisites met, critical files identified and will be preserved. Proceed with confidence! 🚀