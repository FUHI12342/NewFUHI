# Design Document: Deploy Pipeline & Private Staging

## Overview

This design implements a comprehensive deployment pipeline and private staging environment for the NewFUHI Django project. The system provides automated CI/CD capabilities with GitHub Actions, staging-first deployment strategy, privacy controls, and production-ready infrastructure configuration.

The architecture follows a layered approach with clear separation between CI/CD pipeline, deployment mechanisms, infrastructure components, and security controls. The design prioritizes staging environment validation while maintaining existing functionality and preparing for future production deployment.

## Architecture

The system consists of five main architectural layers:

### 1. Source Control Layer
- **Git Workflow Management**: Branch protection, PR requirements, file size validation
- **Repository Structure**: Organized configuration files and documentation
- **Version Control**: Tag-based release management for production deployments

### 2. CI/CD Pipeline Layer
- **GitHub Actions**: Automated workflows for validation and deployment
- **Validation Pipeline**: Linting, type checking, testing, and Django checks
- **Deployment Triggers**: Branch-based automatic and manual deployment controls

### 3. Application Configuration Layer
- **Django Settings**: Environment-specific configuration with staging/production separation
- **Environment Management**: Secure handling of environment variables and secrets
- **Database Abstraction**: SQLite-to-RDS migration path

### 4. Infrastructure Layer
- **Web Server**: Nginx reverse proxy with SSL termination and static file serving
- **Application Server**: Gunicorn WSGI server with worker process management
- **Process Management**: systemd services for automatic startup and recovery
- **Operating System**: Ubuntu server with security hardening

### 5. Security and Privacy Layer
- **Access Control**: IP-based restrictions and BasicAuth for staging privacy
- **Secrets Management**: GitHub Secrets integration and server-side environment files
- **SSL/TLS**: HTTPS enforcement with proper proxy headers

## Components and Interfaces

### GitHub Actions Workflows

**PR Validation Workflow** (`pr-validation.yml`)
- Triggers: Pull request creation/updates to main/develop branches
- Actions: Checkout, Python setup, dependency installation, linting, type checking, testing
- Outputs: Validation status, test results, coverage reports
- Interface: GitHub API for status reporting

**Staging Deployment Workflow** (`deploy-staging.yml`)
- Triggers: Push to develop/staging branch
- Actions: Build validation, deployment to staging server, health checks
- Outputs: Deployment status, application health verification
- Interface: SSH connection to staging server, systemctl commands

**Production Deployment Workflow** (`deploy-production.yml`)
- Triggers: Manual dispatch, release tag creation (release-*)
- Actions: Production build, manual approval gate, deployment to production
- Outputs: Production deployment status
- Interface: SSH connection to production server (future)

### Django Configuration System

**Settings Architecture**
```python
# settings/base.py - Common settings
# settings/staging.py - Staging-specific overrides
# settings/production.py - Production-specific overrides
# settings/__init__.py - Environment detection and loading
```

**Environment Variable Interface**
- `DJANGO_ENVIRONMENT`: Determines which settings module to load
- `DJANGO_DEBUG`: Controls debug mode (False for staging/production)
- `ALLOWED_HOSTS`: Comma-separated list of allowed hostnames
- `CSRF_TRUSTED_ORIGINS`: Comma-separated list of trusted origins
- `DATABASE_URL`: Database connection string (SQLite file path or RDS URL)
- `SECRET_KEY`: Django secret key for cryptographic operations

### Infrastructure Components

**Nginx Configuration**
- Reverse proxy to Gunicorn on localhost:8000
- Static file serving from `/var/www/newfuhi/static/`
- SSL termination with proper headers
- Access logging and error handling
- Rate limiting and security headers

**Gunicorn Configuration**
- WSGI server binding to localhost:8000
- Worker process management (CPU cores * 2 + 1)
- Graceful reloading and error recovery
- Access and error logging
- Unix socket option for better performance

**systemd Service Configuration**
- `newfuhi-staging.service`: Main application service
- `newfuhi-staging-nginx.service`: Nginx service dependency
- Automatic startup, restart on failure
- Environment file loading
- User/group isolation for security

### Privacy and Security Controls

