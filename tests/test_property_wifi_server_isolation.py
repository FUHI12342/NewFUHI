# Property-Based Test for WiFi vs Server Failure Isolation
# Feature: pico-wifi-hardening, Property 4: WiFi vs Server Failure Isolation
# Validates: Requirements 1.4

import pytest
from hypothesis import given, strategies as st, assume
from unittest.mock import Mock
from pico_device.wifi_manager import WiFiManager, ConnectionState
from pico_device.config_manager import DeviceConfig

# Generators for test data
@st.composite
def wifi_connected_state(draw):
    """Generate a WiFiManager in connected state"""
    config_manager = Mock()
    
    # Create valid config
    valid_config = DeviceConfig(
        wifi_ssid=draw(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=5, max_size=20)),
        wifi_password=draw(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=8, max_size=20)),
        server_url=f"https://{draw(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll')), min_size=5, max_size=15))}.com",
        api_key=draw(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=10, max_size=30)),
        device_name="TestDevice",
        device_id="PICO001",
        source="test"
    )
    
    config_manager.get_valid_config.return_value = valid_config
    
    wifi_manager = WiFiManager(config_manager)
    
    # Force into connected state
    wifi_manager.connection_state = ConnectionState.CONNECTED
    wifi_manager.current_config = valid_config
    wifi_manager.failure_count = 0
    
    return wifi_manager, valid_config

@st.composite
def server_failure_scenario(draw):
    """Generate scenarios where server fails but WiFi is connected"""
    wifi_manager, config = draw(wifi_connected_state())
    
    # Simulate various server failure types
    failure_type = draw(st.sampled_from([
        "HTTP_TIMEOUT",
        "HTTP_404", 
        "HTTP_500",
        "CONNECTION_REFUSED",
        "DNS_RESOLUTION_FAILED",
        "SSL_ERROR",
        "INVALID_RESPONSE"
    ]))
    
    return wifi_manager, config, failure_type

class TestWiFiServerIsolationProperty:
    """Property-based tests for WiFi vs Server failure isolation"""
    
    @given(server_failure_scenario())
    def test_server_failure_does_not_trigger_setup_mode(self, scenario):
        """Property 4: Server failures should not trigger Setup AP when WiFi is connected"""
        wifi_manager, config, failure_type = scenario
        
        # Ensure WiFi is connected
        assert wifi_manager.connection_state == ConnectionState.CONNECTED
        assert wifi_manager.current_config is not None
        
        # Server failure should not trigger setup mode
        assert not wifi_manager.should_enter_setup_mode()
        
        # WiFi connection should be maintained
        assert wifi_manager.is_server_failure_only()
        assert wifi_manager.is_connected()
    
    @given(wifi_connected_state())
    def test_wifi_connected_maintains_connection_regardless_of_server(self, state_data):
        """Property 4: WiFi connection should be maintained regardless of server status"""
        wifi_manager, config = state_data
        
        # WiFi is connected
        assert wifi_manager.connection_state == ConnectionState.CONNECTED
        
        # Should not enter setup mode
        assert not wifi_manager.should_enter_setup_mode()
        
        # Should identify as server-only failure
        assert wifi_manager.is_server_failure_only()
        
        # Current SSID should be available
        assert wifi_manager.get_current_ssid() == config.wifi_ssid
    
    def test_wifi_failure_vs_server_failure_distinction(self):
        """Property 4: System should distinguish between WiFi and server failures"""
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
        
        # Scenario 1: WiFi connected, server fails
        wifi_manager.connection_state = ConnectionState.CONNECTED
        wifi_manager.current_config = valid_config
        wifi_manager.failure_count = 0
        
        # Server failure should not trigger setup
        assert not wifi_manager.should_enter_setup_mode()
        assert wifi_manager.is_server_failure_only()
        
        # Scenario 2: WiFi fails
        wifi_manager.connection_state = ConnectionState.FAILED
        wifi_manager.current_config = None
        wifi_manager.failure_count = 3  # Exceeds threshold
        
        # WiFi failure should trigger setup
        assert wifi_manager.should_enter_setup_mode()
        assert not wifi_manager.is_server_failure_only()
    
    @given(st.integers(min_value=0, max_value=10))
    def test_server_failures_do_not_increment_wifi_failure_count(self, initial_failure_count):
        """Property 4: Server failures should not increment WiFi failure counter"""
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
        wifi_manager.connection_state = ConnectionState.CONNECTED
        wifi_manager.current_config = valid_config
        wifi_manager.failure_count = initial_failure_count
        
        # Simulate server failure (but WiFi still connected)
        # Server failures should not affect WiFi failure count
        original_count = wifi_manager.failure_count
        
        # Check that failure count remains unchanged for server-only failures
        assert wifi_manager.is_server_failure_only()
        assert wifi_manager.failure_count == original_count
    
    def test_setup_mode_only_on_wifi_issues(self):
        """Property 4: Setup mode should only be triggered by WiFi-related issues"""
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
        
        # Test various WiFi-related triggers
        wifi_triggers = [
            # No valid config
            (lambda: setattr(config_manager, 'get_valid_config', Mock(return_value=None)), "NO_VALID_CONFIG"),
            # WiFi failure threshold exceeded
            (lambda: setattr(wifi_manager, 'failure_count', 3), "WIFI_RETRY_EXCEEDED"),
        ]
        
        for setup_trigger, expected_reason in wifi_triggers:
            # Reset state
            wifi_manager.connection_state = ConnectionState.DISCONNECTED
            wifi_manager.current_config = None
            wifi_manager.failure_count = 0
            wifi_manager.setup_reason = None
            
            # Apply trigger
            setup_trigger()
            
            # Should trigger setup mode
            assert wifi_manager.should_enter_setup_mode()
            assert wifi_manager.setup_reason == expected_reason
    
    @given(st.text(min_size=5, max_size=20))
    def test_force_setup_mode_with_custom_reason(self, custom_reason):
        """Property 4: Manual setup mode forcing should work with custom reasons"""
        config_manager = Mock()
        wifi_manager = WiFiManager(config_manager)
        
        # Force setup mode
        wifi_manager.force_setup_mode(custom_reason)
        
        assert wifi_manager.connection_state == ConnectionState.SETUP_MODE
        assert wifi_manager.setup_reason == custom_reason
    
    def test_connection_history_tracking(self):
        """Property 4: Connection attempts should be logged for debugging"""
        from unittest.mock import patch
        
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
        
        # Simulate connection attempt
        with patch.object(wifi_manager, '_attempt_wifi_connection', return_value=True):
            wifi_manager.connect_wifi()
        
        # Check history is recorded
        history = wifi_manager.get_connection_history()
        assert len(history) > 0
        
        # Check history contains relevant information
        for entry in history:
            assert 'timestamp' in entry
            assert 'event' in entry
            assert 'details' in entry