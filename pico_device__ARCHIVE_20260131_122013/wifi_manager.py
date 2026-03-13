# WiFi Management for Pico 2 W with Setup AP fallback
# Handles connection attempts, failure tracking, and Setup AP activation

from enum import Enum
from dataclasses import dataclass
from typing import Optional
import time

class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SETUP_MODE = "setup_mode"
    FAILED = "failed"

@dataclass
class WiFiStatus:
    state: ConnectionState
    failure_count: int
    last_attempt: float
    current_config: Optional[object]
    setup_reason: Optional[str]

class WiFiManager:
    """Manages WiFi connections with failure tracking and Setup AP activation"""
    
    def __init__(self, config_manager, failure_threshold: int = 3):
        self.config_manager = config_manager
        self.failure_threshold = failure_threshold
        self.failure_count = 0
        self.connection_state = ConnectionState.DISCONNECTED
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
        self.connection_state = ConnectionState.CONNECTING
        self._log_connection_attempt("CONNECTING", None, f"Attempting connection to {config.wifi_ssid}")
        
        try:
            # Attempt WiFi connection
            success = self._attempt_wifi_connection(config)
            
            if success:
                self.connection_state = ConnectionState.CONNECTED
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
        """Placeholder for actual WiFi connection attempt"""
        # In real CircuitPython implementation:
        # import wifi
        # try:
        #     wifi.radio.connect(config.wifi_ssid, config.wifi_password)
        #     return wifi.radio.connected
        # except Exception as e:
        #     print(f"[WIFI] Connection failed: {e}")
        #     return False
        
        # For testing, simulate connection based on config validity
        return config.is_valid() and not config._is_dummy_value(config.wifi_ssid)
    
    def _handle_connection_failure(self, reason: str):
        """Handle WiFi connection failure"""
        self.failure_count += 1
        self.connection_state = ConnectionState.FAILED
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
        from .logging_utils import log_setup_activation
        log_setup_activation(reason, f"PICO-SETUP-{getattr(self, 'device_id', 'UNKNOWN')}", {'details': details})
    
    def _user_triggered_setup(self) -> bool:
        """Check if user has triggered setup mode manually"""
        # Placeholder for user trigger detection
        # In real implementation, this could check:
        # - Button press patterns (e.g., hold button for 5+ seconds)
        # - Reset sequence detection (e.g., 3 rapid resets)
        # - Special file presence (e.g., "force_setup.txt")
        # - GPIO pin states
        # - Serial command input
        
        # Example implementations:
        # 1. Button press detection:
        # if hasattr(self, 'button_pin'):
        #     return self.button_pin.value and time.time() - self.button_press_start > 5
        
        # 2. File-based trigger:
        # try:
        #     with open('force_setup.txt', 'r') as f:
        #         return f.read().strip() == 'FORCE_SETUP'
        # except FileNotFoundError:
        #     pass
        
        # 3. Reset sequence detection:
        # if hasattr(self, 'reset_counter'):
        #     return self.reset_counter >= 3
        
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
        return (self.connection_state == ConnectionState.CONNECTED and 
                self.current_config is not None)
    
    def _log_connection_attempt(self, event: str, success: Optional[bool], details: str):
        """Log WiFi connection attempts with timestamp"""
        from .logging_utils import log_wifi_event
        
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
        
        # Use centralized logging
        if success is not None:
            log_wifi_event(event, details, success, {'failure_count': self.failure_count})
        else:
            from .logging_utils import get_logger, LogLevel, LogCategory
            logger = get_logger()
            logger.log(LogLevel.INFO, LogCategory.WIFI, f"{event}: {details}", {'failure_count': self.failure_count})
    
    def get_connection_history(self) -> list:
        """Returns recent connection attempt history"""
        return self.connection_history.copy()
    
    def force_setup_mode(self, reason: str = "USER_REQUESTED"):
        """Force entry into setup mode with custom reason"""
        self.setup_reason = reason
        self.connection_state = ConnectionState.SETUP_MODE
        print(f"[WIFI] Forced setup mode: {reason}")
    
    def is_connected(self) -> bool:
        """Check if currently connected to WiFi"""
        return self.connection_state == ConnectionState.CONNECTED
    
    def get_current_ssid(self) -> Optional[str]:
        """Get SSID of current connection"""
        if self.current_config and self.is_connected():
            return self.current_config.wifi_ssid
        return None