**Access Control System**
- IP allowlist configuration in Nginx
- BasicAuth fallback for authorized external access
- robots.txt with noindex directives
- Security headers (HSTS, CSP, X-Frame-Options)

**Secrets Management**
- GitHub Secrets for CI/CD pipeline credentials
- Server-side `.env.staging` file with restricted permissions
- Environment variable injection into systemd services
- Secure credential rotation procedures

## Data Models

### Configuration Data Models

**Environment Configuration**
```python
@dataclass
class EnvironmentConfig:
    name: str  # 'staging', 'production'
    debug: bool
    allowed_hosts: List[str]
    csrf_trusted_origins: List[str]
    database_url: str
    secret_key: str
    static_root: str
    log_level: str
```

**Deployment Configuration**
```python
@dataclass
class DeploymentConfig:
    environment: str
    server_host: str
    server_user: str
    deploy_path: str
    service_name: str
    nginx_config_path: str
    gunicorn_config_path: str
    env_file_path: str
```

**CI/CD Pipeline State**
```python
@dataclass
class PipelineState:
    workflow_name: str
    trigger_event: str
    branch: str
    commit_sha: str
    validation_status: str  # 'pending', 'success', 'failure'
    deployment_status: str  # 'pending', 'success', 'failure'
    test_results: Dict[str, Any]
    deployment_logs: List[str]
```

### Server Configuration Models

**Nginx Site Configuration**
```nginx
server {
    listen 80;
    server_name staging.newfuhi.com;
    
    # Privacy controls
    allow 192.168.1.0/24;  # Office network
    allow 10.0.0.0/8;      # VPN network
    deny all;
    
    # Basic auth fallback
    auth_basic "Staging Environment";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    # Static files
    location /static/ {
        alias /var/www/newfuhi/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Application proxy
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Gunicorn Configuration**
```python
# gunicorn.conf.py
bind = "127.0.0.1:8000"
workers = 3
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
user = "newfuhi"
group = "newfuhi"
tmp_upload_dir = None
logfile = "/var/log/newfuhi/gunicorn.log"
loglevel = "info"
access_logfile = "/var/log/newfuhi/access.log"
error_logfile = "/var/log/newfuhi/error.log"
```

**systemd Service Configuration**
```ini
[Unit]
Description=NewFUHI Django Application (Staging)
After=network.target postgresql.service
Requires=network.target

[Service]
Type=notify
User=newfuhi
Group=newfuhi
WorkingDirectory=/var/www/newfuhi
Environment=DJANGO_ENVIRONMENT=staging
EnvironmentFile=/var/www/newfuhi/.env.staging
ExecStart=/var/www/newfuhi/venv/bin/gunicorn --config gunicorn.conf.py newfuhi.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=3
KillMode=mixed
TimeoutStopSec=5

[Install]
WantedBy=multi-user.target
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Git Branch Protection Enforcement
*For any* attempt to push directly to main/master branches, the Git workflow should reject the push and require a pull request instead.
**Validates: Requirements 1.1**

### Property 2: Large File Rejection
*For any* file larger than 100MB added to the repository, the Git workflow should reject the commit and suggest alternative storage methods.
**Validates: Requirements 1.2**

### Property 3: File Type Validation
*For any* ZIP file or backup file committed to the repository, the Git workflow should generate warnings and suggest alternative storage methods.
**Validates: Requirements 1.3**

### Property 4: CI Pipeline Trigger
*For any* pull request created, the CI pipeline should automatically trigger validation checks including linting, type checking, and tests.
**Validates: Requirements 1.5, 4.1**

### Property 5: Staging Deployment Automation
*For any* code merge to develop/staging branch, the deployment system should automatically trigger staging environment deployment.
**Validates: Requirements 2.1, 4.3**

### Property 6: Existing Page Functionality Preservation
*For any* previously working page, after staging deployment the page should continue to return the same successful response status.
**Validates: Requirements 2.2, 2.3**

### Property 7: Incomplete Page Error Handling
*For any* incomplete or non-existent page accessed on staging, the system should return 404 status codes rather than 500 server errors.
**Validates: Requirements 2.4**

### Property 8: Post-Deployment Validation
*For any* completed deployment, the system should verify that Django management commands (`check`, `migrate`, `collectstatic`) execute successfully.
**Validates: Requirements 2.5, 8.3**

