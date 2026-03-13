# Pico 2W Hardware Diagnostics Guide

## Overview

This guide explains how to run comprehensive hardware diagnostics on your Pico 2W IoT device. The diagnostics system validates all sensors, actuators, WiFi connectivity, and stores results both locally and (optionally) on the Django server.

## What Gets Tested

The diagnostic system tests the following components:

### 1. **Configuration Validation**
- Checks `secrets.py` for valid credentials
- Detects dummy/placeholder values (e.g., "YOUR_API_KEY_HERE")
- Status: PASS if valid, FAIL if placeholders detected

### 2. **WiFi Auto-Connect**
- Attempts connection with credentials from `secrets.py`
- Retries up to 3 times with 10-second timeout per attempt
- Records IP address, RSSI (signal strength), and DNS resolution
- Status: PASS if connected, FAIL if all retries exhausted

### 3. **LCD Display (I2C)**
- Tests I2C initialization at addresses 0x27 and 0x3F
- Displays diagnostic progress and results
- Status: PASS if initialized, FAIL if I2C error

### 4. **Button (GPIO5)**
- **User interaction required**: Press button within 10 seconds
- Status: PASS if pressed, WARN if timeout (check wiring)

### 5. **Buzzer (GPIO20, PWM)**
- Generates 3 beeps (1kHz, 0.2s each)
- **User confirmation**: Listen for audible beeps
- Status: PASS if no errors (user confirms sound)

### 6. **Speaker (GPIO18, PWM)**
- Plays two tones: 440Hz and 880Hz
- **User confirmation**: Listen for audible tones
- Status: PASS if no errors (user confirms sound)

### 7. **MQ-9 Gas Sensor (GPIO26, ADC)**
- Reads 10 samples and calculates average/std deviation
- Validates value not stuck at rails (0 or 65535)
- Status: PASS if electrically active, FAIL if stuck

### 8. **Light Sensor (GPIO27, ADC)**
- **User interaction**: Cover and uncover sensor during 10-second window
- Measures light level variation
- Status: PASS if >10% variation, WARN if stable (sensor may be blocked)

### 9. **PIR Motion Sensor (GPIO22)**
- **User interaction**: Move in front of sensor within 10 seconds
- Status: PASS if motion detected, WARN if timeout

### 10. **Temperature/Humidity Sensor (I2C)**
- Reads DHT or Si7021 sensor via I2C
- Validates values in reasonable range (-20°C to 60°C, 0-100% RH)
- Status: PASS if valid, FAIL if no response or out of range

### 11. **IR TX/RX Loopback**
- Transmits NEC IR pattern (0x20DF10EF) 3 times from TX (GPIO14)
- Listens for signals on RX (GPIO15) for 3 seconds
- **Hardware setup required**: Position TX and RX facing each other, 5-10cm apart
- Status: PASS if signal received, WARN if no signal (check positioning)

## Prerequisites

### Hardware Setup

1. **All sensors connected** per your wiring diagram
2. **IR modules positioned**: Grove IR TX and RX must face each other (~5-10cm apart) for loopback test
3. **Pico 2W connected** to Mac via USB (CIRCUITPY drive mounted)
4. **Serial monitor** ready (optional but recommended for detailed logs)

### Software Configuration

Ensure `/Volumes/CIRCUITPY/secrets.py` has valid values (not placeholders):

```python
secrets = {
    "ssid": "your-actual-wifi-ssid",
    "password": "your-actual-wifi-password",
    "api_key": "actual-api-key-from-django",  # NOT "YOUR_API_KEY_HERE"
    "device": "pico2w_001",
    "server_base": "https://timebaibai.com",  # NOT "your-server.com"
    "DIAGNOSTIC_MODE": True,  # Enable diagnostics
}
```

## Running Diagnostics

### Step 1: Enable Diagnostic Mode

Edit `/Volumes/CIRCUITPY/secrets.py`:

```python
"DIAGNOSTIC_MODE": True,
```

Save the file.

### Step 2: Connect Serial Monitor (Optional)

For detailed logs, connect a serial monitor:

```bash
# Using screen (Mac/Linux)
screen /dev/tty.usbmodem* 115200

# Or using Arduino Serial Monitor
# Tools → Serial Monitor → Select correct port → 115200 baud
```

### Step 3: Reset Pico 2W

1. Safely eject CIRCUITPY drive from Finder
2. Press the **RESET** button on Pico 2W
3. Immediately re-mount CIRCUITPY (or watch serial output)

### Step 4: Follow On-Screen Prompts

The LCD will display:
- `DIAGNOSTIC MODE` (startup)
- `WiFi Test` → `Connecting...`
- `Button Test` → `Press in 10s...`
- `PIR Test` → `Move in 10s...`
- `Light Test` → `Cover/uncover...`
- etc.

