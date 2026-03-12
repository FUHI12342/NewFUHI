# WiFi Management for Pico 2 W with Setup AP fallback
# Handles connection attempts, failure tracking, and Setup AP activation

import time

# Connection state constants (replacing Enum)
CONNECTION_STATE_DISCONNECTED = "disconnected"
CONNECTION_STATE_CONNECTING = "connecting"
CONNECTION_STATE_CONNECTED = "connected"
CONNECTION_STATE_SETUP_MODE = "setup_mode"
CONNECTION_STATE_FAILED = "failed"

class WiFiStatus:
    """WiFi connection status information"""
    
    def __init__(self, state, failure_count, 
                 last_attempt, current_config, 
                 setup_reason):
        self.state = state
        self.failure_count = failure_count
        self.last_attempt = last_attempt
        self.current_config = current_config
        self.setup_reason = setup_reason

class WiFiManager:
    """Manages WiFi connections with failure tracking and Setup AP activation"""
    
    def __init__(self, config_manager, failure_threshold: int = 3):
        self.config_manager = config_manager
        self.failure_threshold = failure_threshold
        self.failure_count = 0
        self.connection_state = CONNECTION_STATE_DISCONNECTED
        self.current_config = None
        self.setup_reason = None
        self.last_attempt_time = 0
        self.connection_history = []  # Track connection attempts
    
    def connect_wifi(self) -> bool:
        """Attempts WiFi connection using valid configuration"""
        self.last_attempt_time = time.time()
        config = self.config_manager.get_valid_config()
        
        if not config:
            self.setup_reason = "NO_VALID_CONFIG"
            self._log_connection_attempt("NO_CONFIG", False, "No valid configuration available")
            return False
        
        self.current_config = config
        self.connection_state = CONNECTION_STATE_CONNECTING
        self._log_connection_attempt("CONNECTING", None, f"Attempting connection to {config.wifi_ssid}")
        
        try:
            # Attempt WiFi connection
            success = self._attempt_wifi_connection(config)
            
            if success:
                self.connection_state = CONNECTION_STATE_CONNECTED
                self.reset_failure_count()
                self._log_connection_attempt("SUCCESS", True, f"Connected to {config.wifi_ssid}")
                return True
            else:
                self._handle_connection_failure("CONNECTION_FAILED")
                return False
                
        except Exception as e:
            self._handle_connection_failure(f"EXCEPTION: {str(e)}")
            return False
    
    def _attempt_wifi_connection(self, config) -> bool:
        """Actual WiFi connection attempt for CircuitPython"""
        try:
            import wifi
            
            # Stop any existing connections
            if wifi.radio.connected:
                wifi.radio.stop_station()
            
            # Attempt connection
            wifi.radio.connect(config.wifi_ssid, config.wifi_password)
            
            # Check if connected
            return wifi.radio.connected
            
        except Exception as e:
            print(f"[WIFI] Connection failed: {e}")
            return False
    
    def _handle_connection_failure(self, reason: str):
        """Handle WiFi connection failure"""
        self.failure_count += 1
        self.connection_state = CONNECTION_STATE_FAILED
        self._log_connection_attempt("FAILED", False, f"Connection failed ({self.failure_count}/{self.failure_threshold}): {reason}")
        
        if self.failure_count >= self.failure_threshold:
            self.setup_reason = "WIFI_RETRY_EXCEEDED"
    
    def should_enter_setup_mode(self) -> bool:
        """Determines if Setup AP should be activated"""
        # Priority 1: Check for WiFi failure threshold exceeded
        if self.failure_count >= self.failure_threshold:
            self.setup_reason = "WIFI_RETRY_EXCEEDED"
            self._log_setup_decision("WIFI_RETRY_EXCEEDED", f"Failed {self.failure_count} times (threshold: {self.failure_threshold})")
            return True
        
        # Priority 2: Check for no valid configuration
        if not self.config_manager.get_valid_config():
            self.setup_reason = "NO_VALID_CONFIG"
            self._log_setup_decision("NO_VALID_CONFIG", "No valid WiFi configuration available from any source")
            return True
        
        # Priority 3: Check for user-triggered setup mode
        if self._user_triggered_setup():
            self.setup_reason = "USER_FORCED_SETUP"
            self._log_setup_decision("USER_FORCED_SETUP", "User manually triggered setup mode")
            return True
        
        # Priority 4: Check for persistent connection issues (advanced)
        if self._has_persistent_connection_issues():
            self.setup_reason = "PERSISTENT_ISSUES"
            self._log_setup_decision("PERSISTENT_ISSUES", "Persistent connection issues detected")
            return True
        
        # No setup mode triggers detected
        return False
    
    def _has_persistent_connection_issues(self) -> bool:
        """Check for patterns indicating persistent connection problems"""
        # Check connection history for patterns
        if len(self.connection_history) < 5:
            return False
        
        # Look for repeated failures in recent history
        recent_failures = 0
        for entry in self.connection_history[-5:]:
            if entry.get('success') is False:
                recent_failures += 1
        
        # If more than 60% of recent attempts failed, consider it persistent
        return recent_failures >= 3
    
    def _log_setup_decision(self, reason: str, details: str):
        """Log Setup AP activation decisions"""
        # Safe logging
        try:
            from .logging_utils import log_setup_activation
            device_id_str = self.config_manager.device_id if self.config_manager and hasattr(self.config_manager, 'device_id') else "UNKNOWN"
            log_setup_activation(reason, f"PICO-SETUP-{device_id_str}", {'details': details})
        except Exception:
            # Fallback to print if logging not available
            print(f"[WIFI] Setup decision: {reason} - {details}")
    
    def _user_triggered_setup(self) -> bool:
        """Check if user has triggered setup mode manually"""
        # Check for setup trigger file
        try:
            with open('force_setup.txt', 'r') as f:
                content = f.read().strip()
                if content == 'FORCE_SETUP':
                    # Remove trigger file
                    import os
                    os.remove('force_setup.txt')
                    return True
        except OSError:
            pass  # File doesn't exist
        
        return False
    
    def reset_failure_count(self) -> None:
        """Resets failure counter on successful connection"""
        if self.failure_count > 0:
            print(f"[WIFI] Resetting failure count from {self.failure_count} to 0")
        self.failure_count = 0
        self.setup_reason = None
    
    def get_status(self) -> WiFiStatus:
        """Returns current WiFi status"""
        return WiFiStatus(
            state=self.connection_state,
            failure_count=self.failure_count,
            last_attempt=self.last_attempt_time,
            current_config=self.current_config,
            setup_reason=self.setup_reason
        )
    
    def is_server_failure_only(self) -> bool:
        """Check if WiFi is connected but server connection failed"""
        # This separates WiFi failures from server connectivity issues
        return (self.connection_state == CONNECTION_STATE_CONNECTED and 
                self.current_config is not None)
    
    def _log_connection_attempt(self, event, success, details):
        """Log WiFi connection attempts with timestamp (safe logging)"""
        timestamp = time.time()
        log_entry = {
            'timestamp': timestamp,
            'event': event,
            'success': success,
            'details': details,
            'failure_count': self.failure_count
        }
        
        self.connection_history.append(log_entry)
        
        # Keep only last 10 entries to prevent memory issues
        if len(self.connection_history) > 10:
            self.connection_history.pop(0)
        
        # Use safe logging with fallback
        try:
            from .logging_utils import log_wifi_event
            log_wifi_event(event, details, success if success is not None else True, 
                          {'failure_count': self.failure_count})
        except Exception:
            # Fallback to print if logging not available
            success_str = "SUCCESS" if success else "FAILED" if success is not None else "INFO"
            print(f"[WIFI] {event} ({success_str}): {details}")
    
    def get_connection_history(self) -> list:
        """Returns recent connection attempt history"""
        return self.connection_history.copy()
    
    def force_setup_mode(self, reason: str = "USER_REQUESTED"):
        """Force entry into setup mode with custom reason"""
        self.setup_reason = reason
        self.connection_state = CONNECTION_STATE_SETUP_MODE
        print(f"[WIFI] Forced setup mode: {reason}")
    
    def is_connected(self) -> bool:
        """Check if currently connected to WiFi"""
        try:
            import wifi
            return wifi.radio.connected
        except:
            return self.connection_state == CONNECTION_STATE_CONNECTED
    
    def get_current_ssid(self):
        """Get SSID of current connection"""
        if self.current_config and self.is_connected():
            return self.current_config.wifi_ssid
        return None