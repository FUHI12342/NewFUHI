# File handling utilities for Pico 2 W WiFi Hardening
# Provides robust JSON validation, backup creation, and error recovery

import json
import os

class FileOperationError(Exception):
    """Custom exception for file operation errors"""
    pass

class FileUtils:
    """Utility class for robust file operations with error handling"""
    
    @staticmethod
    def is_macos_metadata_file(filename):
        """Check if file is a macOS metadata file that should be ignored"""
        if not filename:
            return False
            
        # Check for common macOS metadata file patterns
        macos_patterns = [
            '._',           # Resource fork files
            '.DS_Store',    # Directory metadata
            '.Spotlight-',  # Spotlight index files
            '.Trashes',     # Trash metadata
            '.fseventsd',   # File system events
            '.TemporaryItems',  # Temporary items
            '.VolumeIcon.icns', # Volume icons
            '.DocumentRevisions-', # Document revisions
            '.PKInstallSandboxManager', # Package installer sandbox
        ]
        
        return any(filename.startswith(pattern) for pattern in macos_patterns)
    
    @staticmethod
    def filter_macos_files(file_list):
        """Filter out macOS metadata files from a list of filenames"""
        return [f for f in file_list if not FileUtils.is_macos_metadata_file(f)]
    
    @staticmethod
    def validate_json_file(file_path):
        """Validates that a JSON file exists and is readable"""
        try:
            with open(file_path, 'r') as f:
                json.load(f)
            return True
        except Exception:
            # Catches all errors: file not found, JSON decode, permissions, etc.
            return False
    
    @staticmethod
    def load_json_safe(file_path):
        """Safely load JSON file with error handling"""
        from .logging_utils import log_file_operation
        
        try:
            if not os.path.exists(file_path):
                log_file_operation("load", file_path, False, {'reason': 'file_not_found'})
                return None
                
            if FileUtils.is_macos_metadata_file(os.path.basename(file_path)):
                log_file_operation("load", file_path, False, {'reason': 'macos_metadata_ignored'})
                return None
                
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            log_file_operation("load", file_path, True)
            return data
            
        except json.JSONDecodeError as e:
            log_file_operation("load", file_path, False, {'reason': 'json_decode_error', 'error': str(e)})
            return None
        except OSError as e:
            log_file_operation("load", file_path, False, {'reason': 'os_error', 'error': str(e)})
            return None
        except Exception as e:
            log_file_operation("load", file_path, False, {'reason': 'unexpected_error', 'error': str(e)})
            return None
    
    @staticmethod
    def save_json_with_backup(file_path, data, backup_suffix = ".backup"):
        """Save JSON data with backup of existing file"""
        from .logging_utils import log_file_operation
        
        try:
            # Create backup if file exists
            if os.path.exists(file_path):
                backup_path = f"{file_path}{backup_suffix}"
                try:
                    # Remove old backup if it exists
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                    
                    # Create new backup
                    os.rename(file_path, backup_path)
                    log_file_operation("backup", backup_path, True)
                except OSError as e:
                    log_file_operation("backup", backup_path, False, {'error': str(e)})
                    # Continue anyway - backup failure shouldn't prevent save
            
            # Write new data
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            log_file_operation("save", file_path, True)
            return True
            
        except OSError as e:
            log_file_operation("save", file_path, False, {'reason': 'os_error', 'error': str(e)})
            return False
        except Exception as e:
            log_file_operation("save", file_path, False, {'reason': 'unexpected_error', 'error': str(e)})
            return False
    
    @staticmethod
    def restore_from_backup(file_path, backup_suffix = ".backup"):
        """Restore file from backup"""
        backup_path = f"{file_path}{backup_suffix}"
        
        try:
            if not os.path.exists(backup_path):
                print(f"[FILE] No backup found: {backup_path}")
                return False
            
            # Validate backup before restoring
            if not FileUtils.validate_json_file(backup_path):
                print(f"[FILE] Backup file is invalid: {backup_path}")
                return False
            
            # Remove current file if it exists
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Restore from backup
            os.rename(backup_path, file_path)
            print(f"[FILE] Restored from backup: {backup_path} -> {file_path}")
            return True
            
        except OSError as e:
            print(f"[FILE] Error restoring from backup: {str(e)}")
            return False
    
    @staticmethod
    def cleanup_old_backups(file_path, max_backups = 3):
        """Clean up old backup files, keeping only the most recent ones"""
        try:
            directory = os.path.dirname(file_path) or '.'
            base_name = os.path.basename(file_path)
            
            # Find all backup files for this base file
            backup_files = []
            for filename in os.listdir(directory):
                if filename.startswith(f"{base_name}.backup"):
                    full_path = os.path.join(directory, filename)
                    if os.path.isfile(full_path):
                        backup_files.append((full_path, os.path.getmtime(full_path)))
            
            # Sort by modification time (newest first)
            backup_files.sort(key=lambda x: x[1], reverse=True)
            
            # Remove old backups beyond max_backups
            for backup_path, _ in backup_files[max_backups:]:
                try:
                    os.remove(backup_path)
                    print(f"[FILE] Removed old backup: {backup_path}")
                except OSError as e:
                    print(f"[FILE] Could not remove old backup {backup_path}: {str(e)}")
                    
        except Exception as e:
            print(f"[FILE] Error during backup cleanup: {str(e)}")
    
    @staticmethod
    def get_file_info(file_path):
        """Get file information including size, modification time, and validity"""
        try:
            if not os.path.exists(file_path):
                return None
            
            stat = os.stat(file_path)
            is_valid_json = FileUtils.validate_json_file(file_path)
            
            return {
                'path': file_path,
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'is_valid_json': is_valid_json,
                'is_macos_metadata': FileUtils.is_macos_metadata_file(os.path.basename(file_path))
            }
            
        except OSError as e:
            print(f"[FILE] Error getting file info for {file_path}: {str(e)}")
            return None
    
    @staticmethod
    def ensure_directory_exists(file_path):
        """Ensure the directory for a file path exists"""
        try:
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                print(f"[FILE] Created directory: {directory}")
            return True
        except OSError as e:
            print(f"[FILE] Error creating directory for {file_path}: {str(e)}")
            return False
    
    @staticmethod
    def safe_file_operation(operation_func, *args, **kwargs):
        """Wrapper for safe file operations with error handling"""
        try:
            result = operation_func(*args, **kwargs)
            return True, result
        except FileOperationError as e:
            print(f"[FILE] File operation error: {str(e)}")
            return False, None
        except OSError as e:
            print(f"[FILE] OS error during file operation: {str(e)}")
            return False, None
        except Exception as e:
            print(f"[FILE] Unexpected error during file operation: {str(e)}")
            return False, None