**Respond to interactive tests** within the timeout periods:
- **Button**: Press the button
- **PIR**: Move your hand in front of the sensor
- **Light**: Cover sensor with hand, then remove
- **Buzzer/Speaker**: Listen and confirm you hear sounds

### Step 5: Wait for Completion

Diagnostics takes approximately **2-3 minutes** to complete all tests.

Final LCD display will show:
```
Diagnostics Done
P:8 W:2 F:0
```
(P = PASS count, W = WARN count, F = FAIL count)

### Step 6: Review Results

#### Option A: Check Diagnostic Report File

```bash
cat /Volumes/CIRCUITPY/diag_report.json | python3 -m json.tool
```

Example output:

```json
{
  "device": "pico2w_001",
  "timestamp": "12345s_since_boot",
  "elapsed_seconds": 145.3,
  "wifi": {
    "status": "PASS",
    "ip": "192.168.1.100",
    "rssi": -55,
    "dns_ok": true,
    "attempts": 1
  },
  "tests": {
    "config_validation": {
      "status": "PASS",
      "note": "All required fields present"
    },
    "lcd_display": {
      "status": "PASS",
      "note": "Initialized at I2C address 0x27",
      "i2c_address": "0x27"
    },
    "button": {
      "status": "PASS",
      "note": "Button press detected"
    },
    "mq9": {
      "status": "PASS",
      "note": "Sensor electrically active",
      "avg_value": 12450,
      "std_dev": 123.4
    },
    "ir_loopback": {
      "status": "WARN",
      "note": "No signal detected - check TX/RX positioning"
    }
  }
}
```

#### Option B: Check Serial Console

Look for summary output:

```
[DIAG] ===========================================================
[DIAG]   DIAGNOSTICS COMPLETE
[DIAG] ===========================================================
[DIAG] Results: 8 PASS, 2 WARN, 0 FAIL
[DIAG] 
[DIAG] ✓ config_validation: PASS - All required fields present
[DIAG] ✓ lcd_display: PASS - Initialized at I2C address 0x27
[DIAG] ✓ wifi_autoconnect: PASS - Connected on attempt 1
...
[DIAG] ⚠ ir_loopback: WARN - No signal detected
```

#### Option C: Check Django Server (if online)

SSH to your server and check logs:

```bash
ssh -i newfuhi-key.pem ubuntu@your-server-ip
sudo journalctl -u gunicorn -n 100 --no-pager | grep -i "diagnostic"
```

Look for POST to `/booking/api/iot/events/` with `type: "diagnostic_report"`.

## Interpreting Results

### Status Meanings

| Status | Meaning | Action Required |
|--------|---------|-----------------|
| **PASS** | Component working correctly | None - all good! |
| **WARN** | Component may work but needs attention | Check wiring, verify user interaction was performed, or adjust positioning (for IR) |
| **FAIL** | Component not responding or config invalid | Check wiring, I2C addresses, pin assignments, or fix `secrets.py` |

### Common Issues and Fixes

#### WiFi FAIL: "Failed to connect after 3 attempts"
- **Cause**: Wrong SSID/password, or WiFi out of range
- **Fix**: Double-check `secrets.py` credentials, move Pico closer to router

#### Config Validation FAIL: "Invalid or dummy data"
- **Cause**: `secrets.py` contains placeholder values
- **Fix**: Replace `YOUR_API_KEY_HERE` with actual API key, `your-server.com` with `https://timebaibai.com`

#### LCD FAIL: "I2C initialization failed"
- **Cause**: Wrong I2C address, loose wiring, or SDA/SCL swapped
- **Fix**: Check I2C address (try `diag_scan.py` to detect), verify GPIO4/GP5 connections

#### Button/PIR WARN: "No press/motion detected in 10s"
- **Cause**: User didn't interact in time, sensor not connected, or wrong GPIO
- **Fix**: Re-run diagnostics and respond quickly, check wiring to GPIO5 (button) or GPIO22 (PIR)

#### IR Loopback WARN: "No signal detected"
- **Cause**: TX and RX not facing each other, too far apart, or wiring issue
- **Fix**: Position IR modules 5-10cm apart, directly facing each other, then re-run

#### MQ-9 FAIL: "Sensor reading stuck"
- **Cause**: Sensor not powered, broken, or wrong ADC pin
- **Fix**: Check 5V power to sensor, verify GPIO26 connection

#### Temp/Humidity FAIL: "Sensor not responding"
- **Cause**: I2C address mismatch, sensor type mismatch (DHT vs Si7021), or wiring
- **Fix**: Verify sensor type in code matches hardware, check I2C connections