### Property 9: Access Control Enforcement
*For any* access attempt to the staging environment, unauthorized users should be blocked while authorized users should have full functionality.
**Validates: Requirements 3.1, 3.3**

### Property 10: Access Logging
*For any* access attempt to the staging environment, the system should log the attempt for monitoring purposes.
**Validates: Requirements 3.5**

### Property 11: CI Validation and Merge Control
*For any* pull request with validation failures, the CI pipeline should block merge and provide detailed error reports.
**Validates: Requirements 4.2**

### Property 12: Production Deployment Control
*For any* merge to main/master branch, the CI pipeline should require manual approval before allowing production deployment.
**Validates: Requirements 4.4**

### Property 13: Release Tag Deployment
*For any* tag matching the pattern "release-*", the CI pipeline should enable production deployment options.
**Validates: Requirements 4.5**

### Property 14: Unstable Test Handling
*For any* CI run with unstable tests, the pipeline should generate warnings but allow deployment if Django check passes.
**Validates: Requirements 4.6**

### Property 15: Django Host Validation
*For any* HTTP request to the Django application, the system should validate the request against ALLOWED_HOSTS from environment variables.
**Validates: Requirements 5.2**

### Property 16: CSRF Protection Configuration
*For any* CSRF-protected request, the Django configuration should use CSRF_TRUSTED_ORIGINS from environment variables.
**Validates: Requirements 5.3**

### Property 17: Proxy Header Handling
*For any* request processed behind a reverse proxy, the Django configuration should handle SECURE_PROXY_SSL_HEADER appropriately.
**Validates: Requirements 5.4**

### Property 18: Static File Management
*For any* static file serving operation, the Django configuration should use STATIC_ROOT and successfully execute collectstatic.
**Validates: Requirements 5.5**

### Property 19: Enhanced Logging
*For any* application event in staging environment, the Django configuration should provide enhanced logging for observation.
**Validates: Requirements 5.6**

### Property 20: Database Configuration Flexibility
*For any* database configuration (SQLite or RDS), the Django system should successfully connect and perform operations.
**Validates: Requirements 5.7, 6.5**

### Property 21: HTTP Request Routing
*For any* HTTP request to the server, the infrastructure stack should efficiently route it through Nginx to Gunicorn.
**Validates: Requirements 6.3**

### Property 22: Process Management and Recovery
*For any* application process crash, the systemd infrastructure should automatically restart the process and maintain service availability.
**Validates: Requirements 6.2, 6.4, 6.6**

### Property 23: Secrets Access in CI/CD
*For any* CI/CD pipeline execution, the security manager should successfully access required secrets through GitHub Secrets integration.
**Validates: Requirements 7.1**

### Property 24: Environment Variable Loading
*For any* staging server startup, the security manager should load environment variables from the server-side .env.staging file.
**Validates: Requirements 7.2**

### Property 25: Secret Protection in Logs
*For any* logging or error reporting scenario, the security manager should never expose sensitive data in logs or error messages.
**Validates: Requirements 7.3**

### Property 26: Secure Storage Management
*For any* sensitive configuration data (credentials, API keys), the security manager should provide secure storage and retrieval.
**Validates: Requirements 7.4**

### Property 27: File Permission Security
*For any* environment file creation, the security manager should ensure proper file permissions (600) are set.
**Validates: Requirements 7.5**

### Property 28: Deployment Mechanism Simplicity
*For any* deployment operation, the deploy system should use simple mechanisms (rsync/scp + systemctl restart) for reliability.
**Validates: Requirements 8.1**

### Property 29: Deployment Error Handling
*For any* deployment failure, the deploy system should provide clear error reporting and functional recovery procedures.
**Validates: Requirements 8.6**

## Error Handling

The deployment pipeline and staging environment implement comprehensive error handling across multiple layers:

### CI/CD Pipeline Error Handling
- **Validation Failures**: Failed linting, type checking, or tests block PR merges with detailed error reports
- **Deployment Failures**: Failed deployments trigger rollback procedures and notify administrators
- **Timeout Handling**: Long-running operations have configurable timeouts with graceful failure modes
- **Retry Logic**: Transient failures in deployment operations are automatically retried with exponential backoff

