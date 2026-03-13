# Deployment Guide for Pico 2 W IoT Device

This guide explains how to deploy code to your Pico 2 W device safely and reliably on macOS.

---

## C-Plan Deployment (Recommended) ⭐

**This is the recommended deployment method for macOS → CIRCUITPY (FAT12) to avoid filesystem corruption.**

### Overview

The C-plan provides a complete, FAT12-safe deployment workflow with:
- ✅ Auto-detection of CIRCUITPY device
- ✅ FAT12-safe rsync options (no problematic operations)
- ✅ macOS metadata cleanup (._*, .DS_Store)
- ✅ Automated health checks
- ✅ Secrets protection (no accidental overwrites)

### Quick Start (Normal Deployment)

If your device is already formatted and working:

```bash
cd ~/NewFUHI/MB_IoT_device_main

# Deploy code
./scripts/deploy_to_circuitpy.sh

# The script will automatically:
# 1. Sync files to device (FAT12-safe)
# 2. Clean macOS metadata
# 3. Run health checks
# 4. Report success/failure
```

### Full Workflow (Format + Deploy)

If starting fresh or recovering from corruption:

```bash
cd ~/NewFUHI/MB_IoT_device_main

# Step 1: Format device (auto-detects CIRCUITPY)
./scripts/format_circuitpy.sh

# Or specify device manually:
# ./scripts/format_circuitpy.sh /dev/disk4s1

# Step 2: Deploy code
./scripts/deploy_to_circuitpy.sh

# Step 3: Verify (optional, already run by deploy script)
./scripts/healthcheck_circuitpy.sh
```

### Script Details

#### 1. `scripts/format_circuitpy.sh`

Formats CIRCUITPY device with FAT12 filesystem.

**Features:**
- Auto-detects CIRCUITPY from `diskutil list`
- Creates `settings.toml` with `CIRCUITPY_AUTORELOAD = 0`
- Requires confirmation (type "yes")
- Use `--yes` to skip confirmation (automation)

**Usage:**
```bash
# Auto-detect device
./scripts/format_circuitpy.sh

# Specify device manually
./scripts/format_circuitpy.sh /dev/disk4s1

# Skip confirmation
./scripts/format_circuitpy.sh --yes
```

**⚠️ WARNING:** This erases ALL data on the device!

---

#### 2. `scripts/deploy_to_circuitpy.sh`

Deploys code to CIRCUITPY using FAT12-safe options.

**Features:**
- Uses `rsync --inplace` (no rename operations)
- Excludes system files (`.Trashes`, `.fseventsd`)
- Excludes metadata (`._*`, `.DS_Store`)
- Protects `secrets.py` by default
- Runs metadata cleanup automatically
- Runs health check automatically
- NO `--delete` by default (safety first)

**Usage:**
```bash
# Normal deployment
./scripts/deploy_to_circuitpy.sh

# Dry run (see what would be deployed)
./scripts/deploy_to_circuitpy.sh --dry-run

# Force overwrite secrets.py
./scripts/deploy_to_circuitpy.sh --force-secrets

# Enable --delete (DANGEROUS!)
./scripts/deploy_to_circuitpy.sh --danger-delete
```

**Options:**
- `--dry-run` - Show what would be deployed without making changes
- `--force-secrets` - Overwrite existing `secrets.py` on device
- `--danger-delete` - Enable rsync `--delete` (⚠️ DANGEROUS on FAT12!)

---

#### 3. `scripts/clean_macos_metadata.sh`

Removes macOS metadata files without touching system directories.

**What it does:**
- Runs `dot_clean -m` to merge AppleDouble files
- Removes `._*` files (except in `.Trashes/` and `.fseventsd/`)
- Removes `.DS_Store` files (except in system directories)
- Reports count of removed files

**Usage:**
```bash
./scripts/clean_macos_metadata.sh
```

---

#### 4. `scripts/healthcheck_circuitpy.sh`

Verifies deployment integrity.

**Checks:**
- ✅ CIRCUITPY is mounted
- ✅ `code.py` exists
- ✅ `lib/adafruit_character_lcd` is a directory (not a file!)
- ✅ `lib/adafruit_requests.mpy` exists
- ✅ `lib/adafruit_connection_manager.mpy` exists
- ⚠️ `secrets.py` exists (warning only)
- ⚠️ No metadata pollution (warning only)