## Returning to Normal Operation

After diagnostics complete:

1. Edit `/Volumes/CIRCUITPY/secrets.py`:
   ```python
   "DIAGNOSTIC_MODE": False,
   ```

2. Save and safely eject CIRCUITPY

3. Press **RESET** button on Pico 2W

4. Device will boot into normal IoT mode (sensor polling, Django sync, etc.)

## Advanced: Offline Diagnostics

If WiFi is unavailable or you only want to test hardware:

1. Set `DIAGNOSTIC_MODE = True` in `secrets.py`
2. WiFi test will FAIL or WARN (expected)
3. All other hardware tests will still run
4. Report saved to `/diag_report.json` (no server upload)
5. Review local file for results

This is useful for:
- Testing hardware before deploying to site
- Troubleshooting connectivity-independent issues
- Validating sensor wiring without network

## Troubleshooting the Diagnostics System Itself

If diagnostics fail to start or crash:

### Error: "diagnostics.py not found"
- **Cause**: File not deployed to CIRCUITPY
- **Fix**: Copy `diagnostics.py` from `MB_IoT_device_main/` to `/Volumes/CIRCUITPY/`

### Error: "ImportError: no module named 'sensors.dht_i2c'" (or similar)
- **Cause**: Missing sensor module files
- **Fix**: Ensure all files from `MB_IoT_device_main/sensors/` and `MB_IoT_device_main/actuators/` are on CIRCUITPY

### Diagnostics hang during a test
- **Cause**: Timeout logic failure (bug)
- **Fix**: Press Ctrl+C in serial console, or reset device. Report as bug.

### "MemoryError" during diagnostics
- **Cause**: CircuitPython heap exhaustion
- **Fix**: Reduce number of concurrent imports, or run `gc.collect()` more frequently (modify `diagnostics.py`)

## Example Successful Run

```
[DIAG] ===========================================================
[DIAG]   PICO 2W COMPREHENSIVE DIAGNOSTICS
[DIAG]   Device: pico2w_001
[DIAG] ===========================================================

[DIAG] Validating configuration...
[DIAG] ✓ Configuration valid

[DIAG] ===========================================================
[DIAG] Testing LCD Display
[DIAG] ===========================================================
[DIAG] Trying LCD at I2C address 0x27...
[DIAG] ✓ LCD initialized at 0x27

[DIAG] ===========================================================
[DIAG] Testing WiFi Auto-Connect
[DIAG] ===========================================================
[DIAG] Connection attempt 1/3
[DIAG] ✓ WiFi connected!
[DIAG]   SSID: aterm-16b7fa-g
[DIAG]   IP: 192.168.1.100
[DIAG]   RSSI: -52 dBm
[DIAG] ✓ DNS resolution OK: timebaibai.com -> 52.68.12.34

[DIAG] ===========================================================
[DIAG] Testing Button (GPIO5)
[DIAG] ===========================================================
[DIAG] Waiting for button press (10 seconds)...
[DIAG] ✓ Button press detected!

... (all other tests) ...

[DIAG] ===========================================================
[DIAG]   DIAGNOSTICS COMPLETE
[DIAG] ===========================================================
[DIAG] Results: 10 PASS, 1 WARN, 0 FAIL
[DIAG] 
[DIAG] ✓ config_validation: PASS - All required fields present
[DIAG] ✓ lcd_display: PASS - Initialized at I2C address 0x27
[DIAG] ✓ wifi_autoconnect: PASS - Connected on attempt 1
[DIAG] ✓ button: PASS - Button press detected
[DIAG] ✓ buzzer: PASS - 3 beeps generated
[DIAG] ✓ speaker: PASS - Tones generated
[DIAG] ✓ mq9: PASS - Sensor electrically active
[DIAG] ✓ light: PASS - Sensor responding to light changes
[DIAG] ✓ pir: PASS - Motion detected
[DIAG] ✓ temp_humidity: PASS - Sensor reading in valid range
[DIAG] ⚠ ir_loopback: WARN - No signal detected
[DIAG] 
[DIAG] ✓ Report saved to /diag_report.json
[DIAG] ✓ Diagnostic report uploaded to server
[DIAG] ===========================================================
[DIAG] Diagnostic report saved to /diag_report.json
[DIAG] Set DIAGNOSTIC_MODE=False in secrets.py to return to normal mode
[DIAG] ===========================================================
```

## Summary

The diagnostics system provides a comprehensive, automated way to validate all Pico 2W hardware before deployment or when troubleshooting issues. Results are stored locally and (if online) sent to Django, providing both immediate and historical diagnostic data.

**Remember**: Always review the diagnostic report and address any WARN or FAIL statuses before putting the device into production use!