### Application Error Handling
- **Django Configuration Errors**: Invalid settings or missing environment variables are caught at startup
- **Database Connection Errors**: Connection failures are logged and trigger service restart via systemd
- **Static File Errors**: collectstatic failures are reported and prevent deployment completion
- **Permission Errors**: File permission issues are detected and reported with remediation instructions

### Infrastructure Error Handling
- **Process Crashes**: systemd automatically restarts failed processes with configurable retry limits
- **Nginx Errors**: Reverse proxy failures are logged and trigger health check alerts
- **Disk Space Issues**: Low disk space conditions are monitored and trigger cleanup procedures
- **Network Connectivity**: Connection failures between components trigger diagnostic logging

### Security Error Handling
- **Authentication Failures**: Invalid credentials are logged and rate-limited to prevent brute force attacks
- **Authorization Errors**: Access control violations are logged and blocked with appropriate HTTP status codes
- **Secret Access Errors**: Failed secret retrieval operations are logged without exposing sensitive data
- **SSL/TLS Errors**: Certificate and encryption issues are detected and reported for manual resolution

### Recovery Procedures
- **Rollback Mechanisms**: Failed deployments can be rolled back to previous working versions
- **Health Checks**: Automated health monitoring detects service degradation and triggers recovery
- **Manual Intervention**: Clear procedures for manual recovery when automated systems fail
- **Data Backup**: Database and configuration backups enable recovery from data corruption

## Testing Strategy

The deployment pipeline and staging environment require a dual testing approach combining unit tests for specific scenarios and property-based tests for comprehensive validation.

### Unit Testing Approach
Unit tests focus on specific examples, edge cases, and integration points:

- **Configuration Validation**: Test specific Django settings combinations and environment variable parsing
- **Deployment Scripts**: Test deployment script execution with known file structures and server states
- **Error Scenarios**: Test specific error conditions like missing files, invalid permissions, network failures
- **Integration Points**: Test interactions between Nginx, Gunicorn, and Django with known request patterns
- **Security Controls**: Test specific access control scenarios with known IP addresses and authentication states

### Property-Based Testing Approach
Property-based tests validate universal properties across all possible inputs:

- **Minimum 100 iterations per property test** to ensure comprehensive coverage through randomization
- **Git Workflow Properties**: Test branch protection and file validation with randomly generated repositories and file sets
- **Deployment Properties**: Test deployment consistency with randomly generated code changes and server states
- **Access Control Properties**: Test privacy controls with randomly generated IP addresses and request patterns
- **Configuration Properties**: Test Django configuration with randomly generated environment variable combinations
- **Infrastructure Properties**: Test process management with randomly generated load patterns and failure scenarios

### Property Test Configuration
Each property-based test must:
- Run minimum 100 iterations due to randomization requirements
- Reference its corresponding design document property in test comments
- Use tag format: **Feature: deploy-staging, Property {number}: {property_text}**
- Generate diverse test inputs to cover edge cases and boundary conditions
- Validate both success and failure scenarios where applicable

### Testing Framework Selection
- **Python**: Use `hypothesis` library for property-based testing with Django integration
- **JavaScript/TypeScript**: Use `fast-check` library for CI/CD pipeline testing
- **Shell Scripts**: Use `bats` (Bash Automated Testing System) for deployment script testing
- **Infrastructure**: Use `testinfra` for server configuration and service validation

### Test Environment Management
- **Isolated Test Environments**: Each test run uses isolated Docker containers or virtual machines
- **Test Data Generation**: Automated generation of test repositories, configurations, and server states
- **Cleanup Procedures**: Automatic cleanup of test artifacts and temporary resources
- **Parallel Execution**: Tests run in parallel where possible to reduce execution time

### Continuous Testing Integration
- **PR Validation**: All tests run automatically on pull request creation and updates
- **Staging Deployment**: Subset of tests run after each staging deployment to verify functionality
- **Scheduled Testing**: Full test suite runs on schedule to catch environmental drift
- **Performance Monitoring**: Test execution times are monitored to detect performance regressions

The combination of unit and property-based testing ensures both specific functionality validation and comprehensive correctness verification across all possible system states and inputs.