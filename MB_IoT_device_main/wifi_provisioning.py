# wifi_provisioning.py
# Wi-Fi provisioning via AP mode and web interface
# Uses adafruit_httpserver for web server

import time
import os
import wifi
import socketpool
from adafruit_httpserver import Server, Request, Response, POST

# AP settings
AP_SSID_PREFIX = "FUHI-SETUP-"
AP_PASSWORD_PREFIX = "fuhisetup"

# Settings file
SETTINGS_FILE = "settings.toml"

def get_mac_suffix():
    """Get last 4 hex digits of MAC address"""
    mac = wifi.radio.mac_address
    return "".join(f"{b:02x}" for b in mac[-2:])

def get_ap_ssid():
    """Generate AP SSID"""
    return f"{AP_SSID_PREFIX}{get_mac_suffix()}"

def get_ap_password():
    """Generate AP password"""
    return f"{AP_PASSWORD_PREFIX}{get_mac_suffix()}"

def load_settings():
    """Load settings from settings.toml"""
    settings = {}
    try:
        if SETTINGS_FILE in os.listdir():
            with open(SETTINGS_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        settings[key] = value
    except Exception as e:
        print("Settings load error:", e)
    return settings

def save_settings(settings):
    """Save settings to settings.toml"""
    try:
        # Read existing content
        existing = {}
        if SETTINGS_FILE in os.listdir():
            with open(SETTINGS_FILE, "r") as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        key, _ = line.split("=", 1)
                        key = key.strip()
                        existing[key] = line.strip()
                    else:
                        # Keep comments and empty lines
                        pass

        # Update with new settings
        for key, value in settings.items():
            if isinstance(value, str):
                existing[key] = f'{key} = "{value}"'
            else:
                existing[key] = f"{key} = {value}"

        # Write back
        with open(SETTINGS_FILE, "w") as f:
            for line in existing.values():
                f.write(line + "\n")

        print("Settings saved successfully")
        return True
    except Exception as e:
        print("Settings save error:", e)
        return False

def needs_provisioning():
    """Check if Wi-Fi provisioning is needed"""
    settings = load_settings()
    ssid = settings.get("CIRCUITPY_WIFI_SSID", "").strip()
    password = settings.get("CIRCUITPY_WIFI_PASSWORD", "").strip()

    if not ssid or not password:
        print("Wi-Fi settings missing, provisioning needed")
        return True

    # Try to connect and check
    try:
        wifi.radio.connect(ssid, password)
        if wifi.radio.ipv4_address:
            print("Wi-Fi already configured and connected")
            return False
    except Exception as e:
        print("Wi-Fi connection failed:", e)

    print("Wi-Fi provisioning needed")
    return True

def try_connect(ssid, password, timeout_s=20):
    """Try to connect to Wi-Fi network"""
    try:
        print(f"Trying to connect to {ssid}...")
        wifi.radio.connect(ssid, password)

        start = time.monotonic()
        while time.monotonic() - start < timeout_s:
            if wifi.radio.ipv4_address:
                print(f"Connected to {ssid}, IP: {wifi.radio.ipv4_address}")
                return True
            time.sleep(0.5)

        print("Connection timeout")
        return False
    except Exception as e:
        print("Connection error:", e)
        return False

def run_ap_portal(lcd_notify=None):
    """
    Run AP mode and web portal for Wi-Fi setup
    lcd_notify: callback function for LCD updates (event: str, payload: dict)
    """
    ap_ssid = get_ap_ssid()
    ap_password = get_ap_password()

    print(f"Starting AP mode: {ap_ssid}")
    print(f"AP Password: {ap_password}")

    # Start AP
    wifi.radio.start_ap(ap_ssid, ap_password)
    print("AP started, IP: 192.168.4.1")

    # Notify LCD: AP started
    if lcd_notify:
        try:
            lcd_notify("AP_START", {
                "ssid": ap_ssid,
                "password_hint": f"****{ap_password[-4:]}",
                "ip": "192.168.4.1"
            })
        except Exception as e:
            print("LCD notify error:", e)

    # Create HTTP server
    pool = socketpool.SocketPool(wifi.radio)
    server = Server(pool, "/")

    credentials = {"ssid": None, "password": None}

    @server.route("/")
    def root(request: Request):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>FUHI Wi-Fi Setup</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
        </head>
        <body>
            <h1>FUHI IoT Device Setup</h1>
            <p>Enter your 2.4GHz Wi-Fi network details:</p>
            <form method="POST" action="/configure">
                <label>Wi-Fi SSID:</label><br>
                <input type="text" name="ssid" required><br><br>
                <label>Password:</label><br>
                <input type="password" name="password" required><br><br>
                <input type="submit" value="Connect">
            </form>
            <p><small>Note: Only 2.4GHz networks are supported.</small></p>
        </body>
        </html>
        """
        return Response(request, html, content_type="text/html")

    @server.route("/configure", POST)
    def configure(request: Request):
        ssid = request.form_data.get("ssid", "").strip()
        password = request.form_data.get("password", "").strip()

        if not ssid or not password:
            return Response(request, "SSID and password required", status=400)

        print(f"Received config: SSID={ssid}, Password=***")

        # Save to settings
        if save_settings({
            "CIRCUITPY_WIFI_SSID": ssid,
            "CIRCUITPY_WIFI_PASSWORD": password
        }):
            credentials["ssid"] = ssid
            credentials["password"] = password

            # Notify LCD: settings saved
            if lcd_notify:
                try:
                    lcd_notify("SAVE_OK", {"ssid": ssid})
                except Exception as e:
                    print("LCD notify error:", e)

            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Setup Complete</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
            </head>
            <body>
                <h1>Setup Complete!</h1>
                <p>Configuration saved. Device will restart and connect to your network.</p>
                <p>You can close this page now.</p>
            </body>
            </html>
            """
            return Response(request, html, content_type="text/html")
        else:
            # Notify LCD: save error
            if lcd_notify:
                try:
                    lcd_notify("SAVE_ERR", {})
                except Exception as e:
                    print("LCD notify error:", e)
            return Response(request, "Failed to save settings", status=500)

    # Start server
    server.start("0.0.0.0", 80)
    print("Web server started on http://192.168.4.1")

    # Wait for configuration
    start_time = time.monotonic()
    timeout = 300  # 5 minutes

    while time.monotonic() - start_time < timeout:
        try:
            server.poll()
            if credentials["ssid"] and credentials["password"]:
                print("Configuration received, stopping AP")
                server.stop()
                wifi.radio.stop_ap()
                return credentials
        except Exception as e:
            print("Server error:", e)
        time.sleep(0.1)

    print("Provisioning timeout")
    # Notify LCD: timeout
    if lcd_notify:
        try:
            lcd_notify("AP_TIMEOUT", {})
        except Exception as e:
            print("LCD notify error:", e)
    server.stop()
    wifi.radio.stop_ap()
    return None