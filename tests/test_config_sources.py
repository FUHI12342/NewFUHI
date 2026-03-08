# Tests for Configuration Sources
import pytest
import json
import os
from unittest.mock import patch, mock_open, Mock
from pico_device.config_manager import (
    ConfigurationManager, DeviceConfig, 
    DjangoConfigSource, LocalFileConfigSource, SecretsConfigSource
)

class TestDjangoConfigSource:
    """Test Django configuration source"""
    
    def test_initialization(self):
        source = DjangoConfigSource()
        assert source.get_priority() == 1
        assert source.get_source_name() == "Django API"
        assert not source.is_available()
    
    def test_with_api_client(self):
        api_client = Mock()
        source = DjangoConfigSource(api_client)
        assert source.is_available()
    
    def test_load_config_no_client(self):
        source = DjangoConfigSource()
        config = source.load_config("PICO001")
        assert config is None

class TestLocalFileConfigSource:
    """Test local file configuration source"""
    
    def test_initialization(self):
        source = LocalFileConfigSource()
        assert source.get_priority() == 2
        assert source.get_source_name() == "Local file (wifi_config.json)"
    
    @patch('pico_device.file_utils.FileUtils.load_json_safe')
    def test_load_valid_config(self, mock_load_json):
        mock_load_json.return_value = {
            "wifi_ssid": "TestNetwork", 
            "wifi_password": "TestPass123", 
            "server_url": "https://test.com", 
            "api_key": "test_key_123", 
            "device_name": "TestDevice"
        }
        
        source = LocalFileConfigSource()
        config = source.load_config("PICO001")
        
        assert config is not None
        assert config.wifi_ssid == "TestNetwork"
        assert config.device_id == "PICO001"
        assert config.source == "local_file"
    
    def test_load_config_file_not_found(self):
        source = LocalFileConfigSource()
        with patch('builtins.open', side_effect=FileNotFoundError):
            config = source.load_config("PICO001")
            assert config is None
            assert not source.is_available()
    
    @patch('builtins.open', mock_open(read_data='invalid json'))
    def test_load_config_invalid_json(self):
        source = LocalFileConfigSource()
        config = source.load_config("PICO001")
        assert config is None
        assert not source.is_available()
    
    @patch('builtins.open', mock_open(read_data='{"wifi_ssid": "TestNetwork"}'))
    def test_is_available_valid_file(self):
        source = LocalFileConfigSource()
        assert source.is_available()

class TestSecretsConfigSource:
    """Test secrets.py configuration source"""
    
    def test_initialization(self):
        source = SecretsConfigSource()
        assert source.get_priority() == 3
        assert source.get_source_name() == "secrets.py"
    
    def test_load_config_no_secrets_module(self):
        source = SecretsConfigSource()
        with patch('builtins.__import__', side_effect=ImportError):
            config = source.load_config("PICO001")
            assert config is None
            assert not source.is_available()
    
    def test_load_config_with_secrets(self):
        # Mock secrets module
        mock_secrets = Mock()
        mock_secrets.WIFI_SSID = "SecretNetwork"
        mock_secrets.WIFI_PASSWORD = "SecretPass123"
        mock_secrets.SERVER_URL = "https://secret.com"
        mock_secrets.API_KEY = "secret_key_123"
        mock_secrets.DEVICE_NAME = "SecretDevice"
        
        source = SecretsConfigSource()
        with patch.dict('sys.modules', {'secrets': mock_secrets}):
            config = source.load_config("PICO001")
            
            assert config is not None
            assert config.wifi_ssid == "SecretNetwork"
            assert config.device_id == "PICO001"
            assert config.source == "secrets"

class TestConfigurationManagerWithSources:
    """Test ConfigurationManager with new source interface"""
    
    def test_initialization_with_custom_sources(self):
        sources = [
            LocalFileConfigSource(),
            SecretsConfigSource()
        ]
        manager = ConfigurationManager("PICO001", config_sources=sources)
        assert len(manager.config_sources) == 2
        # Should be sorted by priority
        assert manager.config_sources[0].get_priority() == 2  # LocalFile
        assert manager.config_sources[1].get_priority() == 3  # Secrets
    
    def test_get_valid_config_priority_order(self):
        # Create mock sources with different priorities and availability
        high_priority_source = Mock()
        high_priority_source.get_priority.return_value = 1
        high_priority_source.get_source_name.return_value = "High Priority"
        high_priority_source.is_available.return_value = False
        
        low_priority_source = Mock()
        low_priority_source.get_priority.return_value = 3
        low_priority_source.get_source_name.return_value = "Low Priority"
        low_priority_source.is_available.return_value = True
        
        valid_config = DeviceConfig(
            wifi_ssid="ValidNetwork",
            wifi_password="ValidPass123",
            server_url="https://valid.com",
            api_key="valid_key_123",
            device_name="ValidDevice",
            device_id="PICO001",
            source="test"
        )
        low_priority_source.load_config.return_value = valid_config
        
        sources = [low_priority_source, high_priority_source]  # Unsorted
        manager = ConfigurationManager("PICO001", config_sources=sources)
        
        result = manager.get_valid_config()
        
        # Should get config from low priority source since high priority is unavailable
        assert result == valid_config
        high_priority_source.is_available.assert_called_once()
        low_priority_source.load_config.assert_called_once_with("PICO001")
    
    def test_get_valid_config_invalid_config_rejected(self):
        source = Mock()
        source.get_priority.return_value = 1
        source.get_source_name.return_value = "Test Source"
        source.is_available.return_value = True
        
        # Return invalid config (dummy data)
        invalid_config = DeviceConfig(
            wifi_ssid="test_ssid",  # Dummy value
            wifi_password="ValidPass123",
            server_url="https://valid.com",
            api_key="valid_key_123",
            device_name="ValidDevice",
            device_id="PICO001",
            source="test"
        )
        source.load_config.return_value = invalid_config
        
        manager = ConfigurationManager("PICO001", config_sources=[source])
        result = manager.get_valid_config()
        
        # Should reject invalid config
        assert result is None