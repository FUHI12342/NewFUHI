# Tests for Configuration Manager
import pytest
import json
import os
from unittest.mock import patch, mock_open
from pico_device.config_manager import ConfigurationManager, DeviceConfig, ConfigSource

class TestDeviceConfig:
    """Test DeviceConfig validation and dummy detection"""
    
    def test_valid_config(self):
        config = DeviceConfig(
            wifi_ssid="MyNetwork",
            wifi_password="SecurePassword123",
            server_url="https://myserver.com/api",
            api_key="real_api_key_12345",
            device_name="Device1",
            device_id="PICO001",
            source="test"
        )
        assert config.is_valid()
    
    def test_dummy_ssid_detection(self):
        config = DeviceConfig(
            wifi_ssid="test_ssid",
            wifi_password="SecurePassword123",
            server_url="https://myserver.com/api",
            api_key="real_api_key_12345",
            device_name="Device1",
            device_id="PICO001",
            source="test"
        )
        assert not config.is_valid()
    
    def test_dummy_password_detection(self):
        config = DeviceConfig(
            wifi_ssid="MyNetwork",
            wifi_password="test_password",
            server_url="https://myserver.com/api",
            api_key="real_api_key_12345",
            device_name="Device1",
            device_id="PICO001",
            source="test"
        )
        assert not config.is_valid()
    
    def test_dummy_api_key_detection(self):
        config = DeviceConfig(
            wifi_ssid="MyNetwork",
            wifi_password="SecurePassword123",
            server_url="https://myserver.com/api",
            api_key="YOUR_API_KEY_HERE",
            device_name="Device1",
            device_id="PICO001",
            source="test"
        )
        assert not config.is_valid()
    
    def test_dummy_server_url_detection(self):
        config = DeviceConfig(
            wifi_ssid="MyNetwork",
            wifi_password="SecurePassword123",
            server_url="https://your-server.com",
            api_key="real_api_key_12345",
            device_name="Device1",
            device_id="PICO001",
            source="test"
        )
        assert not config.is_valid()

class TestConfigurationManager:
    """Test Configuration Manager priority and fallback logic"""
    
    def test_initialization(self):
        manager = ConfigurationManager("PICO001")
        assert manager.device_id == "PICO001"
        assert manager.failure_threshold == 3
        assert len(manager.config_sources) == 3
    
    @patch('builtins.open', mock_open(read_data='{"wifi_ssid": "TestNetwork", "wifi_password": "TestPass123", "server_url": "https://test.com", "api_key": "test_key_123", "device_name": "TestDevice"}'))
    def test_load_local_file_config(self):
        manager = ConfigurationManager("PICO001")
        config = manager._load_local_file_config()
        
        assert config is not None
        assert config.wifi_ssid == "TestNetwork"
        assert config.source == "local_file"
    
    def test_load_local_file_config_missing(self):
        manager = ConfigurationManager("PICO001")
        with patch('builtins.open', side_effect=FileNotFoundError):
            config = manager._load_local_file_config()
            assert config is None
    
    @patch('builtins.open', mock_open(read_data='invalid json'))
    def test_load_local_file_config_invalid_json(self):
        manager = ConfigurationManager("PICO001")
        config = manager._load_local_file_config()
        assert config is None