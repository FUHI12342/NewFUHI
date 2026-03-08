# Property-Based Test for Configuration Source Priority
# Feature: pico-wifi-hardening, Property 2: Configuration Source Priority and Fallback
# Validates: Requirements 2.1, 2.4

import pytest
from hypothesis import given, strategies as st, assume
from unittest.mock import Mock
from pico_device.config_manager import (
    ConfigurationManager, DeviceConfig, ConfigSourceInterface
)

# Generators for test data
@st.composite
def mock_config_source(draw):
    """Generate a mock configuration source with random priority and availability"""
    priority = draw(st.integers(min_value=1, max_value=10))
    is_available = draw(st.booleans())
    has_valid_config = draw(st.booleans())
    source_name = draw(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll')), min_size=3, max_size=10))
    
    source = Mock(spec=ConfigSourceInterface)
    source.get_priority.return_value = priority
    source.is_available.return_value = is_available
    source.get_source_name.return_value = source_name
    
    if is_available and has_valid_config:
        # Create valid config
        config = DeviceConfig(
            wifi_ssid="ValidNetwork",
            wifi_password="ValidPass123",
            server_url="https://valid.com",
            api_key="valid_key_123",
            device_name="ValidDevice",
            device_id="PICO001",
            source=source_name
        )
        source.load_config.return_value = config
    else:
        # Return None or invalid config
        if is_available:
            # Available but invalid config
            invalid_config = DeviceConfig(
                wifi_ssid="test_ssid",  # Dummy value
                wifi_password="ValidPass123",
                server_url="https://valid.com",
                api_key="valid_key_123",
                device_name="ValidDevice",
                device_id="PICO001",
                source=source_name
            )
            source.load_config.return_value = invalid_config
        else:
            source.load_config.return_value = None
    
    return source, priority, is_available, has_valid_config

@st.composite
def config_source_list(draw):
    """Generate a list of mock configuration sources"""
    num_sources = draw(st.integers(min_value=1, max_value=5))
    sources = []
    
    for _ in range(num_sources):
        source_data = draw(mock_config_source())
        sources.append(source_data)
    
    return sources

class TestConfigurationPriorityProperty:
    """Property-based tests for configuration source priority and fallback"""
    
    @given(config_source_list())
    def test_sources_sorted_by_priority(self, source_list):
        """Property 2: Configuration sources should be sorted by priority (lower = higher priority)"""
        sources = [source_data[0] for source_data in source_list]
        
        manager = ConfigurationManager("PICO001", config_sources=sources)
        
        # Check that sources are sorted by priority
        priorities = [source.get_priority() for source in manager.config_sources]
        assert priorities == sorted(priorities), "Sources should be sorted by priority (ascending)"
    
    @given(config_source_list())
    def test_highest_priority_valid_source_selected(self, source_list):
        """Property 2: The highest priority valid source should be selected"""
        sources = [source_data[0] for source_data in source_list]
        
        # Find the expected winner (lowest priority number, available, valid config)
        valid_sources = []
        for source_data in source_list:
            source, priority, is_available, has_valid_config = source_data
            if is_available and has_valid_config:
                valid_sources.append((source, priority))
        
        manager = ConfigurationManager("PICO001", config_sources=sources)
        result = manager.get_valid_config()
        
        if valid_sources:
            # Should select the source with lowest priority number (highest priority)
            expected_priority = min(priority for _, priority in valid_sources)
            expected_sources = [source for source, priority in valid_sources if priority == expected_priority]
            
            # Result should be from one of the highest priority sources
            assert result is not None
            assert result.source in [source.get_source_name() for source in expected_sources]
        else:
            # No valid sources available
            assert result is None
    
    def test_fallback_to_lower_priority_when_higher_unavailable(self):
        """Property 2: Should fall back to lower priority sources when higher priority sources are unavailable"""
        # High priority source - unavailable
        high_priority = Mock(spec=ConfigSourceInterface)
        high_priority.get_priority.return_value = 1
        high_priority.is_available.return_value = False
        high_priority.get_source_name.return_value = "HighPriority"
        
        # Low priority source - available with valid config
        low_priority = Mock(spec=ConfigSourceInterface)
        low_priority.get_priority.return_value = 3
        low_priority.is_available.return_value = True
        low_priority.get_source_name.return_value = "LowPriority"
        
        valid_config = DeviceConfig(
            wifi_ssid="ValidNetwork",
            wifi_password="ValidPass123",
            server_url="https://valid.com",
            api_key="valid_key_123",
            device_name="ValidDevice",
            device_id="PICO001",
            source="LowPriority"
        )
        low_priority.load_config.return_value = valid_config
        
        manager = ConfigurationManager("PICO001", config_sources=[high_priority, low_priority])
        result = manager.get_valid_config()
        
        # Should get config from low priority source
        assert result is not None
        assert result.source == "LowPriority"
        
        # Verify high priority was checked first
        high_priority.is_available.assert_called_once()
        low_priority.load_config.assert_called_once_with("PICO001")
    
    def test_fallback_to_lower_priority_when_higher_invalid(self):
        """Property 2: Should fall back to lower priority sources when higher priority sources have invalid config"""
        # High priority source - available but invalid config
        high_priority = Mock(spec=ConfigSourceInterface)
        high_priority.get_priority.return_value = 1
        high_priority.is_available.return_value = True
        high_priority.get_source_name.return_value = "HighPriority"
        
        invalid_config = DeviceConfig(
            wifi_ssid="test_ssid",  # Dummy value
            wifi_password="ValidPass123",
            server_url="https://valid.com",
            api_key="valid_key_123",
            device_name="ValidDevice",
            device_id="PICO001",
            source="HighPriority"
        )
        high_priority.load_config.return_value = invalid_config
        
        # Low priority source - available with valid config
        low_priority = Mock(spec=ConfigSourceInterface)
        low_priority.get_priority.return_value = 3
        low_priority.is_available.return_value = True
        low_priority.get_source_name.return_value = "LowPriority"
        
        valid_config = DeviceConfig(
            wifi_ssid="ValidNetwork",
            wifi_password="ValidPass123",
            server_url="https://valid.com",
            api_key="valid_key_123",
            device_name="ValidDevice",
            device_id="PICO001",
            source="LowPriority"
        )
        low_priority.load_config.return_value = valid_config
        
        manager = ConfigurationManager("PICO001", config_sources=[high_priority, low_priority])
        result = manager.get_valid_config()
        
        # Should get config from low priority source
        assert result is not None
        assert result.source == "LowPriority"
        
        # Verify both sources were checked
        high_priority.load_config.assert_called_once_with("PICO001")
        low_priority.load_config.assert_called_once_with("PICO001")
    
    @given(st.integers(min_value=1, max_value=10))
    def test_no_valid_sources_returns_none(self, num_sources):
        """Property 2: When no valid configuration sources exist, should return None"""
        sources = []
        
        for i in range(num_sources):
            source = Mock(spec=ConfigSourceInterface)
            source.get_priority.return_value = i + 1
            source.is_available.return_value = False  # All unavailable
            source.get_source_name.return_value = f"Source{i}"
            sources.append(source)
        
        manager = ConfigurationManager("PICO001", config_sources=sources)
        result = manager.get_valid_config()
        
        assert result is None
    
    def test_priority_consistency_with_same_priority_values(self):
        """Property 2: Sources with same priority should be handled consistently"""
        # Two sources with same priority
        source1 = Mock(spec=ConfigSourceInterface)
        source1.get_priority.return_value = 2
        source1.is_available.return_value = True
        source1.get_source_name.return_value = "Source1"
        
        valid_config1 = DeviceConfig(
            wifi_ssid="Network1",
            wifi_password="Pass123",
            server_url="https://server1.com",
            api_key="key123",
            device_name="Device1",
            device_id="PICO001",
            source="Source1"
        )
        source1.load_config.return_value = valid_config1
        
        source2 = Mock(spec=ConfigSourceInterface)
        source2.get_priority.return_value = 2  # Same priority
        source2.is_available.return_value = True
        source2.get_source_name.return_value = "Source2"
        
        valid_config2 = DeviceConfig(
            wifi_ssid="Network2",
            wifi_password="Pass456",
            server_url="https://server2.com",
            api_key="key456",
            device_name="Device2",
            device_id="PICO001",
            source="Source2"
        )
        source2.load_config.return_value = valid_config2
        
        manager = ConfigurationManager("PICO001", config_sources=[source1, source2])
        result = manager.get_valid_config()
        
        # Should get a valid config from one of the sources
        assert result is not None
        assert result.source in ["Source1", "Source2"]
        
        # The first valid source encountered should be selected
        # (stable sort behavior)