# Property-Based Test for Setup AP Activation Consistency
# Feature: pico-wifi-hardening, Property 1: Setup AP Activation Consistency
# Validates: Requirements 1.1, 1.2, 1.3, 1.5, 2.5

import pytest
from hypothesis import given, strategies as st, assume
from unittest.mock import Mock
from pico_device.wifi_manager import WiFiManager, ConnectionState
from pico_device.config_manager import DeviceConfig
from pico_device.setup_ap import SetupAPHandler

# Generators for test data
@st.composite
def wifi_failure_scenario(draw):
    """Generate scenarios that should trigger Setup AP due to WiFi failures"""
    config_manager = Mock()
    
    # Generate valid config (so failure is due to connection, not config)
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
    
    # Generate failure count that exceeds threshold
    failure_threshold = draw(st.integers(min_value=1, max_value=10))
    failure_count = draw(st.integers(min_value=failure_threshold, max_value=failure_threshold + 5))
    
    wifi_manager = WiFiManager(config_manager, failure_threshold=failure_threshold)
    wifi_manager.failure_count = failure_count
    
    return wifi_manager, failure_count, failure_threshold

@st.composite
def no_config_scenario(draw):
    """Generate scenarios with no valid configuration"""
    config_manager = Mock()
    config_manager.get_valid_config.return_value = None
    
    failure_threshold = draw(st.integers(min_value=1, max_value=10))
    wifi_manager = WiFiManager(config_manager, failure_threshold=failure_threshold)
    
    return wifi_manager

@st.composite
def device_id_generator(draw):
    """Generate valid device IDs"""
    prefix = draw(st.sampled_from(['PICO', 'DEV', 'IOT', 'DEVICE']))
    number = draw(st.integers(min_value=1, max_value=9999))
    return f"{prefix}{number:03d}"

