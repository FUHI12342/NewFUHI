# WiFi Configuration Guide for Pico 2 W IoT Device

This guide explains how to configure WiFi credentials for your Pico 2 W IoT device using USB direct-write method.

## Quick Setup (USB Direct-Write Method)

### Step 1: Connect Pico to Computer
1. Connect your Pico 2 W to your computer via USB
2. The device should appear as a drive named `CIRCUITPY`

### Step 2: Configure WiFi Credentials
1. Navigate to the `CIRCUITPY` drive
2. Copy `secrets.py.sample` to `secrets.py`
3. Edit `secrets.py` with your actual WiFi credentials:

```python
secrets = {
    # WiFi credentials (REQUIRED)
    "ssid": "Your_WiFi_Network_Name",
    "password": "Your_WiFi_Password",
    
    # Django backend API settings (REQUIRED for server features)
    "api_key": "your_actual_api_key_here",
    "device": "pico2w_001",  # Unique device identifier
    "server_base": "https://your-server.com",
    
    # Optional settings
    "DIAGNOSTIC_MODE": False,  # Set to True for hardware diagnostics
}
```

### Step 3: Save and Restart
1. Save the `secrets.py` file
2. Safely eject the `CIRCUITPY` drive
3. The device will automatically restart and connect to your WiFi

## Configuration Priority

The device uses multiple configuration sources in this priority order:

1. **Django Server** (highest priority) - Dynamic configuration from server
2. **Local File** (`wifi_config.json`) - Configuration saved via Setup AP
3. **Secrets File** (`secrets.py`) - Manual USB configuration (lowest priority)

## Setup AP Fallback Mode

If WiFi connection fails after 3 attempts, the device automatically enters Setup AP mode:

### Setup AP Details:
- **SSID**: `PICO-SETUP-{device_id}`
- **Password**: `SETUP_PASSWORD`
- **Web Interface**: `http://192.168.4.1`

### Using Setup AP:
1. Connect to the setup WiFi network
2. Open a web browser and go to `http://192.168.4.1`
3. Fill in the configuration form
4. Click "Save Configuration & Restart"

## Manual Setup AP Trigger

You can force the device into Setup AP mode by:

1. Creating a file named `force_setup.txt` on the CIRCUITPY drive
2. Adding the text `FORCE_SETUP` to the file
3. Restarting the device

## Troubleshooting

### Device Not Connecting to WiFi
1. Check that your WiFi credentials are correct in `secrets.py`
2. Ensure your WiFi network is 2.4GHz (Pico 2 W doesn't support 5GHz)
3. Check that the WiFi network is within range
4. Look for the Setup AP if connection fails repeatedly

### Setup AP Not Appearing
1. Wait 30-60 seconds after power-on for Setup AP to activate
2. Check that you're scanning for 2.4GHz networks
3. Try restarting the device

### Configuration Not Saving
1. Ensure the `CIRCUITPY` drive is properly mounted
2. Check that `secrets.py` has the correct syntax
3. Verify file permissions allow writing

### Server Connection Issues
1. Verify the `server_base` URL is correct and accessible
2. Check that the `api_key` is valid
3. Ensure your server supports the expected API endpoints

## Security Notes

- **Never commit `secrets.py` to version control**
- The `secrets.py.sample` file is safe to commit (contains no real credentials)
- Use strong, unique WiFi passwords
- Regularly rotate API keys
- Consider using HTTPS for server communication

## File Locations

- Configuration template: `secrets.py.sample`
- Active configuration: `secrets.py` (create from template)
- Setup AP config: `wifi_config.json` (auto-generated)
- Backup configs: `*.backup` files (auto-generated)

## Advanced Configuration

### Multiple WiFi Networks
The device currently supports one WiFi network at a time. To switch networks:
1. Update `secrets.py` with new credentials, OR
2. Use the Setup AP web interface

### Server Integration
For full server integration, ensure your Django server has:
- IoT device API endpoints (`/booking/api/iot/config/`, `/booking/api/iot/events/`)
- Valid API key authentication
- CORS configuration for device requests

### Diagnostic Mode
Enable diagnostic mode to scan for connected sensors:
```python
"DIAGNOSTIC_MODE": True
```

This will run hardware diagnostics instead of normal operation.

## Support

If you encounter issues:
1. Check the device logs via serial connection
2. Verify all configuration files are properly formatted
3. Test WiFi connectivity with a simple device first
4. Consult the main project documentation

For technical support, include:
- Device ID
- WiFi network type (WPA2, WPA3, etc.)
- Error messages from serial output
- Configuration file contents (with credentials redacted)