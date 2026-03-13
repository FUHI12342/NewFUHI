# CircuitPython WiFi Provisioning for Pico 2 W
# Handles Setup AP mode and web configuration interface

import wifi
import socketpool
import time
import json
import microcontroller

class ProvisioningManager:
    """Manages WiFi provisioning through Setup AP mode"""
    
    def __init__(self, device_id: str, setup_password: str = "SETUP_PASSWORD"):
        self.device_id = device_id
        self.setup_ssid = f"PICO-SETUP-{device_id}"
        self.setup_password = setup_password
        self.ap_ip = "192.168.4.1"
        self.web_server = None
        self.socket_pool = None
        
    def enter_setup_mode(self, secrets=None, buzzer=None):
        """Enter Setup AP mode - maintains backward compatibility"""
        print(f"[PROVISIONING] Entering Setup AP mode")
        print(f"[PROVISIONING] SSID: {self.setup_ssid}")
        print(f"[PROVISIONING] Password: {self.setup_password}")
        print(f"[PROVISIONING] Web interface: http://{self.ap_ip}")
        
        try:
            # Stop any existing WiFi connections
            if wifi.radio.connected:
                wifi.radio.stop_station()
            
            # Start Access Point
            wifi.radio.start_ap(
                ssid=self.setup_ssid,
                password=self.setup_password
            )
            
            print(f"[PROVISIONING] AP started successfully")
            print(f"[PROVISIONING] IP: {wifi.radio.ipv4_address_ap}")
            
            # Create socket pool for web server
            self.socket_pool = socketpool.SocketPool(wifi.radio)
            
            # Start web server
            self._start_web_server()
            
            # Optional: Sound buzzer to indicate setup mode
            if buzzer:
                self._signal_setup_mode(buzzer)
                
        except Exception as e:
            print(f"[PROVISIONING] Error starting AP: {e}")
            raise
    
    def _start_web_server(self):
        """Start web server for configuration interface"""
        try:
            # Create server socket
            server_socket = self.socket_pool.socket(
                self.socket_pool.AF_INET, 
                self.socket_pool.SOCK_STREAM
            )
            server_socket.bind(('0.0.0.0', 80))
            server_socket.listen(1)
            
            print(f"[PROVISIONING] Web server listening on port 80")
            
            # Server loop
            while True:
                try:
                    client_socket, addr = server_socket.accept()
                    print(f"[PROVISIONING] Client connected from {addr}")
                    
                    # Handle request
                    self._handle_request(client_socket)
                    
                except Exception as e:
                    print(f"[PROVISIONING] Request handling error: {e}")
                    
        except Exception as e:
            print(f"[PROVISIONING] Web server error: {e}")
            raise
    
    def _handle_request(self, client_socket):
        """Handle HTTP request from client"""
        try:
            # Read request
            request = client_socket.recv(1024).decode('utf-8')
            print(f"[PROVISIONING] Request: {request[:100]}...")
            
            # Parse request
            lines = request.split('\n')
            if len(lines) > 0:
                request_line = lines[0]
                method, path, _ = request_line.split(' ')
                
                if method == 'GET':
                    if path == '/' or path == '/index.html':
                        self._serve_config_form(client_socket)
                    else:
                        self._serve_404(client_socket)
                        
                elif method == 'POST':
                    if path == '/save':
                        self._handle_config_save(client_socket, request)
                    else:
                        self._serve_404(client_socket)
                        
                else:
                    self._serve_404(client_socket)
            
        except Exception as e:
            print(f"[PROVISIONING] Request error: {e}")
            self._serve_error(client_socket, str(e))
        finally:
            client_socket.close()
    
    def _serve_config_form(self, client_socket):
        """Serve configuration form HTML"""
        html = self._generate_config_html()
        
        response = f"""HTTP/1.1 200 OK
Content-Type: text/html
Content-Length: {len(html)}
Connection: close

{html}"""
        
        client_socket.send(response.encode('utf-8'))
    
    def _handle_config_save(self, client_socket, request):
        """Handle configuration save from form"""
        try:
            # Extract form data from POST request
            form_data = self._parse_form_data(request)
            
            # Validate required fields
            required_fields = ['wifi_ssid', 'wifi_password', 'server_url', 'api_key']
            for field in required_fields:
                if not form_data.get(field):
                    raise ValueError(f"Missing required field: {field}")
            
            # Save configuration
            config_data = {
                'wifi_ssid': form_data['wifi_ssid'],
                'wifi_password': form_data['wifi_password'],
                'server_url': form_data['server_url'],
                'api_key': form_data['api_key'],
                'device_name': form_data.get('device_name', self.device_id),
                'device_id': self.device_id
            }
            
            # Write to wifi_config.json
            self._save_config_file(config_data)
            
            # Send success response
            success_html = self._generate_success_html()
            response = f"""HTTP/1.1 200 OK
Content-Type: text/html
Content-Length: {len(success_html)}
Connection: close

{success_html}"""
            
            client_socket.send(response.encode('utf-8'))
            
            print("[PROVISIONING] Configuration saved successfully")
            
            # Schedule restart to apply new configuration
            print("[PROVISIONING] Restarting in 3 seconds...")
            time.sleep(3)
            microcontroller.reset()
            
        except Exception as e:
            print(f"[PROVISIONING] Config save error: {e}")
            self._serve_error(client_socket, str(e))
    
    def _parse_form_data(self, request):
        """Parse form data from POST request"""
        form_data = {}
        
        # Find the form data in the request body
        lines = request.split('\n')
        body_start = False
        
        for line in lines:
            if body_start:
                # Parse URL-encoded form data
                pairs = line.split('&')
                for pair in pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        # URL decode (basic implementation)
                        value = value.replace('+', ' ')
                        value = value.replace('%20', ' ')
                        form_data[key] = value
                break
            elif line.strip() == '':
                body_start = True
        
        return form_data
    
    def _save_config_file(self, config_data):
        """Save configuration to wifi_config.json with backup"""
        import os
        
        # Create backup if file exists
        if 'wifi_config.json' in os.listdir('.'):
            try:
                os.rename('wifi_config.json', 'wifi_config.json.backup')
                print("[PROVISIONING] Created backup: wifi_config.json.backup")
            except OSError as e:
                print(f"[PROVISIONING] Backup warning: {e}")
        
        # Write new configuration
        with open('wifi_config.json', 'w') as f:
            json.dump(config_data, f)
        
        print("[PROVISIONING] Configuration saved to wifi_config.json")
    
    def _generate_config_html(self):
        """Generate configuration form HTML"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Pico WiFi Setup - {self.device_id}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }}
        .container {{ max-width: 500px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; text-align: center; }}
        .form-group {{ margin-bottom: 15px; }}
        label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
        input[type="text"], input[type="password"], input[type="url"] {{ width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }}
        button {{ background: #007cba; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; width: 100%; font-size: 16px; }}
        button:hover {{ background: #005a87; }}
        .info {{ background: #e7f3ff; padding: 10px; border-radius: 4px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Pico WiFi Setup</h1>
        <div class="info">
            <strong>Device ID:</strong> {self.device_id}<br>
            <strong>Setup Network:</strong> {self.setup_ssid}
        </div>
        
        <form method="POST" action="/save">
            <div class="form-group">
                <label for="wifi_ssid">WiFi Network Name (SSID):</label>
                <input type="text" id="wifi_ssid" name="wifi_ssid" required>
            </div>
            
            <div class="form-group">
                <label for="wifi_password">WiFi Password:</label>
                <input type="password" id="wifi_password" name="wifi_password" required>
            </div>
            
            <div class="form-group">
                <label for="server_url">Server URL:</label>
                <input type="url" id="server_url" name="server_url" placeholder="https://your-server.com" required>
            </div>
            
            <div class="form-group">
                <label for="api_key">API Key:</label>
                <input type="text" id="api_key" name="api_key" required>
            </div>
            
            <div class="form-group">
                <label for="device_name">Device Name (optional):</label>
                <input type="text" id="device_name" name="device_name" value="{self.device_id}">
            </div>
            
            <button type="submit">Save Configuration</button>
        </form>
    </div>
</body>
</html>"""
    
    def _generate_success_html(self):
        """Generate success page HTML"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Configuration Saved - {self.device_id}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }}
        .container {{ max-width: 500px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }}
        .success {{ color: #28a745; font-size: 18px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Configuration Saved!</h1>
        <div class="success">✓ WiFi settings have been saved successfully</div>
        <p>The device will restart and connect to your WiFi network.</p>
        <p>You can now disconnect from the setup network.</p>
    </div>
</body>
</html>"""
    
    def _serve_404(self, client_socket):
        """Serve 404 Not Found response"""
        response = """HTTP/1.1 404 Not Found
Content-Type: text/html
Connection: close

<html><body><h1>404 Not Found</h1></body></html>"""
        client_socket.send(response.encode('utf-8'))
    
    def _serve_error(self, client_socket, error_msg):
        """Serve error response"""
        html = f"<html><body><h1>Error</h1><p>{error_msg}</p></body></html>"
        response = f"""HTTP/1.1 500 Internal Server Error
Content-Type: text/html
Content-Length: {len(html)}
Connection: close

{html}"""
        client_socket.send(response.encode('utf-8'))
    
    def _signal_setup_mode(self, buzzer):
        """Signal setup mode with buzzer (if available)"""
        try:
            # Beep pattern to indicate setup mode
            for _ in range(3):
                buzzer.value = True
                time.sleep(0.1)
                buzzer.value = False
                time.sleep(0.1)
        except Exception as e:
            print(f"[PROVISIONING] Buzzer error: {e}")

# Backward compatibility function
def enter_setup_mode(secrets=None, buzzer=None, device_id="PICO001"):
    """Backward compatible entry point for setup mode"""
    provisioning = ProvisioningManager(device_id)
    provisioning.enter_setup_mode(secrets, buzzer)