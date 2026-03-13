# Configuration Management for Pico 2 W WiFi Hardening
# Handles priority-based configuration source selection and validation

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum
import json
import re
from abc import ABC, abstractmethod

class ConfigSource(Enum):
    DJANGO = "django"
    LOCAL_FILE = "local_file"
    SECRETS = "secrets"

class ConfigSourceInterface(ABC):
    """Abstract interface for configuration sources"""
    
    @abstractmethod
    def load_config(self, device_id: str) -> Optional['DeviceConfig']:
        """Loads configuration from source"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Checks if configuration source is accessible"""
        pass
    
    @abstractmethod
    def get_priority(self) -> int:
        """Returns source priority (lower = higher priority)"""
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Returns human-readable source name"""
        pass

class DjangoConfigSource(ConfigSourceInterface):
    """Configuration source from Django API"""
    
    def __init__(self, api_client=None):
        self.api_client = api_client
    
    def load_config(self, device_id: str) -> Optional['DeviceConfig']:
        """Load configuration from Django API"""
        if not self.api_client:
            return None
            
        try:
            # Placeholder for Django API call
            # In real implementation: response = self.api_client.get_device_config(device_id)
            return None
        except Exception:
            return None
    
    def is_available(self) -> bool:
        """Check if Django API is accessible"""
        return self.api_client is not None
    
    def get_priority(self) -> int:
        return 1  # Highest priority
    
    def get_source_name(self) -> str:
        return "Django API"

class LocalFileConfigSource(ConfigSourceInterface):
    """Configuration source from wifi_config.json"""
    
    def __init__(self, file_path: str = "wifi_config.json"):
        self.file_path = file_path
        from .file_utils import FileUtils
        self.file_utils = FileUtils()
    
    def load_config(self, device_id: str) -> Optional['DeviceConfig']:
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
                source=ConfigSource.LOCAL_FILE.value
            )
        except Exception as e:
            print(f"[CONFIG] Error creating DeviceConfig from local file: {str(e)}")
            return None
    
    def is_available(self) -> bool:
        """Check if local config file exists and is readable"""
        return self.file_utils.validate_json_file(self.file_path)
    
    def get_priority(self) -> int:
        return 2  # Medium priority
    
    def get_source_name(self) -> str:
        return f"Local file ({self.file_path})"

class SecretsConfigSource(ConfigSourceInterface):
    """Configuration source from secrets.py"""
    
    def load_config(self, device_id: str) -> Optional['DeviceConfig']:
        """Load configuration from secrets.py"""
        try:
            import secrets
            return DeviceConfig(
                wifi_ssid=getattr(secrets, 'WIFI_SSID', ''),
                wifi_password=getattr(secrets, 'WIFI_PASSWORD', ''),
                server_url=getattr(secrets, 'SERVER_URL', ''),
                api_key=getattr(secrets, 'API_KEY', ''),
                device_name=getattr(secrets, 'DEVICE_NAME', ''),
                device_id=device_id,
                source=ConfigSource.SECRETS.value
            )
        except ImportError:
            return None
    
    def is_available(self) -> bool:
        """Check if secrets.py is importable"""
        try:
            import secrets
            return True
        except ImportError:
            return False
    
    def get_priority(self) -> int:
        return 3  # Lowest priority
    
    def get_source_name(self) -> str:
        return "secrets.py"

@dataclass
class DeviceConfig:
    """Device configuration with validation and dummy detection"""
    wifi_ssid: str
    wifi_password: str
    server_url: str
    api_key: str
    device_name: str
    device_id: str
    source: str
    
    def is_valid(self) -> bool:
        """Validates configuration completeness and format"""
        return all([
            self.wifi_ssid and len(self.wifi_ssid.strip()) >= 3 and not self._is_dummy_value(self.wifi_ssid),
            self.wifi_password and len(self.wifi_password.strip()) >= 3 and not self._is_dummy_value(self.wifi_password),
            self.server_url and self._is_valid_url(self.server_url),
            self.api_key and len(self.api_key.strip()) >= 3 and not self._is_dummy_value(self.api_key)
        ])
    
    def _is_dummy_value(self, value: str) -> bool:
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
    
    def _is_valid_url(self, url: str) -> bool:
        """Basic URL validation"""
        if not url:
            return False
        
        # Check basic URL format
        if not url.startswith(('http://', 'https://')):
            return False
            
        # Check for dummy values
        if self._is_dummy_value(url):
            return False
            
        # Additional validation - must have domain
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return bool(parsed.netloc)
        except:
            # Fallback for CircuitPython without urllib
            return '.' in url and len(url) > 10

class ConfigurationManager:
    """Central configuration manager with priority-based source selection"""
    
    def __init__(self, device_id: str, failure_threshold: int = 3, config_sources: List[ConfigSourceInterface] = None):
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
    
    def get_valid_config(self) -> Optional[DeviceConfig]:
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
    
    def _load_config_from_source(self, source: ConfigSource) -> Optional[DeviceConfig]:
        """Load configuration from specific source - DEPRECATED, use ConfigSourceInterface"""
        if source == ConfigSource.DJANGO:
            return self._load_django_config()
        elif source == ConfigSource.LOCAL_FILE:
            return self._load_local_file_config()
        elif source == ConfigSource.SECRETS:
            return self._load_secrets_config()
        return None
    
    def _load_django_config(self) -> Optional[DeviceConfig]:
        """Load configuration from Django API - DEPRECATED"""
        # Placeholder - will be implemented in Django integration task
        return None
    
    def _load_local_file_config(self) -> Optional[DeviceConfig]:
        """Load configuration from wifi_config.json - DEPRECATED"""
        try:
            with open('wifi_config.json', 'r') as f:
                data = json.load(f)
            
            return DeviceConfig(
                wifi_ssid=data.get('wifi_ssid', ''),
                wifi_password=data.get('wifi_password', ''),
                server_url=data.get('server_url', ''),
                api_key=data.get('api_key', ''),
                device_name=data.get('device_name', ''),
                device_id=self.device_id,
                source=ConfigSource.LOCAL_FILE.value
            )
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return None
    
    def _load_secrets_config(self) -> Optional[DeviceConfig]:
        """Load configuration from secrets.py - DEPRECATED"""
        try:
            import secrets
            return DeviceConfig(
                wifi_ssid=getattr(secrets, 'WIFI_SSID', ''),
                wifi_password=getattr(secrets, 'WIFI_PASSWORD', ''),
                server_url=getattr(secrets, 'SERVER_URL', ''),
                api_key=getattr(secrets, 'API_KEY', ''),
                device_name=getattr(secrets, 'DEVICE_NAME', ''),
                device_id=self.device_id,
                source=ConfigSource.SECRETS.value
            )
        except ImportError:
            return None
    
    def log_config_decision(self, source: str, reason: str) -> None:
        """Logs configuration source selection and rejection reasons"""
        from .logging_utils import log_config_decision
        success = "Selected" in reason or "valid" in reason.lower()
        log_config_decision(source, reason, success)