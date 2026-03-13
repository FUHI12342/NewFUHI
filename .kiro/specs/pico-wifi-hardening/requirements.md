# Requirements Document

## Introduction

This document specifies requirements for a robust WiFi configuration system for Pico 2 W devices running CircuitPython. The system ensures reliable Setup AP fallback when WiFi connections fail and integrates with Django admin for remote configuration management. The system addresses current issues with unreliable Setup fallback, dummy configuration interference, and provides centralized device management through Django.

## Glossary

- **Pico_2W_Device**: A Raspberry Pi Pico 2 W microcontroller running CircuitPython
- **Setup_AP**: Access Point mode activated when WiFi connection fails, providing web interface for configuration
- **Django_Server**: Backend server providing device configuration management through admin interface
- **WiFi_Config_Source**: Any source providing WiFi credentials (Django API, local files, secrets)
- **Device_Config**: Complete configuration including WiFi, server, device, and API key settings
- **Dummy_Config**: Test or placeholder configuration values that should be ignored
- **Configuration_Priority**: Ordered list determining which config source takes precedence

## Requirements

### Requirement 1: Setup AP Activation

**User Story:** As a device operator, I want the Pico 2 W to automatically enter Setup AP mode when WiFi fails, so that I can reconfigure the device without physical access to code.

#### Acceptance Criteria

1. WHEN WiFi connection fails N consecutive times (configurable, default 3), THE Pico_2W_Device SHALL activate Setup_AP mode
2. WHEN no valid WiFi settings are available from any source, THE Pico_2W_Device SHALL activate Setup_AP mode immediately
3. WHEN a user triggers setup mode through button press or reset sequence, THE Pico_2W_Device SHALL activate Setup_AP mode
4. WHEN WiFi is connected but server connection fails, THE Pico_2W_Device SHALL maintain WiFi connection and NOT activate Setup_AP mode
5. WHEN Setup_AP is activated, THE Pico_2W_Device SHALL create an access point with SSID "PICO-SETUP-<device_id>" and password "SETUP_PASSWORD"

### Requirement 2: Configuration Source Priority and Validation

**User Story:** As a system administrator, I want the device to use the most current and valid configuration available, so that devices operate with the intended settings and ignore test data.

#### Acceptance Criteria

1. THE Pico_2W_Device SHALL prioritize configuration sources in this order: Django server config, local wifi_config.json, secrets.py
2. WHEN evaluating wifi_config.json, THE Pico_2W_Device SHALL reject configurations containing dummy values like "test_ssid", "test_password", or "YOUR_API_KEY_HERE"
3. WHEN evaluating secrets.py, THE Pico_2W_Device SHALL reject configurations containing sample placeholder values
4. WHEN a higher priority source is invalid or contains dummy data, THE Pico_2W_Device SHALL fall back to the next valid source
5. WHEN all configuration sources contain invalid or dummy data, THE Pico_2W_Device SHALL activate Setup_AP mode

### Requirement 3: Setup AP Web Interface

**User Story:** As a device operator, I want to configure WiFi and server settings through a web interface when the device is in Setup AP mode, so that I can update device configuration without code changes.

#### Acceptance Criteria

1. WHEN Setup_AP is active, THE Pico_2W_Device SHALL serve a web interface at IP address 192.168.4.1
2. WHEN a user accesses the web interface, THE Setup_AP SHALL display forms for WiFi credentials, server settings, device settings, and API key configuration
3. WHEN a user submits valid configuration through the web interface, THE Setup_AP SHALL save the settings to wifi_config.json
4. WHEN configuration is saved successfully, THE Setup_AP SHALL trigger a device reconnection attempt using the new settings
5. WHEN the web interface saves configuration, THE Pico_2W_Device SHALL log the configuration update with timestamp and source

### Requirement 4: Django Admin Integration

**User Story:** As a system administrator, I want to manage device configurations centrally through Django admin, so that I can update multiple devices remotely without individual device access.

#### Acceptance Criteria

1. THE Django_Server SHALL provide a DeviceConfig model accessible through Django admin interface
2. THE Django_Server SHALL expose an API endpoint at /booking/api/iot/config/ for device configuration retrieval
3. WHEN a device requests configuration, THE Django_Server SHALL return WiFi, server, device, and API key settings in JSON format
4. THE Django_Server SHALL maintain backward compatibility with existing config_endpoint responses
5. WHEN device configuration is updated in Django admin, THE changes SHALL be available to devices on their next configuration request

### Requirement 5: Configuration Persistence and Logging

**User Story:** As a developer, I want comprehensive logging of configuration decisions and file operations, so that I can troubleshoot configuration issues and understand device behavior.

#### Acceptance Criteria

1. THE Pico_2W_Device SHALL log which configuration source was selected and why other sources were rejected
2. THE Pico_2W_Device SHALL log the specific reason when Setup_AP mode is activated
3. WHEN processing configuration files, THE Pico_2W_Device SHALL ignore macOS ._ files during file operations
4. THE Pico_2W_Device SHALL maintain secrets.py as a functional fallback even when it contains sample values
5. THE Pico_2W_Device SHALL log all WiFi connection attempts, failures, and successful connections with timestamps

### Requirement 6: System Reliability and Backward Compatibility

**User Story:** As a system maintainer, I want the enhanced system to work with existing code structure and maintain reliability, so that deployment doesn't break existing functionality.

#### Acceptance Criteria

1. THE enhanced system SHALL preserve existing function names: enter_setup_mode(), DjangoAPIClient, and code.py structure
2. THE enhanced system SHALL maintain existing file names and endpoint compatibility
3. THE enhanced system SHALL NOT use timeout arguments in urequests calls (CircuitPython limitation)
4. WHEN making HTTP requests, THE Pico_2W_Device SHALL handle network timeouts through CircuitPython's default mechanisms
5. THE enhanced system SHALL maintain backward compatibility with existing configuration response formats

### Requirement 7: Configuration File Management

**User Story:** As a device operator, I want the system to handle configuration files robustly, so that file corruption or invalid data doesn't permanently disable the device.

#### Acceptance Criteria

1. WHEN reading wifi_config.json, THE Pico_2W_Device SHALL validate JSON structure and reject malformed files
2. WHEN writing wifi_config.json, THE Pico_2W_Device SHALL create a backup of the existing file before overwriting
3. WHEN a configuration file is corrupted or unreadable, THE Pico_2W_Device SHALL log the error and fall back to the next priority source
4. THE Pico_2W_Device SHALL create wifi_config.json with proper JSON formatting when saving new configurations
5. WHEN configuration files are missing, THE Pico_2W_Device SHALL handle the absence gracefully and proceed with available sources