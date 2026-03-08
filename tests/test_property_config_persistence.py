# Property-Based Test: Configuration Persistence Round Trip
# Feature: pico-wifi-hardening, Property 5: Configuration Persistence Round Trip

import pytest
import json
import os
import tempfile
from hypothesis import given, strategies as st, settings
from pico_device.setup_ap import SetupAPHandler
from pico_device.config_manager import DeviceConfig, ConfigSource

class TestConfigurationPersistenceProperty:
    """
    Property 5: Configuration Persistence Round Trip
    For any valid configuration submitted through the Setup AP web interface,
    saving then loading the configuration should produce equivalent settings
    and trigger reconnection.
    
    **Validates: Requirements 3.3, 3.4**
    """
    
    @given(
        device_id=st.text(min_size=5, max_size=20).filter(lambda x: not any(dummy in x.upper() for dummy in ['TEST', 'SAMPLE', 'DUMMY', 'YOUR', 'TODO', 'REPLACE', 'EXAMPLE'])),
        wifi_ssid=st.text(min_size=5, max_size=32).filter(lambda x: not any(dummy in x.upper() for dummy in ['TEST', 'SAMPLE', 'DUMMY', 'YOUR', 'TODO', 'REPLACE', 'EXAMPLE'])),
        wifi_password=st.text(min_size=8, max_size=63).filter(lambda x: not any(dummy in x.upper() for dummy in ['TEST', 'SAMPLE', 'DUMMY', 'YOUR', 'TODO', 'REPLACE', 'EXAMPLE'])),
        server_url=st.sampled_from([
            "https://api.production.com",
            "https://server.live.com",
            "https://backend.myapp.com",
            "https://api.staging.com",
            "https://192.168.1.100:8000"
        ]),
        api_key=st.text(min_size=16, max_size=64).filter(lambda x: not any(dummy in x.upper() for dummy in ['TEST', 'SAMPLE', 'DUMMY', 'YOUR', 'TODO', 'REPLACE', 'EXAMPLE'])),
        device_name=st.text(min_size=5, max_size=50).filter(lambda x: not any(dummy in x.upper() for dummy in ['TEST', 'SAMPLE', 'DUMMY', 'YOUR', 'TODO', 'REPLACE', 'EXAMPLE']))
    )
    @settings(max_examples=100, deadline=5000)
    def test_configuration_persistence_round_trip(self, device_id, wifi_ssid, wifi_password, server_url, api_key, device_name):
        """
        Property: Configuration persistence round trip consistency
        
        For any valid configuration data:
        1. Save configuration through SetupAPHandler
        2. Load configuration from saved file
        3. Verify all fields match exactly
        4. Verify configuration is valid
        """
        # Create temporary directory for test
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                # Create SetupAPHandler
                handler = SetupAPHandler(device_id)
                
                # Create form data (simulating web form submission)
                form_data = {
                    'wifi_ssid': wifi_ssid,
                    'wifi_password': wifi_password,
                    'server_url': server_url,
                    'api_key': api_key,
                    'device_name': device_name
                }
                
                # Save configuration
                save_success = handler.handle_config_update(form_data)
                assert save_success, "Configuration save should succeed for valid data"
                
                # Verify file was created
                assert os.path.exists('wifi_config.json'), "Configuration file should be created"
                
                # Load configuration from file
                with open('wifi_config.json', 'r') as f:
                    saved_config = json.load(f)
                
                # Verify all fields are preserved exactly
                assert saved_config['wifi_ssid'] == wifi_ssid, "WiFi SSID should be preserved"
                assert saved_config['wifi_password'] == wifi_password, "WiFi password should be preserved"
                assert saved_config['server_url'] == server_url, "Server URL should be preserved"
                assert saved_config['api_key'] == api_key, "API key should be preserved"
                assert saved_config['device_name'] == device_name, "Device name should be preserved"
                assert saved_config['device_id'] == device_id, "Device ID should be preserved"
                
                # Create DeviceConfig from saved data to verify validity
                device_config = DeviceConfig(
                    wifi_ssid=saved_config['wifi_ssid'],
                    wifi_password=saved_config['wifi_password'],
                    server_url=saved_config['server_url'],
                    api_key=saved_config['api_key'],
                    device_name=saved_config['device_name'],
                    device_id=saved_config['device_id'],
                    source=ConfigSource.LOCAL_FILE.value
                )
                
                # Verify configuration is valid
                assert device_config.is_valid(), "Saved configuration should be valid"
                
                # Verify no dummy data was introduced
                assert not device_config._is_dummy_value(device_config.wifi_ssid), "SSID should not be dummy"
                assert not device_config._is_dummy_value(device_config.wifi_password), "Password should not be dummy"
                assert not device_config._is_dummy_value(device_config.api_key), "API key should not be dummy"
                
            finally:
                os.chdir(original_cwd)
    
    @given(
        device_id=st.text(min_size=5, max_size=20).filter(lambda x: not any(dummy in x.upper() for dummy in ['TEST', 'SAMPLE', 'DUMMY', 'YOUR', 'TODO', 'REPLACE', 'EXAMPLE'])),
        wifi_ssid=st.text(min_size=5, max_size=32).filter(lambda x: not any(dummy in x.upper() for dummy in ['TEST', 'SAMPLE', 'DUMMY', 'YOUR', 'TODO', 'REPLACE', 'EXAMPLE'])),
        wifi_password=st.text(min_size=8, max_size=63).filter(lambda x: not any(dummy in x.upper() for dummy in ['TEST', 'SAMPLE', 'DUMMY', 'YOUR', 'TODO', 'REPLACE', 'EXAMPLE'])),
        server_url=st.sampled_from([
            "https://api.production.com",
            "https://server.live.com"
        ]),
        api_key=st.text(min_size=16, max_size=64).filter(lambda x: not any(dummy in x.upper() for dummy in ['TEST', 'SAMPLE', 'DUMMY', 'YOUR', 'TODO', 'REPLACE', 'EXAMPLE']))
    )
    @settings(max_examples=50, deadline=5000)
    def test_configuration_backup_creation(self, device_id, wifi_ssid, wifi_password, server_url, api_key):
        """
        Property: Configuration backup creation
        
        When saving configuration over existing file:
        1. Existing file should be backed up
        2. New configuration should be saved
        3. Both files should be valid JSON
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                # Create initial configuration file
                initial_config = {
                    'wifi_ssid': 'initial_ssid',
                    'wifi_password': 'initial_password',
                    'server_url': 'https://initial.com',
                    'api_key': 'initial_key',
                    'device_name': 'initial_device',
                    'device_id': device_id
                }
                
                with open('wifi_config.json', 'w') as f:
                    json.dump(initial_config, f)
                
                # Create handler and save new configuration
                handler = SetupAPHandler(device_id)
                
                form_data = {
                    'wifi_ssid': wifi_ssid,
                    'wifi_password': wifi_password,
                    'server_url': server_url,
                    'api_key': api_key,
                    'device_name': f"updated_{device_id}"
                }
                
                save_success = handler.handle_config_update(form_data)
                assert save_success, "Configuration save should succeed"
                
                # Verify backup was created
                assert os.path.exists('wifi_config.json.backup'), "Backup file should be created"
                
                # Verify backup contains original data
                with open('wifi_config.json.backup', 'r') as f:
                    backup_config = json.load(f)
                
                assert backup_config['wifi_ssid'] == 'initial_ssid', "Backup should contain original SSID"
                assert backup_config['wifi_password'] == 'initial_password', "Backup should contain original password"
                
                # Verify new file contains updated data
                with open('wifi_config.json', 'r') as f:
                    new_config = json.load(f)
                
                assert new_config['wifi_ssid'] == wifi_ssid, "New file should contain updated SSID"
                assert new_config['wifi_password'] == wifi_password, "New file should contain updated password"
                
            finally:
                os.chdir(original_cwd)
    
    def test_invalid_configuration_rejection(self):
        """
        Property: Invalid configuration rejection
        
        Invalid configurations should be rejected and not saved.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                handler = SetupAPHandler("TEST_DEVICE")
                
                # Test missing required fields
                invalid_configs = [
                    {},  # Empty
                    {'wifi_ssid': 'test'},  # Missing password
                    {'wifi_ssid': 'test', 'wifi_password': 'pass'},  # Missing server_url
                    {'wifi_ssid': 'test', 'wifi_password': 'pass', 'server_url': 'https://test.com'},  # Missing api_key
                    {'wifi_ssid': '', 'wifi_password': 'pass', 'server_url': 'https://test.com', 'api_key': 'key'},  # Empty SSID
                ]
                
                for invalid_config in invalid_configs:
                    save_success = handler.handle_config_update(invalid_config)
                    assert not save_success, f"Invalid configuration should be rejected: {invalid_config}"
                    
                    # Verify no file was created
                    assert not os.path.exists('wifi_config.json'), "No file should be created for invalid config"
                
            finally:
                os.chdir(original_cwd)
    
    @given(
        device_id=st.text(min_size=5, max_size=20).filter(lambda x: not any(dummy in x.upper() for dummy in ['TEST', 'SAMPLE', 'DUMMY', 'YOUR', 'TODO', 'REPLACE', 'EXAMPLE']))
    )
    @settings(max_examples=20, deadline=2000)
    def test_setup_ap_info_consistency(self, device_id):
        """
        Property: Setup AP information consistency
        
        Setup AP information should be consistent with device ID.
        """
        handler = SetupAPHandler(device_id)
        setup_info = handler.get_setup_info()
        
        # Verify SSID format
        expected_ssid = f"PICO-SETUP-{device_id}"
        assert setup_info['ssid'] == expected_ssid, "SSID should follow correct format"
        
        # Verify password is consistent
        assert setup_info['password'] == "SETUP_PASSWORD", "Password should be consistent"
        
        # Verify IP address
        assert setup_info['ip_address'] == "192.168.4.1", "IP address should be consistent"
        
        # Verify web URL
        assert setup_info['web_url'] == "http://192.168.4.1", "Web URL should be consistent"
        
        # Verify device ID
        assert setup_info['device_id'] == device_id, "Device ID should match"