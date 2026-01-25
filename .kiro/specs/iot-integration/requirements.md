# Requirements Document

## Introduction

This specification defines the requirements for integrating IoT implementation (IoTEvent/IoTDevice models) from local development environment into the main branch and EC2 production deployment. The local development environment contains a complete IoT implementation with models, migrations, API endpoints, admin interface, and frontend assets that need to be merged into the production codebase via proper Git workflow.

## Glossary

- **IoT_System**: The complete Internet of Things implementation including device management and event logging
- **Git_Workflow**: The standardized process of feature branch creation, pull request, and merge to main branch
- **EC2_Deployment**: The production environment running on Amazon EC2 requiring database migrations and service restarts
- **Migration_Files**: Django database migration files (0031 and 0032) that define IoT model schema changes
- **API_Endpoints**: REST API endpoints for IoT device communication and configuration
- **Admin_Interface**: Django admin interface for managing IoT devices and viewing event logs
- **Static_Assets**: CSS and JavaScript files for IoT admin interface functionality

## Requirements

### Requirement 1: Model Integration

**User Story:** As a developer, I want to integrate IoT models into the main codebase, so that the production system can manage IoT devices and events.

#### Acceptance Criteria

1. WHEN the IoT models are integrated, THE System SHALL include IoTDevice and IoTEvent models in booking/models.py
2. WHEN importing IoTEvent or IoTDevice, THE System SHALL successfully resolve the imports without ImportError
3. WHEN the models are loaded, THE System SHALL maintain all existing model relationships and constraints
4. WHEN python manage.py check is executed, THE System SHALL pass all model validation checks

### Requirement 2: Database Migration Integration

**User Story:** As a system administrator, I want to apply IoT database migrations, so that the production database schema supports IoT functionality.

#### Acceptance Criteria

1. WHEN migrations 0031 and 0032 are applied, THE System SHALL create IoTDevice and IoTEvent database tables
2. WHEN python manage.py migrate is executed, THE System SHALL complete successfully without errors
3. WHEN migrations are applied, THE System SHALL maintain backward compatibility with existing data
4. WHEN database indexes are created, THE System SHALL include all IoT-related performance indexes

### Requirement 3: API Endpoint Integration

**User Story:** As an IoT device, I want to communicate with the server via API endpoints, so that I can send sensor data and receive configuration updates.

#### Acceptance Criteria

1. WHEN IoT API endpoints are integrated, THE System SHALL provide /api/iot/events/ for event submission
2. WHEN IoT API endpoints are integrated, THE System SHALL provide /api/iot/config/ for device configuration
3. WHEN API requests use correct field names, THE System SHALL accept mq9, light, sound, temp, and hum parameters
4. WHEN API authentication is performed, THE System SHALL validate device external_id and api_key combinations
5. WHEN invalid API requests are received, THE System SHALL return appropriate HTTP error codes

### Requirement 4: Admin Interface Integration

**User Story:** As a system administrator, I want to manage IoT devices through the admin interface, so that I can configure devices and monitor events.

#### Acceptance Criteria

1. WHEN admin interface is accessed, THE System SHALL display IoTDevice and IoTEvent management pages
2. WHEN viewing IoT events, THE System SHALL provide auto-refresh functionality every 20 seconds
3. WHEN managing IoT devices, THE System SHALL allow configuration of device settings and thresholds
4. WHEN accessing MQ-9 graphs, THE System SHALL display sensor data visualization at /admin/iot/mq9/

### Requirement 5: Static Asset Integration

**User Story:** As a system administrator, I want IoT admin interface enhancements, so that I can effectively monitor and manage IoT devices.

#### Acceptance Criteria

1. WHEN IoT admin pages are loaded, THE System SHALL serve iot_event.css for styling
2. WHEN IoT event lists are displayed, THE System SHALL serve iot_event_autorefresh.js for auto-refresh functionality
3. WHEN static files are collected, THE System SHALL include all IoT-related CSS and JavaScript files
4. WHEN admin interface is accessed, THE System SHALL apply IoT-specific styling and behavior

### Requirement 6: Template Integration

**User Story:** As a system administrator, I want IoT-specific admin templates, so that I can view enhanced IoT device management interfaces.

#### Acceptance Criteria

1. WHEN IoT admin templates are integrated, THE System SHALL include iot_mq9_graph.html for sensor visualization
2. WHEN IoT event change list is accessed, THE System SHALL use custom template with auto-refresh messaging
3. WHEN templates are rendered, THE System SHALL display IoT-specific UI enhancements and functionality

### Requirement 7: Git Workflow Compliance

**User Story:** As a developer, I want to follow proper Git workflow, so that code changes are properly reviewed and integrated.

#### Acceptance Criteria

1. WHEN integrating IoT code, THE Git_Workflow SHALL create a feature branch from main
2. WHEN code is ready for integration, THE Git_Workflow SHALL create a pull request for review
3. WHEN pull request is approved, THE Git_Workflow SHALL merge changes to main branch
4. WHEN committing changes, THE Git_Workflow SHALL exclude db.sqlite3, .pem files, and build artifacts
5. WHEN merging is complete, THE Git_Workflow SHALL ensure main branch contains all IoT functionality

### Requirement 8: EC2 Deployment Process

**User Story:** As a system administrator, I want to deploy IoT integration to production, so that the live system supports IoT functionality.

#### Acceptance Criteria

1. WHEN deploying to EC2, THE EC2_Deployment SHALL execute git pull to update codebase
2. WHEN database changes are deployed, THE EC2_Deployment SHALL run python manage.py migrate successfully
3. WHEN static files are updated, THE EC2_Deployment SHALL run python manage.py collectstatic
4. WHEN deployment is complete, THE EC2_Deployment SHALL restart gunicorn service
5. WHEN services are restarted, THE EC2_Deployment SHALL verify IoT functionality is operational

### Requirement 9: API Field Compatibility

**User Story:** As an IoT device developer, I want consistent API field names, so that sensor data is properly processed.

#### Acceptance Criteria

1. WHEN IoT devices send sensor data, THE API_Endpoints SHALL accept 'mq9' field for gas sensor values
2. WHEN IoT devices send sensor data, THE API_Endpoints SHALL accept 'light' field for light sensor values
3. WHEN IoT devices send sensor data, THE API_Endpoints SHALL accept 'sound' field for sound sensor values
4. WHEN IoT devices send sensor data, THE API_Endpoints SHALL accept 'temp' field for temperature values
5. WHEN IoT devices send sensor data, THE API_Endpoints SHALL accept 'hum' field for humidity values
6. WHEN field name mismatches occur, THE API_Endpoints SHALL handle them gracefully without TypeError

### Requirement 10: System Validation

**User Story:** As a system administrator, I want to validate IoT integration, so that I can confirm all functionality works correctly.

#### Acceptance Criteria

1. WHEN system validation is performed, THE System SHALL pass python manage.py check without errors
2. WHEN database validation is performed, THE System SHALL complete python manage.py migrate without errors
3. WHEN import validation is performed, THE System SHALL successfully import IoTEvent and IoTDevice classes
4. WHEN API validation is performed, THE System SHALL accept POST requests to IoT endpoints with correct field names
5. WHEN model validation is performed, THE System SHALL create IoTEvent and IoTDevice instances without TypeError