**Usage:**
```bash
./scripts/healthcheck_circuitpy.sh

# Exit code 0 = all checks passed
# Exit code 1 = one or more checks failed
```

---

### Secrets Management

**Default behavior: secrets.py is PROTECTED**

The deployment script will NOT overwrite `secrets.py` if it already exists on the device. This prevents accidentally losing your WiFi credentials.

```bash
# Initial setup - copy secrets
cp secrets.py.sample secrets.py
# Edit secrets.py with your WiFi credentials
# Deploy (will copy secrets.py to device)
./scripts/deploy_to_circuitpy.sh

# Subsequent deployments - secrets.py preserved
./scripts/deploy_to_circuitpy.sh  # Will NOT overwrite device secrets.py

# Force update secrets
./scripts/deploy_to_circuitpy.sh --force-secrets
```

---

### Dangerous Operations

#### Using --danger-delete

By default, the deployment script does NOT use `rsync --delete` because:
1. FAT12 filesystem has poor support for delete operations
2. Can cause "Bad address" or "Invalid argument" errors  
3. May corrupt filesystem structure

**If you really need --delete:**

```bash
./scripts/deploy_to_circuitpy.sh --danger-delete
# You will be prompted to type 'DELETE' to confirm
```

**⚠️ WARNING:** Only use this if you understand the risks!

**Safer alternative:** Format and redeploy instead of using --delete:
```bash
./scripts/format_circuitpy.sh
./scripts/deploy_to_circuitpy.sh
```

---

### Troubleshooting

#### Issue: "Bad address" or "Invalid argument" during rsync

**Cause:** FAT12 filesystem corruption or incompatible rsync operations.

**Solution:**
```bash
# Format and redeploy
./scripts/format_circuitpy.sh
./scripts/deploy_to_circuitpy.sh
```

---

#### Issue: `lib/adafruit_character_lcd` is a file instead of directory

**Cause:** macOS metadata corruption (._* files).

**Solution:**
```bash
# Format device to clear corruption
./scripts/format_circuitpy.sh

# Deploy clean
./scripts/deploy_to_circuitpy.sh

# Verify fix
./scripts/healthcheck_circuitpy.sh
```

**Prevention:** Never open `.py` files directly from `/Volumes/CIRCUITPY` in macOS editors. Always edit in your local `MB_IoT_device_main/` directory.

---

#### Issue: Permission denied on .Trashes

**Cause:** macOS system directory permissions.

**Solution:** This is normal and can be ignored. The scripts exclude `.Trashes/` and `.fseventsd/` directories.

---

#### Issue: Device reboots during deployment

**Cause:** CircuitPython AutoReload is enabled.

**Solution:** The scripts automatically create `settings.toml` with `CIRCUITPY_AUTORELOAD = 0`. If you manually formatted, ensure this file exists:

```bash
# Check if settings.toml exists
cat /Volumes/CIRCUITPY/settings.toml

# Should contain:
# CIRCUITPY_AUTORELOAD = 0
```

---

### Best Practices

1. **Always use the C-plan scripts** - Don't use manual rsync  
2. **Never edit files on CIRCUITPY directly** - Edit locally, then deploy
3. **Don't open .py files from /Volumes/CIRCUITPY** - Creates metadata files
4. **Use --dry-run first** - Preview changes before deploying
5. **Keep secrets.py local** - Back it up outside the repo
6. **Format when in doubt** - Clean slate prevents corruption
7. **Run health check** - Verify after deployment

---

## Prerequisites

- Pico 2 W device connected via USB
- Device appears as `CIRCUITPY` drive at `/Volumes/CIRCUITPY` (macOS)
- rsync installed on your system

## macOS Deployment (Recommended)

**For macOS users, we provide a hardened deployment script that handles FAT12 filesystem compatibility and prevents metadata pollution.**

### Quick Start

```bash
cd /Users/adon/NewFUHI/MB_IoT_device_main
./scripts/deploy_mac.sh
```

### What the Script Does

The `deploy_mac.sh` script provides:

1. **Automatic mount detection** - Finds CIRCUITPY drive and validates it
2. **AutoReload prevention** - Creates `settings.toml` to prevent mid-transfer reboots
3. **FAT12-safe rsync** - Uses `--inplace`, `--omit-dir-times`, and other compatible options
4. **Metadata cleanup** - Removes `._*` (AppleDouble) and `.DS_Store` files
5. **Health checks** - Verifies critical directories like `lib/adafruit_character_lcd` are intact
6. **Error guidance** - Provides troubleshooting tips on failure

