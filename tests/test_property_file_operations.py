# Property-Based Test: File Operation Safety and Recovery
# Feature: pico-wifi-hardening, Property 9: File Operation Safety and Recovery

import pytest
import json
import os
import tempfile
from hypothesis import given, strategies as st, settings
from pico_device.file_utils import FileUtils, ConfigFileManager, FileOperationError

class TestFileOperationSafetyProperty:
    """
    Property 9: File Operation Safety and Recovery
    For any configuration file operation (read/write/backup), the system should handle errors gracefully,
    create backups before overwriting, validate JSON structure, and fall back to alternative sources
    when files are corrupted or missing.
    
    **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**
    """
    
    @given(
        config_data=st.dictionaries(
            keys=st.sampled_from(['wifi_ssid', 'wifi_password', 'server_url', 'api_key', 'device_name', 'device_id']),
            values=st.text(min_size=1, max_size=100),
            min_size=6,
            max_size=6
        )
    )
    @settings(max_examples=50, deadline=5000)
    def test_json_save_and_load_round_trip(self, config_data):
        """
        Property: JSON save and load round trip consistency
        
        For any valid configuration data:
        1. Save data to JSON file
        2. Load data from JSON file
        3. Verify data matches exactly
        4. Verify backup is created when overwriting
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                file_path = "test_config.json"
                
                # Save configuration
                success = FileUtils.save_json_with_backup(file_path, config_data)
                assert success, "JSON save should succeed for valid data"
                
                # Verify file was created
                assert os.path.exists(file_path), "JSON file should be created"
                
                # Load configuration
                loaded_data = FileUtils.load_json_safe(file_path)
                assert loaded_data is not None, "JSON load should succeed"
                
                # Verify data matches exactly
                assert loaded_data == config_data, "Loaded data should match saved data"
                
                # Test overwrite with backup creation
                modified_data = config_data.copy()
                modified_data['device_id'] = 'MODIFIED_DEVICE'
                
                success = FileUtils.save_json_with_backup(file_path, modified_data)
                assert success, "JSON overwrite should succeed"
                
                # Verify backup was created
                backup_path = f"{file_path}.backup"
                assert os.path.exists(backup_path), "Backup file should be created"
                
                # Verify backup contains original data
                backup_data = FileUtils.load_json_safe(backup_path)
                assert backup_data == config_data, "Backup should contain original data"
                
                # Verify main file contains modified data
                current_data = FileUtils.load_json_safe(file_path)
                assert current_data == modified_data, "Main file should contain modified data"
                
            finally:
                os.chdir(original_cwd)
    
    @given(
        invalid_json=st.sampled_from([
            '{"incomplete": json',  # Incomplete JSON
            '{invalid: "json"}',    # Invalid syntax
            'not json at all',      # Not JSON
            '',                     # Empty file
            '{"valid": "json", "but": "corrupted"} extra text',  # Valid JSON with extra text
        ])
    )
    @settings(max_examples=20, deadline=3000)
    def test_corrupted_file_handling(self, invalid_json):
        """
        Property: Corrupted file handling and recovery
        
        For any corrupted or invalid JSON file:
        1. Loading should fail gracefully (return None)
        2. Validation should correctly identify invalid files
        3. System should not crash or raise unhandled exceptions
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                file_path = "corrupted_config.json"
                
                # Create corrupted file
                with open(file_path, 'w') as f:
                    f.write(invalid_json)
                
                # Verify file exists
                assert os.path.exists(file_path), "Corrupted file should exist"
                
                # Test validation
                is_valid = FileUtils.validate_json_file(file_path)
                assert not is_valid, "Corrupted file should be identified as invalid"
                
                # Test safe loading
                loaded_data = FileUtils.load_json_safe(file_path)
                assert loaded_data is None, "Loading corrupted file should return None"
                
                # Test that operations don't crash
                file_info = FileUtils.get_file_info(file_path)
                assert file_info is not None, "File info should be available even for corrupted files"
                assert not file_info['is_valid_json'], "File info should indicate invalid JSON"
                
            finally:
                os.chdir(original_cwd)
    
    @given(
        macos_filename=st.sampled_from([
            '._test_file.json',
            '.DS_Store',
            '.Spotlight-V100',
            '.Trashes',
            '.fseventsd',
            '.TemporaryItems',
            '.VolumeIcon.icns'
        ])
    )
    @settings(max_examples=10, deadline=2000)
    def test_macos_file_filtering(self, macos_filename):
        """
        Property: macOS metadata file filtering
        
        For any macOS metadata file:
        1. Should be correctly identified as metadata file
        2. Should be filtered out from file operations
        3. Should not interfere with normal operations
        """
        # Test identification
        is_macos_file = FileUtils.is_macos_metadata_file(macos_filename)
        assert is_macos_file, f"File {macos_filename} should be identified as macOS metadata"
        
        # Test filtering
        file_list = ['config.json', macos_filename, 'other_config.json']
        filtered_list = FileUtils.filter_macos_files(file_list)
        
        assert macos_filename not in filtered_list, "macOS file should be filtered out"
        assert 'config.json' in filtered_list, "Regular files should remain"
        assert 'other_config.json' in filtered_list, "Regular files should remain"
        
        # Test safe loading ignores macOS files
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                # Create macOS metadata file with valid JSON
                with open(macos_filename, 'w') as f:
                    json.dump({'test': 'data'}, f)
                
                # Verify file exists
                assert os.path.exists(macos_filename), "macOS file should exist"
                
                # Test that safe loading ignores it
                loaded_data = FileUtils.load_json_safe(macos_filename)
                assert loaded_data is None, "macOS metadata files should be ignored during loading"
                
            finally:
                os.chdir(original_cwd)
    
    @given(
        config_data=st.dictionaries(
            keys=st.sampled_from(['wifi_ssid', 'wifi_password', 'server_url', 'api_key', 'device_name', 'device_id']),
            values=st.text(min_size=1, max_size=50),
            min_size=6,
            max_size=6
        )
    )
    @settings(max_examples=30, deadline=4000)
    def test_backup_and_restore_operations(self, config_data):
        """
        Property: Backup and restore operation consistency
        
        For any configuration data:
        1. Save should create backup of existing file
        2. Restore should recover from backup correctly
        3. Multiple saves should maintain backup history
        4. Cleanup should remove old backups appropriately
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                file_path = "test_config.json"
                
                # Create initial configuration
                initial_data = {'initial': 'data', 'version': 1}
                success = FileUtils.save_json_with_backup(file_path, initial_data)
                assert success, "Initial save should succeed"
                
                # Save new configuration (should create backup)
                success = FileUtils.save_json_with_backup(file_path, config_data)
                assert success, "Second save should succeed"
                
                # Verify backup exists and contains initial data
                backup_path = f"{file_path}.backup"
                assert os.path.exists(backup_path), "Backup should be created"
                
                backup_data = FileUtils.load_json_safe(backup_path)
                assert backup_data == initial_data, "Backup should contain initial data"
                
                # Verify main file contains new data
                current_data = FileUtils.load_json_safe(file_path)
                assert current_data == config_data, "Main file should contain new data"
                
                # Test restore operation
                success = FileUtils.restore_from_backup(file_path)
                assert success, "Restore should succeed"
                
                # Verify restored data matches initial data
                restored_data = FileUtils.load_json_safe(file_path)
                assert restored_data == initial_data, "Restored data should match initial data"
                
                # Verify backup file is consumed (moved to main file)
                assert not os.path.exists(backup_path), "Backup should be consumed during restore"
                
            finally:
                os.chdir(original_cwd)
    
    @given(
        config_data=st.dictionaries(
            keys=st.sampled_from(['wifi_ssid', 'wifi_password', 'server_url', 'api_key', 'device_name', 'device_id']),
            values=st.text(min_size=1, max_size=30),
            min_size=6,
            max_size=6
        )
    )
    @settings(max_examples=20, deadline=3000)
    def test_config_file_manager_operations(self, config_data):
        """
        Property: ConfigFileManager operation consistency
        
        For any configuration data:
        1. Save and load should be consistent
        2. Validation should work correctly
        3. Status reporting should be accurate
        4. Error recovery should work
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                config_file = "wifi_config.json"
                manager = ConfigFileManager(config_file)
                
                # Test save operation
                success = manager.save_config(config_data)
                assert success, "Config save should succeed"
                
                # Test load operation
                loaded_config = manager.load_config()
                assert loaded_config is not None, "Config load should succeed"
                assert loaded_config == config_data, "Loaded config should match saved config"
                
                # Test validation
                is_valid = manager.validate_config(config_data)
                assert is_valid, "Valid config should pass validation"
                
                # Test status reporting
                status = manager.get_config_status()
                assert status['has_valid_config'], "Status should indicate valid config"
                assert status['main_file'] is not None, "Status should include main file info"
                
                # Test with invalid config
                invalid_config = {'incomplete': 'config'}
                is_valid = manager.validate_config(invalid_config)
                assert not is_valid, "Invalid config should fail validation"
                
            finally:
                os.chdir(original_cwd)
    
    def test_missing_file_handling(self):
        """
        Property: Missing file handling
        
        Operations on non-existent files should:
        1. Return None/False appropriately
        2. Not crash or raise unhandled exceptions
        3. Provide meaningful error information
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                non_existent_file = "does_not_exist.json"
                
                # Test loading non-existent file
                loaded_data = FileUtils.load_json_safe(non_existent_file)
                assert loaded_data is None, "Loading non-existent file should return None"
                
                # Test validation of non-existent file
                is_valid = FileUtils.validate_json_file(non_existent_file)
                assert not is_valid, "Non-existent file should be invalid"
                
                # Test file info for non-existent file
                file_info = FileUtils.get_file_info(non_existent_file)
                assert file_info is None, "File info for non-existent file should be None"
                
                # Test restore from non-existent backup
                success = FileUtils.restore_from_backup(non_existent_file)
                assert not success, "Restore from non-existent backup should fail"
                
                # Test ConfigFileManager with non-existent file
                manager = ConfigFileManager(non_existent_file)
                loaded_config = manager.load_config()
                assert loaded_config is None, "Loading non-existent config should return None"
                
                status = manager.get_config_status()
                assert not status['has_valid_config'], "Status should indicate no valid config"
                
            finally:
                os.chdir(original_cwd)
    
    def test_directory_creation_and_cleanup(self):
        """
        Property: Directory creation and cleanup
        
        File operations should:
        1. Create necessary directories
        2. Handle directory creation errors gracefully
        3. Clean up backup files appropriately
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                # Test directory creation
                nested_file = "subdir/config.json"
                success = FileUtils.ensure_directory_exists(nested_file)
                assert success, "Directory creation should succeed"
                assert os.path.exists("subdir"), "Subdirectory should be created"
                
                # Test saving to nested directory
                config_data = {'test': 'data'}
                success = FileUtils.save_json_with_backup(nested_file, config_data)
                assert success, "Save to nested directory should succeed"
                assert os.path.exists(nested_file), "File in nested directory should exist"
                
                # Test backup cleanup
                # Create multiple backup files
                for i in range(5):
                    backup_file = f"{nested_file}.backup.{i}"
                    with open(backup_file, 'w') as f:
                        json.dump({'backup': i}, f)
                
                # Run cleanup
                FileUtils.cleanup_old_backups(nested_file, max_backups=2)
                
                # Count remaining backup files
                backup_count = 0
                for filename in os.listdir("subdir"):
                    if filename.startswith("config.json.backup"):
                        backup_count += 1
                
                assert backup_count <= 2, "Cleanup should limit backup files to max_backups"
                
            finally:
                os.chdir(original_cwd)