class ConfigFileManager:
    """Specialized file manager for configuration files"""
    
    def __init__(self, config_file = "wifi_config.json"):
        self.config_file = config_file
        self.file_utils = FileUtils()
    
    def load_config(self):
        """Load configuration with error recovery"""
        # Try to load main config file
        config = self.file_utils.load_json_safe(self.config_file)
        
        if config is not None:
            return config
        
        # If main file failed, try backup
        backup_path = f"{self.config_file}.backup"
        if os.path.exists(backup_path):
            print(f"[CONFIG] Main config failed, trying backup: {backup_path}")
            backup_config = self.file_utils.load_json_safe(backup_path)
            
            if backup_config is not None:
                # Restore backup as main file
                if self.file_utils.restore_from_backup(self.config_file):
                    return backup_config
        
        print(f"[CONFIG] No valid configuration found")
        return None
    
    def save_config(self, config_data):
        """Save configuration with backup and validation"""
        # Ensure directory exists
        if not self.file_utils.ensure_directory_exists(self.config_file):
            return False
        
        # Save with backup
        success = self.file_utils.save_json_with_backup(self.config_file, config_data)
        
        if success:
            # Clean up old backups
            self.file_utils.cleanup_old_backups(self.config_file)
        
        return success
    
    def validate_config(self, config_data):
        """Validate configuration data structure"""
        required_fields = ['wifi_ssid', 'wifi_password', 'server_url', 'api_key', 'device_id']
        
        for field in required_fields:
            if field not in config_data or not config_data[field]:
                print(f"[CONFIG] Missing or empty required field: {field}")
                return False
        
        return True
    
    def get_config_status(self):
        """Get status information about configuration files"""
        main_info = self.file_utils.get_file_info(self.config_file)
        backup_info = self.file_utils.get_file_info(f"{self.config_file}.backup")
        
        return {
            'main_file': main_info,
            'backup_file': backup_info,
            'has_valid_config': main_info is not None and main_info.get('is_valid_json', False),
            'has_valid_backup': backup_info is not None and backup_info.get('is_valid_json', False)
        }