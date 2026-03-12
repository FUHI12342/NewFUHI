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
        
        # Network recovery tracking
        self.consecutive_failures = 0
        self.last_recovery_attempt = 0
        self.recovery_backoff_sec = 10  # Start at 10s, max 60s
        
        # Outbox queue (RAM only - Phase 1)
        self.outbox = []  # Failed events queue
        self.max_outbox_size = 200  # Maximum queue size
        
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
    
    def get_device_config(self, device_id: str = None, save_to_file: bool = False) -> dict:
        """Get device configuration from Django API
        
        Args:
            device_id: Device ID to fetch config for
            save_to_file: If True, save config to wifi_config.json (may fail on read-only FS)
        
        Returns:
            Configuration dict or empty dict on failure
        """
        if not device_id:
            device_id = self.device_id
            
        if not self.session or not self.server_url:
            print("[API] No session or server URL available")
            return {}
        
        try:
            # Construct API endpoint URL
            config_url = f"{self.server_url.rstrip('/')}/api/iot/config/?device={device_id}"
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'X-API-KEY': self.api_key,
                'User-Agent': f'Pico2W-{device_id}'
            }
            
            print(f"[API] Fetching config from: {config_url}")
            
            # Make request
            response = self.session.get(config_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                config_data = response.json()
                print("[API] Configuration retrieved successfully")
                
                # Optional save (only if requested)
                if save_to_file:
                    try:
                        self.save_local_config(config_data)
                    except OSError as e:
                        if e.errno == 30:
                            print("[API] Skip save: read-only filesystem")
                        else:
                            print(f"[API] Save failed: {e}")
                    except Exception as e:
                        print(f"[API] Save error: {e}")
                
                return config_data
            else:
                print(f"[API] Config request failed: {response.status_code}")
                return {}
                
        except Exception as e:
            print(f"[API] Config request error: {e}")
            return {}
    
    def fetch_config(self, save_to_file: bool = False) -> dict:
        """Alias for get_device_config for backward compatibility"""
        return self.get_device_config(save_to_file=save_to_file)
    
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
    
    def post_event(self, event_data: dict) -> tuple:
        """Post event to Django API with failure tracking and outbox support
        
        Returns:
            tuple: (success: bool, status_code: int, info: str)
        """
        if not self.session or not self.server_url:
            print("[API] No session or server URL for event post")
            self.consecutive_failures += 1
            return (False, 0, "No session")
        
        try:
            # Construct event endpoint URL
            event_url = f"{self.server_url.rstrip('/')}/api/iot/events/"
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'X-API-KEY': self.api_key,
                'User-Agent': f'Pico2W-{self.device_id}'
            }
            
            # Ensure device field is set (Django requires it)
            event_data["device"] = self.device_id

            print(f"[API] Posting event to: {event_url}")

            # Make request
            response = self.session.post(event_url, json=event_data, headers=headers, timeout=10)
            
            if response.status_code in [200, 201]:
                print(f"[API] ✓ Event posted successfully ({response.status_code})")
                self.consecutive_failures = 0  # Reset on success
                self.recovery_backoff_sec = 10  # Reset backoff
                
                # Flush outbox on successful post (up to 5 items)
                if len(self.outbox) > 0:
                    self._flush_outbox(max_items=5)
                
                return (True, response.status_code, "Success")
            else:
                print(f"[API] Event post failed: {response.status_code}")
                self.consecutive_failures += 1
                
                # Enqueue to outbox
                self._enqueue_to_outbox(event_data)
                
                # Trigger recovery if failures >= 3
                if self.consecutive_failures >= 3:
                    print(f"[API] Consecutive failures: {self.consecutive_failures}, triggering recovery")
                    self.attempt_recovery()
                
                return (False, response.status_code, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.consecutive_failures += 1
            error_str = str(e).lower()
            
            # Enqueue to outbox
            self._enqueue_to_outbox(event_data)
            
            # Check for DNS/network errors
            if "getaddrinfo" in error_str or "name or service" in error_str or "dns" in error_str:
                print(f"[API] DNS/Network error detected: {e}")
            
            # Trigger recovery if failures >= 3
            if self.consecutive_failures >= 3:
                print(f"[API] Consecutive failures: {self.consecutive_failures}, triggering recovery")
                self.attempt_recovery()
            
            return (False, 0, f"Exception: {e}")
    
    def send_device_status(self, status_data: dict) -> bool:
        """Send device status to Django server"""
        if not self.session or not self.server_url:
            print("[API] No session or server URL for status update")
            return False
        
        try:
            # Construct status endpoint URL
            status_url = f"{self.server_url.rstrip('/')}/api/iot/status/"
            
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
                headers=headers,
                timeout=10
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
    
    def _should_attempt_recovery(self) -> bool:
        """Check if recovery should be attempted based on backoff"""
        now = time.monotonic()
        if now - self.last_recovery_attempt < self.recovery_backoff_sec:
            return False
        return True
    
    def _increase_backoff(self):
        """Increase backoff time (max 60s)"""
        self.recovery_backoff_sec = min(self.recovery_backoff_sec * 2, 60)
    
    def reset_session(self) -> bool:
        """Reset requests session and socket pool"""
        print("[API] Resetting session...")
        try:
            # Close existing session (CircuitPython doesn't have explicit close, just drop reference)
            if self.session:
                self.session = None
            
            if self.socket_pool:
                self.socket_pool = None
            
            # Re-init
            self._init_session()
            print("[API] Session reset complete")
            return True
        except Exception as e:
            print(f"[API] Session reset error: {e}")
            return False
    
    def attempt_recovery(self) -> bool:
        """Attempt to recover from network issues"""
        if not self._should_attempt_recovery():
            return False
        
        self.last_recovery_attempt = time.monotonic()
        print(f"[API] Recovery attempt (backoff: {self.recovery_backoff_sec}s, failures: {self.consecutive_failures})")
        
        # Step 1: Reset session
        if not self.reset_session():
            self._increase_backoff()
            return False
        
        # Step 2: Test connectivity
        if self.test_connection():
            print("[API] ✓ Recovery successful")
            self.consecutive_failures = 0
            self.recovery_backoff_sec = 10  # Reset backoff
            return True
        
        self._increase_backoff()
        return False
    
    def is_server_reachable(self) -> bool:
        """Check if server is reachable (for server vs WiFi failure isolation)"""
        if not wifi.radio.connected:
            return False
        
        try:
            # Simple connectivity test
            return self.test_connection()
        except Exception:
            return False
    
    def _enqueue_to_outbox(self, event_data: dict):
        """Add failed event to RAM outbox queue"""
        if len(self.outbox) >= self.max_outbox_size:
            dropped = self.outbox.pop(0)  # Drop oldest (FIFO)
            print(f"[OUTBOX] Queue full ({self.max_outbox_size}), dropped oldest event")
        
        self.outbox.append({
            'timestamp': time.time(),
            'event': event_data
        })
        print(f"[OUTBOX] Enqueued event ({len(self.outbox)}/{self.max_outbox_size} items)")
    
    def _flush_outbox(self, max_items: int = 10) -> int:
        """Flush outbox queue by sending to API
        
        Args:
            max_items: Maximum number of items to send in this flush
            
        Returns:
            Number of items successfully sent
        """
        if not self.outbox:
            return 0
        
        items_sent = 0
        print(f"[OUTBOX] Flushing queue ({len(self.outbox)} items, max {max_items})...")
        
        while self.outbox and items_sent < max_items:
            item = self.outbox[0]  # Peek first
            
            try:
                # Try to post the event
                event_url = f"{self.server_url.rstrip('/')}/api/iot/events/"
                headers = {
                    'Content-Type': 'application/json',
                    'X-API-KEY': self.api_key,
                    'User-Agent': f'Pico2W-{self.device_id}'
                }
                
                response = self.session.post(event_url, json=item['event'], headers=headers, timeout=10)
                
                if response.status_code in [200, 201]:
                    # Success - remove from queue
                    self.outbox.pop(0)
                    items_sent += 1
                    print(f"[OUTBOX] ✓ Sent queued event ({items_sent}/{max_items})")
                else:
                    # HTTP error - abort flush (network still issues)
                    print(f"[OUTBOX] Flush aborted: HTTP {response.status_code}")
                    break
                    
            except Exception as e:
                # Network error - abort flush
                print(f"[OUTBOX] Flush aborted: {e}")
                break
        
        if items_sent > 0:
            print(f"[OUTBOX] ✓ Flushed {items_sent} items, {len(self.outbox)} remaining")
        
        return items_sent