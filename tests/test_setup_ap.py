# Tests for Setup AP Handler
import pytest
import json
import os
from unittest.mock import patch, mock_open
from pico_device.setup_ap import SetupAPHandler

class TestSetupAPHandler:
    """Test Setup AP Handler configuration and web interface"""
    
    def test_initialization(self):
        handler = SetupAPHandler("PICO001")
        
        assert handler.device_id == "PICO001"
        assert handler.ssid == "PICO-SETUP-PICO001"
        assert handler.password == "SETUP_PASSWORD"
        assert handler.ap_ip == "192.168.4.1"
    
    def test_handle_config_update_valid(self):
        handler = SetupAPHandler("PICO001")
        
        form_data = {
            'wifi_ssid': 'NewNetwork',
            'wifi_password': 'NewPassword123',
            'server_url': 'https://newserver.com',
            'api_key': 'new_api_key_456',
            'device_name': 'NewDevice'
        }
        
        with patch.object(handler.config_manager, 'save_config', return_value=True) as mock_save:
            result = handler.handle_config_update(form_data)
            
            assert result
            mock_save.assert_called_once()
            
            # Check the config data passed to save
            call_args = mock_save.call_args[0][0]
            assert call_args['wifi_ssid'] == 'NewNetwork'
            assert call_args['device_id'] == 'PICO001'
    
    def test_handle_config_update_missing_fields(self):
        handler = SetupAPHandler("PICO001")
        
        # Missing required field
        form_data = {
            'wifi_ssid': 'NewNetwork',
            # Missing wifi_password
            'server_url': 'https://newserver.com',
            'api_key': 'new_api_key_456'
        }
        
        result = handler.handle_config_update(form_data)
        assert not result
    
    def test_config_file_operations(self):
        handler = SetupAPHandler("PICO001")
        
        config_data = {
            'wifi_ssid': 'TestNetwork',
            'wifi_password': 'TestPass123',
            'server_url': 'https://test.com',
            'api_key': 'test_key_123'
        }
        
        with patch.object(handler.config_manager, 'save_config', return_value=True) as mock_save:
            result = handler.config_manager.save_config(config_data)
            assert result
            mock_save.assert_called_once_with(config_data)
    
    def test_config_status_retrieval(self):
        handler = SetupAPHandler("PICO001")
        
        with patch.object(handler.config_manager, 'get_config_status', return_value={'has_valid_config': True}) as mock_status:
            status = handler.get_config_status()
            assert status['has_valid_config']
            mock_status.assert_called_once()
    
    def test_generate_config_form(self):
        handler = SetupAPHandler("PICO001")
        html = handler._generate_config_form()
        
        # Check that form contains required fields
        assert 'wifi_ssid' in html
        assert 'wifi_password' in html
        assert 'server_url' in html
        assert 'api_key' in html
        assert 'device_name' in html
        assert 'method="POST"' in html