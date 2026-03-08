# Tests for WiFi Manager
import pytest
from unittest.mock import Mock, patch
from pico_device.wifi_manager import WiFiManager, ConnectionState
from pico_device.config_manager import DeviceConfig

class TestWiFiManager:
    """Test WiFi Manager connection logic and Setup AP triggers"""
    
    def test_initialization(self):
        config_manager = Mock()
        wifi_manager = WiFiManager(config_manager)
        
        assert wifi_manager.failure_threshold == 3
        assert wifi_manager.failure_count == 0
        assert wifi_manager.connection_state == ConnectionState.DISCONNECTED
    
    def test_connect_wifi_no_config(self):
        config_manager = Mock()
        config_manager.get_valid_config.return_value = None
        
        wifi_manager = WiFiManager(config_manager)
        result = wifi_manager.connect_wifi()
        
        assert not result
        assert wifi_manager.setup_reason == "NO_VALID_CONFIG"
    
    def test_connect_wifi_success(self):
        config_manager = Mock()
        valid_config = DeviceConfig(
            wifi_ssid="TestNetwork",
            wifi_password="TestPass123",
            server_url="https://test.com",
            api_key="test_key_123",
            device_name="TestDevice",
            device_id="PICO001",
            source="test"
        )
        config_manager.get_valid_config.return_value = valid_config
        
        wifi_manager = WiFiManager(config_manager)
        
        with patch.object(wifi_manager, '_attempt_wifi_connection', return_value=True):
            result = wifi_manager.connect_wifi()
        
        assert result
        assert wifi_manager.connection_state == ConnectionState.CONNECTED
        assert wifi_manager.failure_count == 0
    
    def test_connect_wifi_failure_counting(self):
        config_manager = Mock()
        valid_config = DeviceConfig(
            wifi_ssid="TestNetwork",
            wifi_password="TestPass123",
            server_url="https://test.com",
            api_key="test_key_123",
            device_name="TestDevice",
            device_id="PICO001",
            source="test"
        )
        config_manager.get_valid_config.return_value = valid_config
        
        wifi_manager = WiFiManager(config_manager)
        
        with patch.object(wifi_manager, '_attempt_wifi_connection', return_value=False):
            # First failure
            result1 = wifi_manager.connect_wifi()
            assert not result1
            assert wifi_manager.failure_count == 1
            
            # Second failure
            result2 = wifi_manager.connect_wifi()
            assert not result2
            assert wifi_manager.failure_count == 2
            
            # Third failure - should trigger setup mode
            result3 = wifi_manager.connect_wifi()
            assert not result3
            assert wifi_manager.failure_count == 3
            assert wifi_manager.setup_reason == "WIFI_RETRY_EXCEEDED"
    
    def test_should_enter_setup_mode_retry_exceeded(self):
        config_manager = Mock()
        wifi_manager = WiFiManager(config_manager)
        wifi_manager.failure_count = 3
        
        assert wifi_manager.should_enter_setup_mode()
        assert wifi_manager.setup_reason == "WIFI_RETRY_EXCEEDED"
    
    def test_should_enter_setup_mode_no_valid_config(self):
        config_manager = Mock()
        config_manager.get_valid_config.return_value = None
        
        wifi_manager = WiFiManager(config_manager)
        
        assert wifi_manager.should_enter_setup_mode()
        assert wifi_manager.setup_reason == "NO_VALID_CONFIG"
    
    def test_reset_failure_count(self):
        config_manager = Mock()
        wifi_manager = WiFiManager(config_manager)
        wifi_manager.failure_count = 2
        wifi_manager.setup_reason = "TEST_REASON"
        
        wifi_manager.reset_failure_count()
        
        assert wifi_manager.failure_count == 0
        assert wifi_manager.setup_reason is None
    
    def test_server_failure_isolation(self):
        config_manager = Mock()
        wifi_manager = WiFiManager(config_manager)
        wifi_manager.connection_state = ConnectionState.CONNECTED
        wifi_manager.current_config = Mock()
        
        # Server failure should not trigger Setup AP if WiFi is connected
        assert wifi_manager.is_server_failure_only()
        assert not wifi_manager.should_enter_setup_mode()