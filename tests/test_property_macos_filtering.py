# Property-Based Test: macOS File Filtering
# Feature: pico-wifi-hardening, Property 10: macOS File Filtering

import pytest
import json
import os
import tempfile
from hypothesis import given, strategies as st, settings
from pico_device.file_utils import FileUtils

class TestMacOSFileFilteringProperty:
    """
    Property 10: macOS File Filtering
    For any file system operation, the system should ignore macOS ._ files
    and process only relevant configuration files.
    
    **Validates: Requirements 5.3**
    """
    
    @given(
        base_filename=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))),
        extension=st.sampled_from(['.json', '.txt', '.cfg', '.conf', '.ini'])
    )
    @settings(max_examples=50, deadline=3000)
    def test_macos_resource_fork_detection(self, base_filename, extension):
        """
        Property: macOS resource fork file detection
        
        For any filename, the corresponding macOS resource fork file (._filename)
        should be correctly identified and filtered out.
        """
        regular_filename = f"{base_filename}{extension}"
        macos_filename = f"._{base_filename}{extension}"
        
        # Regular file should not be identified as macOS metadata
        assert not FileUtils.is_macos_metadata_file(regular_filename), \
            f"Regular file {regular_filename} should not be identified as macOS metadata"
        
        # macOS resource fork should be identified as metadata
        assert FileUtils.is_macos_metadata_file(macos_filename), \
            f"macOS resource fork {macos_filename} should be identified as metadata"
        
        # Test filtering behavior
        file_list = [regular_filename, macos_filename, "other_file.json"]
        filtered_list = FileUtils.filter_macos_files(file_list)
        
        assert regular_filename in filtered_list, "Regular file should remain after filtering"
        assert macos_filename not in filtered_list, "macOS resource fork should be filtered out"
        assert "other_file.json" in filtered_list, "Other regular files should remain"
    
    @given(
        directory_name=st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        file_count=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=30, deadline=4000)
    def test_macos_file_filtering_in_directory_operations(self, directory_name, file_count):
        """
        Property: macOS file filtering in directory operations
        
        When processing files in a directory, macOS metadata files should be
        automatically filtered out without affecting regular file operations.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                # Create test directory
                os.makedirs(directory_name, exist_ok=True)
                
                regular_files = []
                macos_files = []
                
                # Create regular files and their macOS counterparts
                for i in range(file_count):
                    regular_file = f"{directory_name}/config_{i}.json"
                    macos_file = f"{directory_name}/._config_{i}.json"
                    
                    # Create regular file with valid JSON
                    config_data = {'file_id': i, 'type': 'regular'}
                    with open(regular_file, 'w') as f:
                        json.dump(config_data, f)
                    
                    # Create macOS metadata file
                    with open(macos_file, 'w') as f:
                        f.write("macOS resource fork data")
                    
                    regular_files.append(regular_file)
                    macos_files.append(macos_file)
                
                # Add .DS_Store file
                ds_store_file = f"{directory_name}/.DS_Store"
                with open(ds_store_file, 'w') as f:
                    f.write("DS_Store data")
                macos_files.append(ds_store_file)
                
                # Get all files in directory
                all_files = os.listdir(directory_name)
                
                # Filter macOS files
                filtered_files = FileUtils.filter_macos_files(all_files)
                
                # Verify filtering results
                for regular_file in regular_files:
                    basename = os.path.basename(regular_file)
                    assert basename in filtered_files, f"Regular file {basename} should remain after filtering"
                
                for macos_file in macos_files:
                    basename = os.path.basename(macos_file)
                    assert basename not in filtered_files, f"macOS file {basename} should be filtered out"
                
                # Test that safe loading ignores macOS files
                for macos_file in macos_files:
                    loaded_data = FileUtils.load_json_safe(macos_file)
                    assert loaded_data is None, f"macOS file {macos_file} should be ignored during loading"
                
                # Test that regular files can still be loaded
                for regular_file in regular_files:
                    loaded_data = FileUtils.load_json_safe(regular_file)
                    assert loaded_data is not None, f"Regular file {regular_file} should be loadable"
                    assert loaded_data['type'] == 'regular', "Loaded data should match expected content"
                
            finally:
                os.chdir(original_cwd)
    
    @given(
        macos_system_file=st.sampled_from([
            '.DS_Store',
            '.Spotlight-V100',
            '.Trashes',
            '.fseventsd',
            '.TemporaryItems',
            '.VolumeIcon.icns',
            '.DocumentRevisions-V100',
            '.PKInstallSandboxManager',
            '.PKInstallSandboxManager-SystemSoftware'
        ])
    )
    @settings(max_examples=20, deadline=2000)
    def test_macos_system_file_detection(self, macos_system_file):
        """
        Property: macOS system file detection
        
        Common macOS system files should be correctly identified as metadata
        and filtered out from configuration file operations.
        """
        # Test identification
        assert FileUtils.is_macos_metadata_file(macos_system_file), \
            f"macOS system file {macos_system_file} should be identified as metadata"
        
        # Test filtering in mixed file list
        regular_files = ['config.json', 'settings.ini', 'data.txt']
        mixed_files = regular_files + [macos_system_file]
        
        filtered_files = FileUtils.filter_macos_files(mixed_files)
        
        # Verify system file is filtered out
        assert macos_system_file not in filtered_files, \
            f"macOS system file {macos_system_file} should be filtered out"
        
        # Verify regular files remain
        for regular_file in regular_files:
            assert regular_file in filtered_files, \
                f"Regular file {regular_file} should remain after filtering"
    
    @given(
        filename_base=st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        spotlight_suffix=st.sampled_from(['V100', 'V200', 'V300'])
    )
    @settings(max_examples=20, deadline=2000)
    def test_spotlight_index_file_detection(self, filename_base, spotlight_suffix):
        """
        Property: Spotlight index file detection
        
        Spotlight index files with various version suffixes should be
        correctly identified as macOS metadata files.
        """
        spotlight_file = f".Spotlight-{spotlight_suffix}"
        
        # Test identification
        assert FileUtils.is_macos_metadata_file(spotlight_file), \
            f"Spotlight file {spotlight_file} should be identified as metadata"
        
        # Test with directory context
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                # Create spotlight file
                with open(spotlight_file, 'w') as f:
                    f.write("Spotlight index data")
                
                # Create regular config file
                config_file = f"{filename_base}_config.json"
                config_data = {'test': 'data'}
                with open(config_file, 'w') as f:
                    json.dump(config_data, f)
                
                # Test that spotlight file is ignored during loading
                loaded_data = FileUtils.load_json_safe(spotlight_file)
                assert loaded_data is None, "Spotlight file should be ignored during loading"
                
                # Test that regular file can still be loaded
                loaded_data = FileUtils.load_json_safe(config_file)
                assert loaded_data is not None, "Regular config file should be loadable"
                assert loaded_data == config_data, "Loaded data should match saved data"
                
            finally:
                os.chdir(original_cwd)
    
    def test_empty_and_none_filename_handling(self):
        """
        Property: Empty and None filename handling
        
        Edge cases with empty or None filenames should be handled gracefully
        without causing crashes or incorrect filtering.
        """
        # Test None filename
        assert not FileUtils.is_macos_metadata_file(None), "None filename should not be identified as macOS metadata"
        
        # Test empty filename
        assert not FileUtils.is_macos_metadata_file(""), "Empty filename should not be identified as macOS metadata"
        
        # Test filtering with None and empty values
        file_list = ['config.json', None, '', '.DS_Store', 'settings.ini']
        
        # This should not crash
        try:
            filtered_list = FileUtils.filter_macos_files(file_list)
            # None and empty strings should be preserved (not filtered as macOS files)
            # Only .DS_Store should be filtered out
            assert 'config.json' in filtered_list, "Regular file should remain"
            assert 'settings.ini' in filtered_list, "Regular file should remain"
            assert '.DS_Store' not in filtered_list, "macOS file should be filtered out"
        except Exception as e:
            pytest.fail(f"Filtering with None/empty values should not crash: {e}")
    
    @given(
        config_content=st.dictionaries(
            keys=st.sampled_from(['wifi_ssid', 'wifi_password', 'server_url', 'api_key']),
            values=st.text(min_size=1, max_size=50),
            min_size=2,
            max_size=4
        )
    )
    @settings(max_examples=30, deadline=3000)
    def test_macos_file_interference_prevention(self, config_content):
        """
        Property: macOS file interference prevention
        
        macOS metadata files should not interfere with normal configuration
        file operations, even when they contain valid JSON data.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                config_file = "wifi_config.json"
                macos_file = "._wifi_config.json"
                
                # Save legitimate configuration
                success = FileUtils.save_json_with_backup(config_file, config_content)
                assert success, "Saving legitimate config should succeed"
                
                # Create macOS metadata file with different (but valid) JSON
                macos_content = {'metadata': 'should_be_ignored', 'type': 'resource_fork'}
                with open(macos_file, 'w') as f:
                    json.dump(macos_content, f)
                
                # Verify both files exist
                assert os.path.exists(config_file), "Config file should exist"
                assert os.path.exists(macos_file), "macOS file should exist"
                
                # Load configuration - should get legitimate config, not macOS metadata
                loaded_config = FileUtils.load_json_safe(config_file)
                assert loaded_config == config_content, "Should load legitimate config"
                
                # Attempt to load macOS file - should be ignored
                loaded_macos = FileUtils.load_json_safe(macos_file)
                assert loaded_macos is None, "macOS metadata file should be ignored"
                
                # Test file listing and filtering
                all_files = os.listdir('.')
                filtered_files = FileUtils.filter_macos_files(all_files)
                
                assert config_file in filtered_files, "Config file should remain after filtering"
                assert macos_file not in filtered_files, "macOS file should be filtered out"
                
            finally:
                os.chdir(original_cwd)