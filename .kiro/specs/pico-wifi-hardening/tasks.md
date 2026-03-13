# Implementation Plan: Pico 2 W WiFi Hardening System

## Overview

This implementation plan converts the WiFi hardening design into discrete Python coding tasks for both the CircuitPython device code and Django server integration. The approach maintains backward compatibility while adding robust configuration management, Setup AP fallback, and centralized device management.

## Tasks

- [x] 1. Set up project structure and core interfaces
  - Create directory structure for device and server components
  - Define core Python interfaces and data classes for configuration management
  - Set up testing framework with pytest and hypothesis for property-based testing
  - _Requirements: 6.1, 6.2_

- [x] 2. Implement configuration management system
  - [x] 2.1 Create DeviceConfig data class and validation
    - Implement DeviceConfig dataclass with validation methods
    - Add dummy data detection patterns and validation logic
    - _Requirements: 2.2, 2.3_
  
  - [x] 2.2 Write property test for dummy data detection
    - **Property 3: Dummy Data Detection and Rejection**
    - **Validates: Requirements 2.2, 2.3**
  
  - [x] 2.3 Implement ConfigSource interface and concrete sources
    - Create abstract ConfigSource base class
    - Implement DjangoConfigSource, LocalFileConfigSource, SecretsConfigSource
    - _Requirements: 2.1, 2.4_
  
  - [x] 2.4 Write property test for configuration source priority
    - **Property 2: Configuration Source Priority and Fallback**
    - **Validates: Requirements 2.1, 2.4**

- [x] 3. Implement WiFi management and failure tracking
  - [x] 3.1 Create WiFiManager class with connection logic
    - Implement WiFi connection attempts with failure counting
    - Add connection state management and Setup AP trigger logic
    - _Requirements: 1.1, 1.4_
  
  - [x] 3.2 Write property test for WiFi vs server failure isolation
    - **Property 4: WiFi vs Server Failure Isolation**
    - **Validates: Requirements 1.4**
  
  - [x] 3.3 Implement Setup AP activation decision logic
    - Add should_enter_setup_mode() method with all trigger conditions
    - Implement failure threshold checking and configuration validation
    - _Requirements: 1.1, 1.2, 2.5_
  
  - [x] 3.4 Write property test for Setup AP activation consistency
    - **Property 1: Setup AP Activation Consistency**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.5, 2.5**

- [x] 4. Checkpoint - Ensure core configuration and WiFi logic tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Setup AP and web interface
  - [x] 5.1 Create SetupAPHandler class
    - Implement access point creation with correct SSID/password format
    - Add web server initialization and request handling
    - _Requirements: 1.5, 3.1_
  
  - [x] 5.2 Implement web interface forms and handlers
    - Create HTML forms for WiFi, server, device, and API configuration
    - Add form validation and error handling
    - _Requirements: 3.2_
  
  - [x] 5.3 Implement configuration save and restart logic
    - Add configuration persistence to wifi_config.json with backup
    - Implement device reconnection trigger after configuration save
    - _Requirements: 3.3, 3.4_
  
  - [x] 5.4 Write property test for configuration persistence round trip
    - **Property 5: Configuration Persistence Round Trip**
    - **Validates: Requirements 3.3, 3.4**

- [x] 6. Implement file operations and error handling
  - [x] 6.1 Create robust file handling utilities
    - Implement JSON validation, backup creation, and error recovery
    - Add macOS ._ file filtering and missing file handling
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 5.3_
  
  - [x] 6.2 Write property test for file operation safety
    - **Property 9: File Operation Safety and Recovery**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**
  
  - [x] 6.3 Write property test for macOS file filtering
    - **Property 10: macOS File Filtering**
    - **Validates: Requirements 5.3**

- [x] 7. Implement logging system
  - [x] 7.1 Create comprehensive logging utilities
    - Implement event logging for configuration decisions, Setup AP activation, and WiFi events
    - Add timestamp and context information to all log entries
    - _Requirements: 5.1, 5.2, 5.5_
  
  - [x] 7.2 Write property test for comprehensive event logging
    - **Property 8: Comprehensive Event Logging**
    - **Validates: Requirements 5.1, 5.2, 5.5**

- [ ] 8. Implement Django server integration
  - [ ] 8.1 Create DeviceConfig Django model
    - Implement DeviceConfig model with all required fields
    - Add Django admin interface configuration
    - _Requirements: 4.1_
  
  - [ ] 8.2 Implement configuration API endpoint
    - Create /booking/api/iot/config/ endpoint with backward compatibility
    - Add JSON response formatting and error handling
    - _Requirements: 4.2, 4.3, 4.4_
  
  - [ ] 8.3 Write property test for Django API response format
    - **Property 6: Django API Response Format Consistency**
    - **Validates: Requirements 4.3, 4.4, 6.5**
  
  - [ ] 8.4 Write property test for configuration update propagation
    - **Property 7: Configuration Update Propagation**
    - **Validates: Requirements 4.5**

- [ ] 9. Implement CircuitPython constraints and compatibility
  - [ ] 9.1 Update HTTP request handling for CircuitPython
    - Ensure urequests calls don't include timeout arguments
    - Implement proper error handling for network timeouts
    - _Requirements: 6.3, 6.4_
  
  - [ ] 9.2 Implement secrets.py fallback functionality
    - Ensure secrets.py works as fallback even with sample values
    - Add proper fallback logic in configuration priority system
    - _Requirements: 5.4_
  
  - [ ] 9.3 Write property test for CircuitPython constraint compliance
    - **Property 11: CircuitPython Constraint Compliance**
    - **Validates: Requirements 6.3, 6.4**
  
  - [ ] 9.4 Write property test for secrets fallback functionality
    - **Property 12: Secrets Fallback Functionality**
    - **Validates: Requirements 5.4**

- [ ] 10. Integration and system wiring
  - [ ] 10.1 Create main device application (code.py)
    - Wire together ConfigurationManager, WiFiManager, and SetupAPHandler
    - Implement main application loop with proper error handling
    - _Requirements: 6.1_
  
  - [ ] 10.2 Integrate Django models and API with existing booking app
    - Add DeviceConfig to Django admin and wire API endpoint
    - Ensure backward compatibility with existing config_endpoint
    - _Requirements: 4.1, 4.2, 6.2, 6.5_
  
  - [ ] 10.3 Write integration tests for end-to-end functionality
    - Test complete WiFi connection flow with various configuration sources
    - Test Setup AP activation and web interface interaction
    - _Requirements: 1.1, 1.2, 1.4, 3.1, 3.2, 3.3, 3.4_

- [ ] 11. Final checkpoint - Ensure all tests pass and system integration works
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required for comprehensive system validation
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties using hypothesis library
- Unit tests validate specific examples and edge cases
- CircuitPython constraints (no timeout arguments) are enforced throughout
- Backward compatibility with existing Django booking app is maintained
- All file operations include proper error handling and backup mechanisms