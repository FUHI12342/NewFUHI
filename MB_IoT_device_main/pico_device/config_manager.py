# Configuration Management for Pico 2 W WiFi Hardening
# Handles priority-based configuration source selection and validation

import json
import re

# Configuration source constants (replacing Enum)
CONFIG_SOURCE_DJANGO = "django"
CONFIG_SOURCE_LOCAL_FILE = "local_file"
CONFIG_SOURCE_SECRETS = "secrets"

class ConfigSourceInterface:
    """Base class for configuration sources (duck typing - no ABC needed for CircuitPython)"""
    
    def load_config(self, device_id):
        """Loads configuration from source"""
        raise NotImplementedError("Subclass must implement load_config")
    
    def is_available(self):
        """Checks if configuration source is accessible"""
        raise NotImplementedError("Subclass must implement is_available")
    
    def get_priority(self):
        """Returns source priority (lower = higher priority)"""
        raise NotImplementedError("Subclass must implement get_priority")
    
    def get_source_name(self):
        """Returns human-readable source name"""
        raise NotImplementedError("Subclass must implement get_source_name")

class DjangoConfigSource(ConfigSourceInterface):
    """Configuration source from Django API"""
    
    def __init__(self, api_client=None):
        self.api_client = api_client
    
    def load_config(self, device_id):
        """Load configuration from Django API"""
        if not self.api_client:
            return None
            
        try:
            # Placeholder for Django API call
            # In real implementation: response = self.api_client.get_device_config(device_id)
            return None
        except Exception:
            return None
    
    def is_available(self):
        """Check if Django API is accessible"""
        return self.api_client is not None
    
    def get_priority(self):
        return 1  # Highest priority
    
    def get_source_name(self):
        return "Django API"

class LocalFileConfigSource(ConfigSourceInterface):
    """Configuration source from wifi_config.json"""
    
    def __init__(self, file_path="wifi_config.json"):
        self.file_path = file_path
        from .file_utils import FileUtils
        self.file_utils = FileUtils()
    
    def load_config(self, device_id):
        """Load configuration from local JSON file"""
        data = self.file_utils.load_json_safe(self.file_path)
        
        if data is None:
            return None
            
        try:
            return DeviceConfig(
                wifi_ssid=data.get('wifi_ssid', ''),
                wifi_password=data.get('wifi_password', ''),
                server_url=data.get('server_url', ''),
                api_key=data.get('api_key', ''),
                device_name=data.get('device_name', ''),
                device_id=device_id,
                source=CONFIG_SOURCE_LOCAL_FILE
            )
        except Exception as e:
            print(f"[CONFIG] Error creating DeviceConfig from local file: {str(e)}")
            return None
    
    def is_available(self):
        """Check if local config file exists and is readable"""
        return self.file_utils.validate_json_file(self.file_path)
    
    def get_priority(self):
        return 2  # Medium priority
    
    def get_source_name(self):
        return f"Local file ({self.file_path})"

class SecretsConfigSource(ConfigSourceInterface):
    """Configuration source from secrets.py"""
    
    def load_config(self, device_id):
        """Load configuration from secrets.py (dict or attribute format)"""
        try:
            # First, try to import secrets module
            try:
                import secrets as secrets_mod
            except Exception:
                return None
            
            # Strategy 1: Check for dict format (secrets = {...})
            secrets_data = None
            if hasattr(secrets_mod, 'secrets') and isinstance(getattr(secrets_mod, 'secrets'), dict):
                secrets_data = secrets_mod.secrets
                
                # Support multiple key formats
                wifi_ssid = secrets_data.get('ssid') or secrets_data.get('wifi_ssid', '')
                wifi_password = secrets_data.get('password') or secrets_data.get('wifi_password', '')
                server_url = secrets_data.get('server_base') or secrets_data.get('server_url', '')
                api_key = secrets_data.get('api_key', '')
                device_name = secrets_data.get('device') or secrets_data.get('device_name', device_id)
                
            # Strategy 2: Attribute format (WIFI_SSID, WIFI_PASSWORD, etc.)
            else:
                wifi_ssid = getattr(secrets_mod, 'WIFI_SSID', getattr(secrets_mod, 'ssid', ''))
                wifi_password = getattr(secrets_mod, 'WIFI_PASSWORD', getattr(secrets_mod, 'password', ''))
                server_url = getattr(secrets_mod, 'SERVER_URL', getattr(secrets_mod, 'server_base', ''))
                api_key = getattr(secrets_mod, 'API_KEY', getattr(secrets_mod, 'api_key', ''))
                device_name = getattr(secrets_mod, 'DEVICE_NAME', getattr(secrets_mod, 'device', device_id))
            
            # Return None if no valid config found
            if not wifi_ssid or not wifi_password:
                return None
            
            return DeviceConfig(
                wifi_ssid=wifi_ssid,
                wifi_password=wifi_password,
                server_url=server_url,
                api_key=api_key,
                device_name=device_name,
                device_id=device_id,
                source=CONFIG_SOURCE_SECRETS
            )
        except Exception:
            return None
    
    def is_available(self):
        """Check if secrets.py is importable"""
        try:
            import secrets as secrets_mod
            # Check if it has either dict format or attributes
            if hasattr(secrets_mod, 'secrets'):
                return isinstance(getattr(secrets_mod, 'secrets'), dict) and bool(secrets_mod.secrets)
            # Check for attribute format
            return (hasattr(secrets_mod, 'WIFI_SSID') or hasattr(secrets_mod, 'ssid') or
                    hasattr(secrets_mod, 'wifi_ssid'))
        except Exception:
            return False
    
    def get_priority(self):
        return 3  # Lowest priority
    
    def get_source_name(self):
        return "secrets.py"

