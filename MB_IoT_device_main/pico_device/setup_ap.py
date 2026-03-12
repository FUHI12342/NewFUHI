# Setup Access Point for Pico 2 W configuration
# Provides web interface for WiFi and server configuration

import json
import time
from .file_utils import ConfigFileManager

class SetupAPHandler:
    """Manages Setup AP mode and configuration web interface"""
    
    def __init__(self, device_id):
        self.device_id = device_id
        self.ssid = f"PICO-SETUP-{device_id}"
        self.password = "SETUP_PASSWORD"
        self.web_server = None
        self.ap_ip = "192.168.4.1"
        self.is_active = False
        self.config_saved = False
        self.config_manager = ConfigFileManager()
    
    def activate_setup_mode(self):
        """Activates access point and starts web server"""
        print(f"[SETUP] *** ACTIVATING SETUP AP MODE ***")
        print(f"[SETUP] SSID: {self.ssid}")
        print(f"[SETUP] Password: {self.password}")
        print(f"[SETUP] Web interface: http://{self.ap_ip}")
        
        try:
            # For CircuitPython implementation:
            import wifi
            import ipaddress
            
            # Stop any existing connections
            if wifi.radio.connected:
                wifi.radio.stop_station()
            
            # Start access point (minimal arguments - dns not supported)
            wifi.radio.start_ap(ssid=self.ssid, password=self.password)
            wifi.radio.set_ipv4_address_ap(
                ipv4=ipaddress.IPv4Address("192.168.4.1"),
                netmask=ipaddress.IPv4Address("255.255.255.0"),
                gateway=ipaddress.IPv4Address("192.168.4.1")
            )
            
            self.is_active = True
            print(f"[SETUP] Access Point activated successfully")
            
        except Exception as e:
            print(f"[SETUP] CRITICAL: Failed to activate AP: {str(e)}")
            raise
    
    def handle_config_update(self, form_data):
        """Processes configuration updates from web interface"""
        try:
            # Validate form data
            required_fields = ['wifi_ssid', 'wifi_password', 'server_url', 'api_key']
            for field in required_fields:
                if not form_data.get(field):
                    print(f"[SETUP] Missing required field: {field}")
                    return False
            
            # Create configuration object
            config_data = {
                'wifi_ssid': form_data['wifi_ssid'],
                'wifi_password': form_data['wifi_password'],
                'server_url': form_data['server_url'],
                'api_key': form_data['api_key'],
                'device_name': form_data.get('device_name', self.device_id),
                'device_id': self.device_id
            }
            
            # Validate configuration structure
            if not self.config_manager.validate_config(config_data):
                print(f"[SETUP] Configuration validation failed")
                return False
            
            # Save configuration using robust file manager
            success = self.config_manager.save_config(config_data)
            
            if success:
                print(f"[SETUP] Configuration saved successfully")
                return True
            else:
                print(f"[SETUP] Failed to save configuration")
                return False
            
        except Exception as e:
            print(f"[SETUP] Error saving configuration: {str(e)}")
            return False
    
    def get_config_status(self):
        """Get current configuration file status"""
        return self.config_manager.get_config_status()
    
    def serve_web_interface(self):
        """Serves configuration web interface at 192.168.4.1"""
        if not self.is_active:
            print(f"[SETUP] ERROR: Cannot serve web interface - AP not active")
            return
            
        print(f"[SETUP] Starting web server at http://{self.ap_ip}")
        
        try:
            # For CircuitPython implementation:
            import socketpool
            import wifi
            
            pool = socketpool.SocketPool(wifi.radio)
            server_socket = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
            server_socket.bind((self.ap_ip, 80))
            server_socket.listen(1)
            
            print(f"[SETUP] Web server listening on {self.ap_ip}:80")
            
            while not self.config_saved:
                try:
                    client, addr = server_socket.accept()
                    self._handle_http_request(client)
                    client.close()
                except Exception as e:
                    print(f"[SETUP] Request handling error: {e}")
                    time.sleep(0.1)
            
        except Exception as e:
            print(f"[SETUP] CRITICAL: Web server error: {str(e)}")
            raise
    
    def _handle_http_request(self, client_socket):
        """Handle HTTP request from client - CircuitPython compatible"""
        try:
            # Read request
            request = client_socket.recv(1024).decode('utf-8')
            
            if 'GET /' in request:
                # Serve configuration form
                response = self._generate_http_response(self._generate_config_form())
                client_socket.send(response.encode('utf-8'))
                
            elif 'POST /save' in request:
                # Process form submission
                form_data = self._parse_form_data(request)
                if self.handle_config_update(form_data):
                    success_html = self._generate_success_page()
                    response = self._generate_http_response(success_html)
                    self.config_saved = True
                else:
                    error_html = self._generate_error_page("Configuration save failed")
                    response = self._generate_http_response(error_html)
                
                client_socket.send(response.encode('utf-8'))
                
            else:
                # 404 Not Found
                response = self._generate_http_response("<h1>404 Not Found</h1>", status="404 Not Found")
                client_socket.send(response.encode('utf-8'))
                
        except Exception as e:
            print(f"[SETUP] HTTP request handling error: {str(e)}")
            error_response = self._generate_http_response("<h1>500 Internal Server Error</h1>", status="500 Internal Server Error")
            try:
                client_socket.send(error_response.encode('utf-8'))
            except:
                pass
    
    def _generate_http_response(self, html_content, status="200 OK"):
        """Generate HTTP response with proper headers"""
        return f"""HTTP/1.1 {status}\r
Content-Type: text/html; charset=utf-8\r
Content-Length: {len(html_content)}\r
Connection: close\r
\r
{html_content}"""
    
    def _parse_form_data(self, request):
        """Parse form data from POST request"""
        form_data = {}
        
        try:
            # Find the form data in the request body
            if '\r\n\r\n' in request:
                body = request.split('\r\n\r\n', 1)[1]
                
                # Parse URL-encoded form data
                for pair in body.split('&'):
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        # Basic URL decoding
                        key = key.replace('+', ' ').replace('%20', ' ')
                        value = value.replace('+', ' ').replace('%20', ' ')
                        form_data[key] = value
                        
        except Exception as e:
            print(f"[SETUP] Form parsing error: {str(e)}")
            
        return form_data
    
    def _generate_config_form(self):
        """Generate HTML configuration form"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Pico WiFi Setup - {self.device_id}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; text-align: center; }}
        h2 {{ color: #666; border-bottom: 2px solid #eee; padding-bottom: 5px; }}
        label {{ display: block; margin: 10px 0 5px 0; font-weight: bold; }}
        input {{ width: 100%; padding: 8px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }}
        button {{ background-color: #007cba; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%; }}
        button:hover {{ background-color: #005a87; }}
        .info {{ background-color: #e7f3ff; padding: 10px; border-radius: 4px; margin-bottom: 20px; }}
        .required {{ color: red; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Pico WiFi Configuration</h1>
        <div class="info">
            <strong>Device ID:</strong> {self.device_id}<br>
            <strong>Setup Network:</strong> {self.ssid}
        </div>
        
        <form method="POST" action="/save">
            <h2>WiFi Settings <span class="required">*</span></h2>
            <label for="wifi_ssid">Network Name (SSID) <span class="required">*</span></label>
            <input type="text" id="wifi_ssid" name="wifi_ssid" required placeholder="Enter WiFi network name">
            
            <label for="wifi_password">WiFi Password <span class="required">*</span></label>
            <input type="password" id="wifi_password" name="wifi_password" required placeholder="Enter WiFi password">
            
            <h2>Server Settings <span class="required">*</span></h2>
            <label for="server_url">Server URL <span class="required">*</span></label>
            <input type="url" id="server_url" name="server_url" required placeholder="https://your-server.com">
            
            <label for="api_key">API Key <span class="required">*</span></label>
            <input type="text" id="api_key" name="api_key" required placeholder="Enter API key">
            
            <h2>Device Settings</h2>
            <label for="device_name">Device Name (Optional)</label>
            <input type="text" id="device_name" name="device_name" placeholder="Custom device name" value="{self.device_id}">
            
            <button type="submit">Save Configuration & Restart</button>
        </form>
    </div>
</body>
</html>"""
    
    def _generate_success_page(self):
        """Generate success page after configuration save"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Configuration Saved - {self.device_id}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .success {{ background-color: #d4edda; color: #155724; padding: 15px; border-radius: 4px; margin-bottom: 20px; }}
        h1 {{ color: #333; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Configuration Saved Successfully!</h1>
        <div class="success">
            <strong>✓ Configuration has been saved</strong><br>
            The device will now restart and attempt to connect to your WiFi network.
        </div>
        <p>You can now disconnect from this setup network. The device will be available on your main WiFi network shortly.</p>
        <p><strong>Device ID:</strong> {self.device_id}</p>
    </div>
</body>
</html>"""
    
    def _generate_error_page(self, error_message):
        """Generate error page for configuration failures"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Configuration Error - {self.device_id}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .error {{ background-color: #f8d7da; color: #721c24; padding: 15px; border-radius: 4px; margin-bottom: 20px; }}
        h1 {{ color: #333; text-align: center; }}
        a {{ color: #007cba; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Configuration Error</h1>
        <div class="error">
            <strong>✗ Error:</strong> {error_message}
        </div>
        <p>Please check your settings and try again.</p>
        <p><a href="/">← Back to Configuration Form</a></p>
    </div>
</body>
</html>"""
    
    def trigger_reconnection(self):
        """Trigger device reconnection after configuration save"""
        print(f"[SETUP] Triggering device reconnection...")
        print(f"[SETUP] Stopping Setup AP...")
        
        try:
            # For CircuitPython implementation:
            import wifi
            import microcontroller
            
            # Stop access point
            wifi.radio.stop_ap()
            
            # Small delay before restart
            time.sleep(2)
            
            # Restart device to apply new configuration
            microcontroller.reset()
            
        except Exception as e:
            print(f"[SETUP] Error during reconnection: {str(e)}")
    
    def stop_setup_mode(self):
        """Stop Setup AP mode and clean up resources"""
        if self.is_active:
            print(f"[SETUP] Stopping Setup AP mode")
            
            try:
                # For CircuitPython implementation:
                import wifi
                wifi.radio.stop_ap()
                
                self.is_active = False
                self.config_saved = False
                print(f"[SETUP] Setup AP stopped successfully")
                
            except Exception as e:
                print(f"[SETUP] Error stopping Setup AP: {str(e)}")
    
    def is_setup_active(self):
        """Check if Setup AP mode is currently active"""
        return self.is_active
    
    def get_setup_info(self):
        """Get Setup AP connection information"""
        return {
            'ssid': self.ssid,
            'password': self.password,
            'ip_address': self.ap_ip,
            'web_url': f"http://{self.ap_ip}",
            'device_id': self.device_id,
            'is_active': self.is_active
        }