### Critical macOS Warning

> ⚠️ **NEVER IMPORT .py FILES FROM /Volumes/CIRCUITPY IN macOS EDITORS**
> 
> Opening Python files directly from the CIRCUITPY volume in macOS applications (editors, IDEs, Python interpreters) will create `._*` (AppleDouble) metadata files. These files can corrupt the FAT12 filesystem and cause directories like `lib/adafruit_character_lcd` to become files instead of directories.
>
> **Always edit files in your local project directory** (`MB_IoT_device_main/`), then deploy using the script.

### When to Format and Redeploy

If you encounter persistent issues like:
- `lib/adafruit_character_lcd` is a file instead of a directory
- "Bad address" or "Invalid argument" errors during deployment
- Device won't boot after deployment
- Excessive `._*` files on the device

**Use the format script:**

```bash
./scripts/format_device_mac.sh /dev/diskX
```

Replace `/dev/diskX` with your actual device node. The script will:
1. Show all connected disks (`diskutil list`)
2. Display CIRCUITPY device information
3. Require explicit "YES" confirmation
4. Format the device as MS-DOS (FAT)
5. Guide you to deploy fresh code

**Complete format and redeploy procedure:**

```bash
# Step 1: Find your device node
diskutil list
# Look for CIRCUITPY, note the identifier (e.g., disk4)

# Step 2: Format (ERASES ALL DATA!)
./scripts/format_device_mac.sh /dev/disk4

# Step 3: Wait for remount
ls -la /Volumes/CIRCUITPY

# Step 4: Deploy code
./scripts/deploy_mac.sh

# Step 5: Eject and test
diskutil unmount /Volumes/CIRCUITPY
```

## Deployment Process

### Step 1: Verify CIRCUITPY Mount

```bash
ls -la /Volumes/CIRCUITPY
```

Expected output should show the device files. If not mounted, reconnect the USB cable.

### Step 2: Dry Run (Recommended)

Always perform a dry run first to see what changes will be made:

```bash
rsync -avn --delete MB_IoT_device_main/ /Volumes/CIRCUITPY/
```

