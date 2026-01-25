"""
Unit tests for server configuration validation.

Tests Nginx configuration parsing and systemd service file syntax.
Validates: Requirements 6.1, 6.2
"""
import os
import re
import unittest
from pathlib import Path


class ServerConfigurationTest(unittest.TestCase):
    """
    Unit tests for server configuration files.
    """

    def setUp(self):
        self.config_dir = Path(__file__).parent.parent / 'config'
        self.nginx_config = self.config_dir / 'nginx' / 'staging.conf'
        self.gunicorn_config = self.config_dir / 'gunicorn' / 'staging.conf.py'
        self.systemd_config = self.config_dir / 'systemd' / 'newfuhi-staging.service'

    def test_nginx_config_exists(self):
        """Test that Nginx configuration file exists."""
        self.assertTrue(self.nginx_config.exists(), "Nginx config file should exist")

    def test_nginx_config_syntax(self):
        """Test Nginx configuration syntax and required directives."""
        with open(self.nginx_config, 'r') as f:
            content = f.read()

        # Test required server block
        self.assertIn('server {', content, "Should contain server block")
        
        # Test listen directive
        self.assertIn('listen 80;', content, "Should listen on port 80")
        
        # Test server_name
        self.assertIn('server_name', content, "Should have server_name directive")
        
        # Test proxy_pass
        self.assertIn('proxy_pass http://127.0.0.1:8000;', content, "Should proxy to Gunicorn")
        
        # Test static files location
        self.assertIn('location /static/', content, "Should serve static files")
        
        # Test security headers
        security_headers = [
            'X-Frame-Options',
            'X-Content-Type-Options',
            'X-XSS-Protection',
            'X-Robots-Tag'
        ]
        for header in security_headers:
            self.assertIn(header, content, f"Should include {header} security header")

    def test_nginx_privacy_controls(self):
        """Test Nginx privacy control configuration."""
        with open(self.nginx_config, 'r') as f:
            content = f.read()

        # Test IP allowlist
        self.assertIn('allow', content, "Should have IP allowlist")
        self.assertIn('deny all;', content, "Should deny all by default")
        
        # Test BasicAuth
        self.assertIn('auth_basic', content, "Should have BasicAuth configured")
        self.assertIn('auth_basic_user_file', content, "Should reference htpasswd file")
        
        # Test robots.txt
        self.assertIn('location = /robots.txt', content, "Should serve robots.txt")
        self.assertIn('Disallow: /', content, "Should disallow all in robots.txt")

    def test_gunicorn_config_exists(self):
        """Test that Gunicorn configuration file exists."""
        self.assertTrue(self.gunicorn_config.exists(), "Gunicorn config file should exist")

    def test_gunicorn_config_syntax(self):
        """Test Gunicorn configuration syntax and required settings."""
        with open(self.gunicorn_config, 'r') as f:
            content = f.read()

        # Test required settings
        required_settings = [
            'bind = "127.0.0.1:8000"',
            'workers =',
            'worker_class =',
            'timeout =',
            'user = "newfuhi"',
            'group = "newfuhi"',
            'logfile =',
            'loglevel ='
        ]
        
        for setting in required_settings:
            self.assertIn(setting, content, f"Should contain {setting}")

    def test_gunicorn_config_python_syntax(self):
        """Test that Gunicorn config is valid Python."""
        try:
            with open(self.gunicorn_config, 'r') as f:
                code = f.read()
            compile(code, str(self.gunicorn_config), 'exec')
        except SyntaxError as e:
            self.fail(f"Gunicorn config has syntax error: {e}")

    def test_systemd_service_exists(self):
        """Test that systemd service file exists."""
        self.assertTrue(self.systemd_config.exists(), "systemd service file should exist")

    def test_systemd_service_syntax(self):
        """Test systemd service file syntax and required sections."""
        with open(self.systemd_config, 'r') as f:
            content = f.read()

        # Test required sections
        required_sections = ['[Unit]', '[Service]', '[Install]']
        for section in required_sections:
            self.assertIn(section, content, f"Should contain {section} section")

        # Test required Unit directives
        unit_directives = ['Description=', 'After=network.target']
        for directive in unit_directives:
            self.assertIn(directive, content, f"Should contain {directive}")

        # Test required Service directives
        service_directives = [
            'Type=notify',
            'User=newfuhi',
            'Group=newfuhi',
            'ExecStart=',
            'Restart=always',
            'EnvironmentFile='
        ]
        for directive in service_directives:
            self.assertIn(directive, content, f"Should contain {directive}")

        # Test Install section
        self.assertIn('WantedBy=multi-user.target', content, 
                     "Should be wanted by multi-user.target")

    def test_systemd_service_security(self):
        """Test systemd service security settings."""
        with open(self.systemd_config, 'r') as f:
            content = f.read()

        # Test security directives
        security_directives = [
            'NoNewPrivileges=true',
            'PrivateTmp=true',
            'ProtectSystem=strict',
            'ProtectHome=true'
        ]
        
        for directive in security_directives:
            self.assertIn(directive, content, f"Should contain security directive {directive}")

    def test_systemd_service_paths(self):
        """Test systemd service file paths are consistent."""
        with open(self.systemd_config, 'r') as f:
            content = f.read()

        # Test working directory
        self.assertIn('WorkingDirectory=/var/www/newfuhi', content,
                     "Should set correct working directory")
        
        # Test environment file path
        self.assertIn('EnvironmentFile=/var/www/newfuhi/.env.staging', content,
                     "Should reference staging environment file")
        
        # Test ExecStart path
        self.assertIn('/var/www/newfuhi/venv/bin/gunicorn', content,
                     "Should use correct gunicorn path")

    def test_log_configuration_consistency(self):
        """Test that log paths are consistent across configurations."""
        # Read all config files
        configs = {}
        for config_file in [self.nginx_config, self.gunicorn_config, self.systemd_config]:
            with open(config_file, 'r') as f:
                configs[config_file.name] = f.read()

        # Test log directory consistency
        log_patterns = {
            'nginx': r'/var/log/nginx/newfuhi-staging',
            'gunicorn': r'/var/log/newfuhi/',
            'systemd': r'SyslogIdentifier=newfuhi-staging'
        }

        nginx_content = configs['staging.conf']
        gunicorn_content = configs['staging.conf.py']
        systemd_content = configs['newfuhi-staging.service']

        # Check Nginx logs
        self.assertRegex(nginx_content, log_patterns['nginx'],
                        "Nginx should log to correct directory")
        
        # Check Gunicorn logs
        self.assertRegex(gunicorn_content, log_patterns['gunicorn'],
                        "Gunicorn should log to correct directory")
        
        # Check systemd identifier
        self.assertRegex(systemd_content, log_patterns['systemd'],
                        "systemd should have correct syslog identifier")

    def test_port_consistency(self):
        """Test that port configuration is consistent between Nginx and Gunicorn."""
        with open(self.nginx_config, 'r') as f:
            nginx_content = f.read()
        
        with open(self.gunicorn_config, 'r') as f:
            gunicorn_content = f.read()

        # Extract ports
        nginx_proxy_match = re.search(r'proxy_pass http://127\.0\.0\.1:(\d+);', nginx_content)
        gunicorn_bind_match = re.search(r'bind = "127\.0\.0\.1:(\d+)"', gunicorn_content)

        self.assertIsNotNone(nginx_proxy_match, "Should find proxy_pass port in Nginx config")
        self.assertIsNotNone(gunicorn_bind_match, "Should find bind port in Gunicorn config")

        nginx_port = nginx_proxy_match.group(1)
        gunicorn_port = gunicorn_bind_match.group(1)

        self.assertEqual(nginx_port, gunicorn_port,
                        "Nginx proxy port should match Gunicorn bind port")


if __name__ == '__main__':
    unittest.main()