class DeviceConfig:
    """Device configuration with validation and dummy detection"""
    
    def __init__(self, wifi_ssid, wifi_password, server_url, 
                 api_key, device_name, device_id, source):
        self.wifi_ssid = wifi_ssid
        self.wifi_password = wifi_password
        self.server_url = server_url
        self.api_key = api_key
        self.device_name = device_name
        self.device_id = device_id
        self.source = source
    
    def is_valid(self):
        """Validates configuration completeness and format"""
        return all([
            self.wifi_ssid and len(self.wifi_ssid.strip()) >= 3 and not self._is_dummy_value(self.wifi_ssid),
            self.wifi_password and len(self.wifi_password.strip()) >= 3 and not self._is_dummy_value(self.wifi_password),
            self.server_url and self._is_valid_url(self.server_url),
            self.api_key and len(self.api_key.strip()) >= 3 and not self._is_dummy_value(self.api_key)
        ])
    
    def _is_dummy_value(self, value):
        """Detects common test/placeholder patterns"""
        if not value:
            return True
            
        dummy_patterns = [
            'test_', 'sample_', 'example_', 'dummy_',
            'YOUR_', '_HERE', 'REPLACE_ME', 'TODO',
            'your-server.com', 'localhost', 'example.com',
            'test.com', 'sample.com', 'placeholder',
            'changeme', 'default', 'temp_'
        ]
        value_upper = value.upper()
        return any(pattern.upper() in value_upper for pattern in dummy_patterns)
    
    def _is_valid_url(self, url):
        """Basic URL validation (CircuitPython-safe, no urllib)"""
        if not url:
            return False
        
        # Check basic URL format
        if not url.startswith(('http://', 'https://')):
            return False
            
        # Check for dummy values
        if self._is_dummy_value(url):
            return False
            
        # Simple validation - must have a dot (domain)
        return '.' in url and len(url) > 10

class ConfigurationManager:
    """Central configuration manager with priority-based source selection"""
    
    def __init__(self, device_id, failure_threshold=3, config_sources=None):
        self.device_id = device_id
        self.failure_threshold = failure_threshold
        
        # Use provided sources or create default ones
        if config_sources:
            self.config_sources = sorted(config_sources, key=lambda x: x.get_priority())
        else:
            self.config_sources = [
                DjangoConfigSource(),
                LocalFileConfigSource(),
                SecretsConfigSource()
            ]
    
    def get_valid_config(self):
        """Returns first valid configuration from priority-ordered sources"""
        for source in self.config_sources:
            try:
                if not source.is_available():
                    self.log_config_decision(source.get_source_name(), "Source not available")
                    continue
                    
                config = source.load_config(self.device_id)
                if config and config.is_valid():
                    self.log_config_decision(source.get_source_name(), "Selected as valid configuration")
                    return config
                else:
                    reason = "Invalid or contains dummy data" if config else "No configuration returned"
                    self.log_config_decision(source.get_source_name(), f"Rejected: {reason}")
            except Exception as e:
                self.log_config_decision(source.get_source_name(), f"Error loading: {str(e)}")
        
        self.log_config_decision("ALL_SOURCES", "No valid configuration found")
        return None
    
    def log_config_decision(self, source, reason):
        """Logs configuration source selection and rejection reasons (safe import)"""
        try:
            from .logging_utils import log_config_decision as _lcd
            success = "Selected" in reason or "valid" in reason.lower()
            _lcd(source, reason, success)
        except Exception:
            # Fallback if logging_utils not available
            print(f"[CONFIG] {source} - {reason}")