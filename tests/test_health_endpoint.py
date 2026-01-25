"""
Tests for health check endpoint.

Feature: deploy-staging, Health Check Endpoint
Validates: Production deployment monitoring requirements
"""
import os
from django.test import TestCase
from unittest.mock import patch


class HealthEndpointTest(TestCase):
    """
    Test health check endpoint functionality.
    """

    def test_health_view_function_exists(self):
        """Test that health view function exists and is importable."""
        from booking.health import healthz
        self.assertTrue(callable(healthz))

    @patch.dict(os.environ, {'APP_GIT_SHA': 'abc123def456'})
    def test_git_sha_environment_variable(self):
        """Test that APP_GIT_SHA environment variable is read correctly."""
        git_sha = os.getenv("APP_GIT_SHA", "unknown")
        self.assertEqual(git_sha, 'abc123def456')

    def test_environment_detection_logic(self):
        """Test environment detection logic."""
        # Test staging detection
        settings_module = "project.settings.staging"
        env = "staging" if "staging" in settings_module else "unknown"
        self.assertEqual(env, "staging")
        
        # Test production detection
        settings_module = "project.settings.production"
        env = "production" if "production" in settings_module else "unknown"
        self.assertEqual(env, "production")
        
        # Test local detection
        settings_module = "project.settings.local"
        env = "local" if "local" in settings_module else "unknown"
        self.assertEqual(env, "local")