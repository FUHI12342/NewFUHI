# django_api.py
# Helper module for communicating with Django backend APIs
import time
import json

try:
    import wifi
    import socketpool
    import ssl
    import adafruit_requests
except ImportError:
    # Fallback for testing/simulation
    wifi = None
    socketpool = None
    ssl = None
    adafruit_requests = None

class DjangoAPIClient:
    """
    Django backend API client for IoT device
    Handles:
    - WiFi connection management
    - Config fetching from /booking/api/iot/config/
    - Event posting to /booking/api/iot/events/
    -Auto-retry with exponential backoff
    """
    
    def __init__(self, secrets_dict=None, debug=False, **kwargs):
        """
        secrets_dict should contain:
        - ssid, password (WiFi)
        - api_key (X-API-KEY header)
        - device (device identifier)
        - server_base (e.g., "https://example.com")
        - events_endpoint (optional, default: "/booking/api/iot/events/")
        - config_endpoint (optional, default: "/booking/api/iot/config/")

        Also supports keyword arguments (WiFi Hardening compatibility):
          DjangoAPIClient(server_url=..., api_key=..., device_id=...)
        """
        if secrets_dict is None:
            secrets_dict = {
                'server_url': kwargs.get('server_url', ''),
                'api_key': kwargs.get('api_key', ''),
                'device': kwargs.get('device_id', 'unknown'),
            }
        self.secrets = secrets_dict
        self.debug = debug
        self.api_key = secrets_dict.get("api_key", "")
        self.device = secrets_dict.get("device", "unknown")
        
        # Primary key is 'server_url', fallback to 'server_base'
        self.server_url = secrets_dict.get("server_url") or secrets_dict.get("server_base", "")
        self.server_url = self.server_url.rstrip("/")
        
        self.events_endpoint = secrets_dict.get("events_endpoint", "/booking/api/iot/events/")
        self.config_endpoint = secrets_dict.get("config_endpoint", "/booking/api/iot/config/")
        
        # Stricter Guard: Check for placeholders or invalid URLs
        self.server_configured = True
        u_low = self.server_url.lower()
        if not self.server_url or \
           "your-server.com" in u_low or \
           "example.com" in u_low or \
           "localhost" in u_low or \
           "<" in self.server_url or \
           ">" in self.server_url:
            self.server_configured = False
            self.log("Server URL not configured; API communication disabled.")
        
        self.pool = None
        self.requests = None
        self.wifi_connected = False
        self.wifi_ssid = secrets_dict.get("ssid", "")
        self.wifi_password = secrets_dict.get("password", "")
        
        # Server config cache
        self.server_config = None
        
        # Network Auto-Recovery (Ticket C)
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.last_failure_time = 0
        self.backoff_delay = 0  # seconds to wait before next attempt
        
        # Outbox Queue (Ticket D)
        self.outbox = []  # List of failed events for retry
        self.max_outbox_size = 200  # FIFO eviction
        self.max_payload_size = 2000  # bytes, reject huge payloads
        
    def log(self, msg):
        if self.debug:
            print(f"[DjangoAPI] {msg}")
            
    def now_iso8601(self):
        """
        Generate ISO8601 timestamp without using strftime (not in CircuitPython).
        Returns string like "2024-01-14T12:34:56" or "boot:<ms>" if time not set.
        """
        try:
            t = time.time()
            # CircuitPython typically defaults to 2000-01-01 if not set
            if t < 1600000000:  # If before 2020, assume time not set via NTP
                return "boot:{}".format(int(time.monotonic() * 1000))
            
            s = time.localtime(t)
            # s is a struct_time: (tm_year, tm_mon, tm_mday, tm_hour, tm_min, tm_sec, tm_wday, tm_yday, tm_isdst)
            return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
                s[0], s[1], s[2], s[3], s[4], s[5]
            )
        except Exception:
            # Fallback that NEVER fails
            try:
                ms = int(time.monotonic() * 1000)
                return "boot:{}".format(ms)
            except:
                return "boot:0"
    
    def connect_wifi(self, ssid=None, password=None, retries=3):
        """
        Connect to WiFi. If ssid/password provided, use those instead of secrets.
        Returns True if successful, False otherwise.
        """
        if wifi is None:
            self.log("WiFi module not available (running in simulation?)")
            return False
        
        # Use provided credentials or fall back to secrets
        _ssid = ssid or self.wifi_ssid
        _password = password or self.wifi_password
        
        if not _ssid or not _password:
            self.log("SSID/password not provided")
            return False
        
        self.log(f"Connecting to WiFi: {_ssid}")
        
        for attempt in range(retries):
            try:
                # Disconnect if already connected
                if wifi.radio.connected:
                    wifi.radio.stop_station()
                
                wifi.radio.connect(_ssid, _password)
                
                if wifi.radio.connected:
                    self.log(f"WiFi connected! IP: {wifi.radio.ipv4_address}")
                    self.wifi_connected = True
                    self.wifi_ssid = _ssid  # Update current SSID
                    self.wifi_password = _password
                    
                    # Initialize request session
                    if self.pool is None:
                        self.pool = socketpool.SocketPool(wifi.radio)
                    if self.requests is None:
                        self.requests = adafruit_requests.Session(self.pool, ssl.create_default_context())
                    
                    return True
                else:
                    self.log(f"WiFi connection failed (attempt {attempt+1}/{retries})")
            except Exception as e:
                self.log(f"WiFi connect error (attempt {attempt+1}/{retries}): {e}")
                time.sleep(2)
        
        self.wifi_connected = False
        return False
    
    def ensure_connection(self):
        """Check WiFi connection, reconnect if needed"""
        if wifi is None:
            return False
        
        if not wifi.radio.connected:
            self.wifi_connected = False
            self.log("WiFi disconnected, attempting reconnect...")
            return self.connect_wifi()
        
        return True
    
    def _should_backoff(self):
        """Check if we should delay due to backoff"""
        if self.backoff_delay <= 0:
            return False
        
        elapsed = time.monotonic() - self.last_failure_time
        if elapsed < self.backoff_delay:
            remaining = self.backoff_delay - elapsed
            self.log(f"Backoff active: {remaining:.1f}s remaining")
            return True
        
        # Backoff period expired
        return False
    
    def _handle_connection_failure(self):
        """Handle connection failure with exponential backoff and recovery"""
        self.consecutive_failures += 1
        self.last_failure_time = time.monotonic()
        
        # Exponential backoff: min(60, 2^n) seconds
        self.backoff_delay = min(60, 2 ** min(self.consecutive_failures, 6))
        self.log(f"Connection failure #{self.consecutive_failures}, backoff: {self.backoff_delay}s")
        
        # Reset session/pool on persistent failures
        if self.consecutive_failures >= 3:
            self.log("Resetting requests session and socket pool...")
            self.requests = None
            self.pool = None
        
        # Try WiFi reset on severe failures
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.log("Max failures reached, attempting WiFi reconnection...")
            self.wifi_connected = False
            return self.connect_wifi()
        
        return False
    
    def _handle_connection_success(self):
        """Reset failure counters on successful connection"""
        if self.consecutive_failures > 0:
            self.log(f"Connection recovered after {self.consecutive_failures} failures")
        self.consecutive_failures = 0
        self.backoff_delay = 0
    
    def fetch_config(self, save_to_file=True):
        """
        Fetch config from Django backend: GET /booking/api/iot/config/?device=...
        Returns dict with config or None on failure.
        """
        if not self.server_configured:
            return None
        
        # Check backoff
        if self._should_backoff():
            return None
            
        if not self.ensure_connection():
            self.log("Cannot fetch config: no WiFi connection")
            self._handle_connection_failure()
            return None
        
        url = f"{self.server_url}{self.config_endpoint}?device={self.device}"
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        self.log(f"Fetching config from {url}")
        
        try:
            response = self.requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                config = response.json()
                self.log(f"Config fetched: {config}")
                self.server_config = config
                
                # Save to local file for next boot
                if save_to_file:
                    try:
                        with open("wifi_config.json", "w") as f:
                            json.dump(config, f)
                        self.log("Config saved to wifi_config.json")
                    except Exception as e:
                        self.log(f"Failed to save config: {e}")
                
                response.close()
                self._handle_connection_success()
                return config
            else:
                self.log(f"Config fetch failed: HTTP {response.status_code}")
                response.close()
                return None
        except Exception as e:
            self.log(f"Config fetch exception: {e}")
            self._handle_connection_failure()
            return None
    
    def enqueue_event(self, event_data, reason="unknown"):
        """Add failed event to outbox for later retry"""
        try:
            # Check payload size
            payload_str = json.dumps(event_data)
            if len(payload_str) > self.max_payload_size:
                self.log(f"Event too large ({len(payload_str)} bytes), dropping")
                return
            
            # FIFO eviction if at capacity
            if len(self.outbox) >= self.max_outbox_size:
                dropped = self.outbox.pop(0)
                self.log(f"Outbox full, dropped oldest event: {dropped.get('event_type')}")
            
            # Add to outbox
            event_copy = event_data.copy()
            event_copy["_outbox_reason"] = reason
            event_copy["_outbox_ts"] = time.monotonic()
            self.outbox.append(event_copy)
            self.log(f"Enqueued event to outbox ({len(self.outbox)}/{self.max_outbox_size}): {event_data.get('event_type')}")
            
        except Exception as e:
            self.log(f"Failed to enqueue event: {e}")
    
    def flush_outbox(self, max_items=5):
        """Attempt to send queued events, limited batch size"""
        if not self.outbox:
            return 0
        
        self.log(f"Flushing outbox ({len(self.outbox)} events, max={max_items})...")
        sent_count = 0
        
        # Process in order (FIFO)
        while self.outbox and sent_count < max_items:
            event = self.outbox[0]  # Peek first
            
            # Remove meta fields
            event.pop("_outbox_reason", None)
            event.pop("_outbox_ts", None)
            
            # Try to send (no retries here, will re-enqueue if fails)
            success, _, _ = self._post_event_internal(event, retries=1)
            
            if success:
                self.outbox.pop(0)  # Remove from queue
                sent_count += 1
            else:
                # Failed to send, stop flushing
                self.log("Outbox flush stopped due to failure")
                # Re-add meta fields
                event["_outbox_reason"] = "retry_failed"
                event["_outbox_ts"] = time.monotonic()
                break
        
        if sent_count > 0:
            self.log(f"Outbox flushed: {sent_count} events sent, {len(self.outbox)} remaining")
        
        return sent_count
    
    def load_local_config(self):
        """Load previously saved wifi_config.json"""
        try:
            with open("wifi_config.json", "r") as f:
                config = json.load(f)
            self.log(f"Loaded local config: {config}")
            self.server_config = config
            return config
        except Exception as e:
            self.log(f"Failed to load local config: {e}")
            return None
    
    def _post_event_internal(self, event_data, retries=2):
        """Internal post_event implementation without outbox logic"""
        if not self.server_configured:
            return False, None, "server_url_not_configured"
            
        # Check backoff
        if self._should_backoff():
            return False, None, "backoff_active"
            
        if not self.ensure_connection():
            self.log("Cannot post event: no WiFi connection")
            return False, None, "no_wifi"
        
        url = "{}{}".format(self.server_url, self.events_endpoint)
        
        # Ensure device and timestamp  are in payload
        event_data["device"] = self.device
        
        # Add timestamp if not present
        if "ts" not in event_data:
            event_data["ts"] = self.now_iso8601()
        
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        self.log("Posting event type={} to {}".format(event_data.get('event_type'), url))
        
        for attempt in range(retries):
            try:
                response = self.requests.post(
                    url,
                    headers=headers,
                    json=event_data,
                    timeout=10
                )
                
                status = response.status_code
                
                if status in (200, 201):
                    self.log("✓ Event posted successfully: HTTP {}".format(status))
                    response.close()
                    self._handle_connection_success()
                    return True, status, "ok"
                elif 400 <= status < 500:
                    # Client error - might be payload serialization issue
                    try:
                        response_text = response.text[:200]
                    except:
                        response_text = "(unable to read response)"
                    
                    self.log("✗ Event post failed: HTTP {}".format(status))
                    self.log("  Response snippet: {}".format(response_text))
                    
                    # Check if it's a serialization error and we have a payload dict
                    if "payload" in event_data and isinstance(event_data["payload"], dict):
                        if "serial" in response_text.lower() or "json" in response_text.lower():
                            self.log("  Retrying with JSON-serialized payload...")
                            event_data_copy = event_data.copy()
                            event_data_copy["payload"] = json.dumps(event_data["payload"])
                            
                            response.close()
                            
                            response2 = self.requests.post(
                                url, headers=headers, json=event_data_copy, timeout=10
                            )
                            
                            s2 = response2.status_code
                            if s2 in (200, 201):
                                self.log("✓ Event posted with serialized payload: HTTP {}".format(s2))
                                response2.close()
                                return True, s2, "ok_retry"
                            else:
                                self.log("✗ Retry also failed: HTTP {}".format(s2))
                                response2.close()
                                return False, s2, "retry_failed"
                    
                    response.close()
                    return False, status, response_text
                else:
                    self.log("✗ Event post failed: HTTP {}".format(status))
                    info = ""
                    try:
                        info = response.text[:200]
                        self.log("  Response: {}".format(info))
                    except:
                        pass
                    response.close()
                    return False, status, info
            except Exception as e:
                err_msg = str(e)
                self.log("Event post exception (attempt {}/{}): {}".format(attempt+1, retries, err_msg))
                if attempt == retries - 1:
                    return False, None, err_msg
                time.sleep(1)
        
        self._handle_connection_failure()
        return False, None, "exhausted_retries"
    
    def post_event(self, event_data, retries=2):
        """POST event with outbox support
        
        Returns: (success:bool, status_code:int|None, info:str)
        """
        # Try to send
        success, status, info = self._post_event_internal(event_data, retries=retries)
        
        if success:
            # On success, try to flush some outbox items
            if self.outbox:
                try:
                    self.flush_outbox(max_items=5)
                except Exception as e:
                    self.log(f"Outbox flush error: {e}")
        else:
            # On failure, enqueue to outbox
            self.enqueue_event(event_data, reason=info or "post_failed")
        
        return success, status, info
    
    def apply_server_wifi_config(self):
        """
        If server config contains wifi credentials, reconnect using them.
        Returns True if reconnected successfully.
        """
        if not self.server_config:
            return False
        
        wifi_cfg = self.server_config.get("wifi", {})
        ssid = wifi_cfg.get("ssid")
        password = wifi_cfg.get("password")
        
        if ssid and password:
            self.log(f"Applying server WiFi config: {ssid}")
            return self.connect_wifi(ssid=ssid, password=password)
        
        return False