class TestSetupAPActivationProperty:
    """Property-based tests for Setup AP activation consistency"""
    
    @given(wifi_failure_scenario())
    def test_wifi_failure_threshold_triggers_setup(self, scenario):
        """Property 1: WiFi failures reaching threshold should trigger Setup AP"""
        wifi_manager, failure_count, failure_threshold = scenario
        
        # Should trigger setup mode when threshold exceeded
        assert wifi_manager.should_enter_setup_mode()
        assert wifi_manager.setup_reason == "WIFI_RETRY_EXCEEDED"
        
        # Verify failure count is at or above threshold
        assert failure_count >= failure_threshold
    
    @given(no_config_scenario())
    def test_no_valid_config_triggers_setup(self, wifi_manager):
        """Property 1: No valid configuration should trigger Setup AP immediately"""
        assert wifi_manager.should_enter_setup_mode()
        assert wifi_manager.setup_reason == "NO_VALID_CONFIG"
    
    @given(device_id_generator())
    def test_setup_ap_ssid_format_consistency(self, device_id):
        """Property 1: Setup AP should create correct SSID format"""
        handler = SetupAPHandler(device_id)
        
        expected_ssid = f"PICO-SETUP-{device_id}"
        assert handler.ssid == expected_ssid
        assert handler.password == "SETUP_PASSWORD"
        assert handler.ap_ip == "192.168.4.1"
    
    def test_user_triggered_setup_consistency(self):
        """Property 1: User-triggered setup should work consistently"""
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
        
        # Force user-triggered setup
        wifi_manager.force_setup_mode("USER_REQUESTED")
        
        assert wifi_manager.connection_state == ConnectionState.SETUP_MODE
        assert wifi_manager.setup_reason == "USER_REQUESTED"
    
    @given(st.integers(min_value=1, max_value=10))
    def test_setup_not_triggered_below_threshold(self, failure_threshold):
        """Property 1: Setup should NOT be triggered when below failure threshold"""
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
        
        wifi_manager = WiFiManager(config_manager, failure_threshold=failure_threshold)
        
        # Set failure count below threshold
        wifi_manager.failure_count = failure_threshold - 1
        
        # Should NOT trigger setup mode
        assert not wifi_manager.should_enter_setup_mode()
        assert wifi_manager.setup_reason is None
    
    def test_setup_decision_logging_consistency(self):
        """Property 1: Setup decisions should be logged consistently"""
        from pico_device.logging_utils import get_logger, init_logger
        
        # Initialize fresh logger
        init_logger(max_entries=50, enable_console=False)
        logger = get_logger()
        initial_count = len(logger.log_entries)
        
        config_manager = Mock()
        config_manager.get_valid_config.return_value = None
        
        wifi_manager = WiFiManager(config_manager)
        
        # Trigger setup decision
        wifi_manager.should_enter_setup_mode()
        
        # Check that decision was logged in the centralized logger
        new_entries = logger.log_entries[initial_count:]
        setup_logs = [entry for entry in new_entries if entry.category.value == 'SETUP']
        assert len(setup_logs) > 0, "Setup decision should be logged"
        
        # Verify log entry contains required information
        decision_entry = setup_logs[0]
        assert decision_entry.context.get('reason') == 'NO_VALID_CONFIG', "Should log the specific reason"
    
    @given(st.lists(st.booleans(), min_size=5, max_size=5))
    def test_persistent_issues_detection(self, connection_results):
        """Property 1: Persistent connection issues should trigger setup"""
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
        
        # Simulate connection history
        for i, success in enumerate(connection_results):
            wifi_manager._log_connection_attempt(
                f"TEST_ATTEMPT_{i}",
                success,
                f"Test connection attempt {i}"
            )
        
        # Count failures
        failure_count = sum(1 for success in connection_results if not success)
        
        # Should trigger setup if 60% or more failures (3+ out of 5)
        if failure_count >= 3:
            assert wifi_manager._has_persistent_connection_issues()
        else:
            assert not wifi_manager._has_persistent_connection_issues()
    
    def test_setup_reason_consistency_across_triggers(self):
        """Property 1: Different triggers should set appropriate reasons"""
        config_manager = Mock()
        
        # Test different trigger scenarios
        test_scenarios = [
            # (config_return, failure_count, expected_reason)
            (None, 0, "NO_VALID_CONFIG"),
            (Mock(), 3, "WIFI_RETRY_EXCEEDED"),  # Assuming threshold is 3
        ]
        
        for config_return, failure_count, expected_reason in test_scenarios:
            config_manager.get_valid_config.return_value = config_return
            wifi_manager = WiFiManager(config_manager, failure_threshold=3)
            wifi_manager.failure_count = failure_count
            
            # Reset reason
            wifi_manager.setup_reason = None
            
            # Check trigger
            should_trigger = wifi_manager.should_enter_setup_mode()
            
            if expected_reason:
                assert should_trigger
                assert wifi_manager.setup_reason == expected_reason
            else:
                assert not should_trigger
    
    @given(st.text(min_size=1, max_size=50))
    def test_custom_setup_reasons(self, custom_reason):
        """Property 1: Custom setup reasons should be handled consistently"""
        config_manager = Mock()
        wifi_manager = WiFiManager(config_manager)
        
        # Force setup with custom reason
        wifi_manager.force_setup_mode(custom_reason)
        
        assert wifi_manager.setup_reason == custom_reason
        assert wifi_manager.connection_state == ConnectionState.SETUP_MODE
    
    def test_setup_activation_idempotency(self):
        """Property 1: Multiple setup activation calls should be idempotent"""
        config_manager = Mock()
        config_manager.get_valid_config.return_value = None
        
        wifi_manager = WiFiManager(config_manager)
        
        # Call should_enter_setup_mode multiple times
        result1 = wifi_manager.should_enter_setup_mode()
        result2 = wifi_manager.should_enter_setup_mode()
        result3 = wifi_manager.should_enter_setup_mode()
        
        # All calls should return the same result
        assert result1 == result2 == result3 == True
        assert wifi_manager.setup_reason == "NO_VALID_CONFIG"