**Flags explanation:**
- `-a`: Archive mode (preserves permissions, timestamps, etc.)
- `-v`: Verbose output
- `-n`: Dry run (don't actually copy)
- `--delete`: Remove files on destination that don't exist in source

### Step 3: Review Changes

The dry run output will show:
- Files to be copied (new or modified)
- Files to be deleted (marked with `deleting`)
- Directories to be created

**⚠️ CRITICAL CHECK:** Look for any files being deleted that contain important data:
- `secrets.py` (your WiFi credentials)
- `wifi_config.json` (Setup AP configuration)
- `*.backup` files (configuration backups)
- Custom sensor calibration files

### Step 4: Backup Important Files (if needed)

If the dry run shows important files will be deleted, back them up first:

```bash
# Backup secrets.py
cp /Volumes/CIRCUITPY/secrets.py ~/pico_backup_secrets.py

# Backup wifi config
cp /Volumes/CIRCUITPY/wifi_config.json ~/pico_backup_wifi_config.json
```

### Step 5: Perform Actual Deployment

If the dry run looks good, perform the actual sync:

```bash
rsync -av --delete MB_IoT_device_main/ /Volumes/CIRCUITPY/
```

### Step 6: Verify Deployment

Check that essential files are present:

```bash
ls -la /Volumes/CIRCUITPY/code.py
ls -la /Volumes/CIRCUITPY/pico_device/
ls -la /Volumes/CIRCUITPY/secrets.py
```

### Step 7: Test Device Boot

1. Safely eject the CIRCUITPY drive
2. Watch the device LED for status indication:
   - **Solid ON**: WiFi connected successfully
   - **Slow blink**: WiFi disconnected, attempting connection
   - **Fast blink**: Setup AP mode active

## Deployment Checklist

Before each deployment, verify:

- [ ] Dry run completed and reviewed
- [ ] Important configuration files backed up (if being deleted)
- [ ] `code.py` is present in source
- [ ] `pico_device/` directory is complete
- [ ] `lib/` directory contains required CircuitPython libraries
- [ ] `secrets.py` exists (copy from `secrets.py.sample` if needed)
- [ ] No syntax errors in Python files

## Required Files Structure

After deployment, CIRCUITPY should contain:

```
/Volumes/CIRCUITPY/
├── code.py                 # Main entry point
├── secrets.py              # WiFi credentials (user-created)
├── secrets.py.sample       # Template file
├── pico_device/            # WiFi hardening package
│   ├── __init__.py
│   ├── config_manager.py
│   ├── wifi_manager.py
│   ├── setup_ap.py
│   ├── logging_utils.py
│   ├── file_utils.py
│   ├── provisioning.py
│   └── django_api.py
├── lib/                    # CircuitPython libraries
│   ├── adafruit_requests.mpy
│   ├── adafruit_connection_manager.mpy
│   └── ...
├── sensors/                # Sensor modules
├── actuators/              # Actuator modules
└── ...                     # Other project files
```

## Troubleshooting Deployment

### CIRCUITPY Not Mounted
```bash
# Check if device is connected
ls /Volumes/
# If not visible, try:
# 1. Reconnect USB cable
# 2. Press RESET button on Pico
# 3. Check USB cable quality
```

### Permission Denied Errors
```bash
# Check mount permissions
ls -la /Volumes/CIRCUITPY/
# If read-only, try:
# 1. Safely eject and reconnect
# 2. Check USB cable connection
# 3. Try different USB port
```

### Rsync Command Not Found
```bash
# Install rsync (macOS with Homebrew)
brew install rsync

# Or use built-in rsync (usually available)
which rsync
```

### Files Not Updating
```bash
# Force update with checksum comparison
rsync -avc --delete MB_IoT_device_main/ /Volumes/CIRCUITPY/

# Or delete and recopy specific files
rm /Volumes/CIRCUITPY/code.py
cp MB_IoT_device_main/code.py /Volumes/CIRCUITPY/
```

### Device Not Booting After Deployment
1. Check for syntax errors in `code.py`
2. Verify all required imports are available
3. Check that `secrets.py` exists and is properly formatted
4. Look at boot_out.txt for error messages

## Selective Deployment

To deploy only specific components:

### Deploy only code.py
```bash
cp MB_IoT_device_main/code.py /Volumes/CIRCUITPY/
```

### Deploy only pico_device package
```bash
rsync -av --delete MB_IoT_device_main/pico_device/ /Volumes/CIRCUITPY/pico_device/
```

### Deploy only libraries
```bash
rsync -av --delete MB_IoT_device_main/lib/ /Volumes/CIRCUITPY/lib/
```

## Automated Deployment Script

Create a deployment script for convenience:

```bash
#!/bin/bash
# deploy.sh

set -e  # Exit on error

DEVICE_PATH="/Volumes/CIRCUITPY"
SOURCE_PATH="MB_IoT_device_main"

echo "=== Pico 2 W Deployment Script ==="

# Check if device is mounted
if [ ! -d "$DEVICE_PATH" ]; then
    echo "ERROR: CIRCUITPY not found at $DEVICE_PATH"
    echo "Please connect your Pico 2 W device"
    exit 1
fi

# Perform dry run
echo "Performing dry run..."
rsync -avn --delete "$SOURCE_PATH/" "$DEVICE_PATH/"

read -p "Proceed with deployment? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Deploying..."
    rsync -av --delete "$SOURCE_PATH/" "$DEVICE_PATH/"
    echo "Deployment complete!"
    echo "Device will restart automatically."
else
    echo "Deployment cancelled."
fi
```

Make it executable:
```bash
chmod +x deploy.sh
./deploy.sh
```

## Best Practices

1. **Always dry run first** - Prevents accidental data loss
2. **Backup configurations** - Save important settings before deployment
3. **Test incrementally** - Deploy small changes and test frequently
4. **Version control** - Keep track of working configurations
5. **Monitor device logs** - Watch serial output during deployment
6. **Keep libraries updated** - Regularly update CircuitPython libraries
7. **Document changes** - Note what was changed in each deployment

## Emergency Recovery

If deployment breaks the device:

1. **Safe Mode**: Hold RESET while plugging in USB to enter safe mode
2. **Restore backup**: Copy backed-up files back to device
3. **Fresh install**: Delete all files and redeploy from scratch
4. **Factory reset**: Flash new CircuitPython firmware if needed

## Serial Monitoring

Monitor device output during deployment:

```bash
# macOS - find the device
ls /dev/tty.usbmodem*

# Connect with screen
screen /dev/tty.usbmodem* 115200

# Exit screen: Ctrl+A, then K, then Y
```

This helps debug boot issues and verify successful deployment.