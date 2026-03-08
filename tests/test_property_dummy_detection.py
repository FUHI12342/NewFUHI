# Property-Based Test for Dummy Data Detection
# Feature: pico-wifi-hardening, Property 3: Dummy Data Detection and Rejection
# Validates: Requirements 2.2, 2.3

import pytest
from hypothesis import given, strategies as st, assume
from pico_device.config_manager import DeviceConfig

# Generators for test data
@st.composite
def dummy_values(draw):
    """Generate values that should be detected as dummy data"""
    dummy_patterns = [
        'test_', 'sample_', 'example_', 'dummy_',
        'YOUR_', '_HERE', 'REPLACE_ME', 'TODO',
        'your-server.com', 'localhost', 'example.com',
        'test.com', 'sample.com', 'placeholder',
        'changeme', 'default', 'temp_'
    ]
    
    pattern = draw(st.sampled_from(dummy_patterns))
    suffix = draw(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=1, max_size=20))
    
    # Mix case variations
    case_variant = draw(st.sampled_from(['upper', 'lower', 'mixed']))
    if case_variant == 'upper':
        return (pattern + suffix).upper()
    elif case_variant == 'lower':
        return (pattern + suffix).lower()
    else:
        return pattern + suffix

@st.composite
def valid_values(draw):
    """Generate values that should NOT be detected as dummy data"""
    # Generate legitimate-looking values
    prefixes = ['prod_', 'live_', 'real_', 'actual_', 'secure_']
    domains = ['mycompany.com', 'production.net', 'api.service.io', 'backend.app']
    
    value_type = draw(st.sampled_from(['prefixed', 'domain', 'random']))
    
    if value_type == 'prefixed':
        prefix = draw(st.sampled_from(prefixes))
        # Ensure suffix doesn't contain dummy patterns
        suffix = draw(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=5, max_size=20))
        result = prefix + suffix
        # Double-check it doesn't contain dummy patterns
        dummy_patterns = [
            'test_', 'sample_', 'example_', 'dummy_',
            'your_', '_here', 'replace_me', 'todo',
            'localhost', 'example.com', 'test.com', 
            'sample.com', 'placeholder', 'changeme', 'default', 'temp_'
        ]
        assume(not any(pattern.lower() in result.lower() for pattern in dummy_patterns))
        return result
    elif value_type == 'domain':
        return draw(st.sampled_from(domains))
    else:
        # Generate random string that doesn't contain dummy patterns
        text = draw(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=8, max_size=30))
        # Ensure it doesn't accidentally contain dummy patterns
        dummy_patterns = [
            'test_', 'sample_', 'example_', 'dummy_',
            'your_', '_here', 'replace_me', 'todo',
            'localhost', 'example.com', 'test.com', 
            'sample.com', 'placeholder', 'changeme', 'default', 'temp_'
        ]
        assume(not any(pattern.lower() in text.lower() for pattern in dummy_patterns))
        return text

@st.composite
def device_config_with_dummy_field(draw):
    """Generate DeviceConfig with one dummy field"""
    # Generate valid values for most fields
    valid_ssid = draw(valid_values())
    valid_password = draw(valid_values())
    valid_url = f"https://{draw(valid_values())}"
    valid_api_key = draw(valid_values())
    
    # Choose which field to make dummy
    dummy_field = draw(st.sampled_from(['wifi_ssid', 'wifi_password', 'server_url', 'api_key']))
    dummy_value = draw(dummy_values())
    
    config_data = {
        'wifi_ssid': valid_ssid,
        'wifi_password': valid_password,
        'server_url': valid_url,
        'api_key': valid_api_key,
        'device_name': 'TestDevice',
        'device_id': 'PICO001',
        'source': 'test'
    }
    
    # Replace one field with dummy value
    if dummy_field == 'server_url':
        config_data[dummy_field] = f"https://{dummy_value}"
    else:
        config_data[dummy_field] = dummy_value
    
    return DeviceConfig(**config_data), dummy_field

class TestDummyDataDetectionProperty:
    """Property-based tests for dummy data detection"""
    
    @given(dummy_values())
    def test_dummy_values_detected(self, dummy_value):
        """Property 3: Any configuration containing dummy patterns should be rejected"""
        # Test with dummy SSID
        config = DeviceConfig(
            wifi_ssid=dummy_value,
            wifi_password="ValidPassword123",
            server_url="https://valid-server.com",
            api_key="valid_api_key_12345",
            device_name="Device1",
            device_id="PICO001",
            source="test"
        )
        assert not config.is_valid(), f"Dummy SSID '{dummy_value}' should be detected as invalid"
        
        # Test with dummy password
        config = DeviceConfig(
            wifi_ssid="ValidNetwork",
            wifi_password=dummy_value,
            server_url="https://valid-server.com",
            api_key="valid_api_key_12345",
            device_name="Device1",
            device_id="PICO001",
            source="test"
        )
        assert not config.is_valid(), f"Dummy password '{dummy_value}' should be detected as invalid"
        
        # Test with dummy API key
        config = DeviceConfig(
            wifi_ssid="ValidNetwork",
            wifi_password="ValidPassword123",
            server_url="https://valid-server.com",
            api_key=dummy_value,
            device_name="Device1",
            device_id="PICO001",
            source="test"
        )
        assert not config.is_valid(), f"Dummy API key '{dummy_value}' should be detected as invalid"
    
    @given(valid_values())
    def test_valid_values_accepted(self, valid_value):
        """Property 3: Valid configurations should not be rejected as dummy data"""
        config = DeviceConfig(
            wifi_ssid=valid_value,
            wifi_password=valid_value,
            server_url=f"https://{valid_value}",
            api_key=valid_value,
            device_name="Device1",
            device_id="PICO001",
            source="test"
        )
        assert config.is_valid(), f"Valid value '{valid_value}' should not be detected as dummy"
    
    @given(device_config_with_dummy_field())
    def test_single_dummy_field_invalidates_config(self, config_and_field):
        """Property 3: Any single dummy field should invalidate entire configuration"""
        config, dummy_field = config_and_field
        assert not config.is_valid(), f"Config with dummy {dummy_field} should be invalid"
    
    @given(st.text(min_size=0, max_size=2))
    def test_empty_or_short_values_rejected(self, short_value):
        """Property 3: Empty or very short values should be rejected"""
        config = DeviceConfig(
            wifi_ssid=short_value,
            wifi_password="ValidPassword123",
            server_url="https://valid-server.com",
            api_key="valid_api_key_12345",
            device_name="Device1",
            device_id="PICO001",
            source="test"
        )
        # Empty or very short values should be invalid
        assert not config.is_valid(), f"Short SSID '{short_value}' should be invalid"
    
    def test_case_insensitive_dummy_detection(self):
        """Property 3: Dummy detection should be case-insensitive"""
        dummy_variations = [
            "TEST_SSID", "test_ssid", "Test_SSID", "TeSt_SsId",
            "YOUR_API_KEY_HERE", "your_api_key_here", "Your_Api_Key_Here"
        ]
        
        for dummy_value in dummy_variations:
            config = DeviceConfig(
                wifi_ssid=dummy_value,
                wifi_password="ValidPassword123",
                server_url="https://valid-server.com",
                api_key="valid_api_key_12345",
                device_name="Device1",
                device_id="PICO001",
                source="test"
            )
            assert not config.is_valid(), f"Case variant '{dummy_value}' should be detected as dummy"