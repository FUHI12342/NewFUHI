# Django API Client for CircuitPython Pico 2 W
# Handles communication with Django server for configuration and data sync

import json
import time
import ssl
import wifi
import socketpool
import adafruit_requests

class DjangoAPIClient:
    """Django API client for CircuitPython - maintains backward compatibility"""
    
    def __init__(self, server_url: str = None, api_key: str = None, device_id: str = "PICO001"):
        self.server_url = server_url
        self.api_key = api_key
        self.device_id = device_id
        self.session = None
        self.socket_pool = None
        
        # Initialize requests session if WiFi is available
        if wifi.radio.connected:
            self._init_session()
    
    def _init_session(self):
        """Initialize HTTP session"""
        try:
            self.socket_pool = socketpool.SocketPool(wifi.radio)
            
            # Create SSL context (for HTTPS)
            ssl_context = ssl.create_default_context()
            
            # Initialize requests session
            self.session = adafruit_requests.Session(
                self.socket_pool, 
                ssl_context
            )
            
            print("[API] Session initialized")
            
        except Exception as e:
            print(f"[API] Session init error: {e}")
            self.session = None
    
    def get_device_config(self, device_id: str = None) -> dict:
        """Get device configuration from Django API"""
        if not device_id:
            device_id = self.device_id
            
        if not self.session or not self.server_url:
            print("[API] No session or server URL available")
            return {}
        
        try:
            # Construct API endpoint URL
            config_url = f"{self.server_url.rstrip('/')}/booking/api/iot/config/{device_id}/"
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': f'Pico2W-{device_id}'
            }
            
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            print(f"[API] Fetching config from: {config_url}")
            
            # Make request (no timeout parameter for CircuitPython compatibility)
            response = self.session.get(config_url, headers=headers)
            
            if response.status_code == 200:
                config_data = response.json()
                print("[API] Configuration retrieved successfully")
                return config_data
            else:
                print(f"[API] Config request failed: {response.status_code}")
                return {}
                
        except Exception as e:
            print(f"[API] Config request error: {e}")
            return {}
    
    def load_local_config(self) -> dict:
        """Load configuration from local wifi_config.json file"""
        try:
            with open('wifi_config.json', 'r') as f:
                config_data = json.load(f)
            
            print("[API] Local config loaded successfully")
            return config_data
            
        except OSError:
            print("[API] Local config file not found")
            return {}
        except json.JSONDecodeError as e:
            print(f"[API] Local config JSON error: {e}")
            return {}
        except Exception as e:
            print(f"[API] Local config error: {e}")
            return {}
    
    def save_local_config(self, config_data: dict) -> bool:
        """Save configuration to local wifi_config.json file"""
        try:
            import os
            
            # Create backup if file exists
            if 'wifi_config.json' in os.listdir('.'):
                try:
                    os.rename('wifi_config.json', 'wifi_config.json.backup')
                    print("[API] Created config backup")
                except OSError:
                    pass  # Backup failed, continue anyway
            
            # Write new configuration
            with open('wifi_config.json', 'w') as f:
                json.dump(config_data, f)
            
            print("[API] Local config saved successfully")
            return True
            
        except Exception as e:
            print(f"[API] Local config save error: {e}")
            return False
    
    def apply_server_wifi_config(self, server_config: dict) -> bool:
        """Apply WiFi configuration from server if different from current"""
        try:
            # Get current local config
            local_config = self.load_local_config()
            
            # Extract WiFi settings from server config
            server_wifi = server_config.get('wifi', {})
            if not server_wifi:
                print("[API] No WiFi config in server response")
                return False
            
            # Check if WiFi settings are different
            local_wifi_ssid = local_config.get('wifi_ssid', '')
            local_wifi_password = local_config.get('wifi_password', '')
            
            server_wifi_ssid = server_wifi.get('ssid', '')
            server_wifi_password = server_wifi.get('password', '')
            
            if (local_wifi_ssid == server_wifi_ssid and 
                local_wifi_password == server_wifi_password):
                print("[API] WiFi config unchanged")
                return False
            
            # Update local config with server WiFi settings
            updated_config = local_config.copy()
            updated_config.update({
                'wifi_ssid': server_wifi_ssid,
                'wifi_password': server_wifi_password,
                'server_url': server_config.get('server', {}).get('url', self.server_url),
                'api_key': server_config.get('server', {}).get('api_key', self.api_key),
                'device_name': server_config.get('device', {}).get('name', self.device_id),
                'device_id': self.device_id
            })
            
            # Save updated config
            if self.save_local_config(updated_config):
                print("[API] Server WiFi config applied successfully")
                return True
            else:
                print("[API] Failed to save server WiFi config")
                return False
                
        except Exception as e:
            print(f"[API] Apply server config error: {e}")
            return False
    
    def send_device_status(self, status_data: dict) -> bool:
        """Send device status to Django server"""
        if not self.session or not self.server_url:
            print("[API] No session or server URL for status update")
            return False
        
        try:
            # Construct status endpoint URL
            status_url = f"{self.server_url.rstrip('/')}/booking/api/iot/status/"
            
            # Prepare payload
            payload = {
                'device_id': self.device_id,
                'timestamp': time.time(),
                **status_data
            }
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': f'Pico2W-{self.device_id}'
            }
            
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            print(f"[API] Sending status to: {status_url}")
            
            # Make request
            response = self.session.post(
                status_url, 
                json=payload, 
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                print("[API] Status sent successfully")
                return True
            else:
                print(f"[API] Status request failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"[API] Status send error: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test connection to Django server"""
        if not self.session or not self.server_url:
            return False
        
        try:
            # Try to get device config as a connection test
            config = self.get_device_config()
            return bool(config)
            
        except Exception as e:
            print(f"[API] Connection test error: {e}")
            return False
    
    def update_credentials(self, server_url: str = None, api_key: str = None):
        """Update API credentials"""
        if server_url:
            self.server_url = server_url
        if api_key:
            self.api_key = api_key
        
        # Reinitialize session if WiFi is connected
        if wifi.radio.connected:
            self._init_session()
    
    def is_server_reachable(self) -> bool:
        """Check if server is reachable (for server vs WiFi failure isolation)"""
        if not wifi.radio.connected:
            return False
        
        try:
            # Simple connectivity test
            return self.test_connection()
        except Exception:
            return False