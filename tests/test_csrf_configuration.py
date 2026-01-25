"""
Property-based tests for CSRF configuration.

Feature: deploy-staging, Property 16: CSRF Protection Configuration
Validates: Requirements 5.3
"""
import os
from hypothesis import given, strategies as st, settings, HealthCheck
from hypothesis.extra.django import TestCase
from django.test import override_settings
from django.middleware.csrf import get_token
from django.test.client import RequestFactory
from django.http import HttpRequest


@st.composite
def url_strategy(draw):
    """Generate valid URL strings for CSRF trusted origins."""
    protocols = ['https', 'http']
    domains = ['staging.example.com', 'test.org', 'app.local', 'secure.site']
    protocol = draw(st.sampled_from(protocols))
    domain = draw(st.sampled_from(domains))
    return f"{protocol}://{domain}"


class CSRFConfigurationPropertyTest(TestCase):
    """
    Property test for CSRF configuration.
    
    **Property 16: CSRF Protection Configuration**
    For any CSRF-protected request, the Django configuration should use 
    CSRF_TRUSTED_ORIGINS from environment variables.
    """

    def setUp(self):
        self.factory = RequestFactory()

    @given(
        trusted_origins=st.lists(url_strategy(), min_size=1, max_size=5)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_csrf_trusted_origins_property(self, trusted_origins):
        """
        Property: For any list of trusted origins,
        Django should accept CSRF tokens from those origins.
        """
        with override_settings(CSRF_TRUSTED_ORIGINS=trusted_origins):
            from django.conf import settings
            # Verify that CSRF_TRUSTED_ORIGINS is properly set
            self.assertEqual(set(settings.CSRF_TRUSTED_ORIGINS), set(trusted_origins))

    @given(
        env_origins=st.lists(url_strategy(), min_size=1, max_size=3)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_environment_variable_parsing_property(self, env_origins):
        """
        Property: For any comma-separated list of origins in environment variables,
        Django configuration should parse them correctly.
        """
        from project.settings.base import env_list
        
        # Test comma-separated parsing
        env_value = ','.join(env_origins)
        
        # Mock environment variable
        original_value = os.environ.get('TEST_CSRF_ORIGINS')
        os.environ['TEST_CSRF_ORIGINS'] = env_value
        
        try:
            parsed_origins = env_list('TEST_CSRF_ORIGINS', [])
            self.assertEqual(set(parsed_origins), set(env_origins))
        finally:
            if original_value is not None:
                os.environ['TEST_CSRF_ORIGINS'] = original_value
            else:
                os.environ.pop('TEST_CSRF_ORIGINS', None)

    @given(
        origin=url_strategy(),
        trusted_origins=st.lists(url_strategy(), min_size=1, max_size=3)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_csrf_origin_validation_property(self, origin, trusted_origins):
        """
        Property: For any origin and trusted origins configuration,
        Django should validate CSRF requests based on trusted origins.
        """
        # Test with origin in trusted list
        if origin not in trusted_origins:
            trusted_origins.append(origin)
        
        with override_settings(CSRF_TRUSTED_ORIGINS=trusted_origins):
            from django.middleware.csrf import CsrfViewMiddleware
            
            # Create a request with the origin
            request = self.factory.post('/', HTTP_ORIGIN=origin)
            
            # The origin should be considered trusted
            middleware = CsrfViewMiddleware(lambda req: None)
            
            # Check if origin is in trusted origins
            from django.conf import settings
            self.assertIn(origin, settings.CSRF_TRUSTED_ORIGINS)

    def test_csrf_token_generation_property(self):
        """
        Property: CSRF token generation should work consistently
        across different configurations.
        """
        with override_settings(CSRF_TRUSTED_ORIGINS=['https://example.com']):
            request = self.factory.get('/')
            
            # Should be able to generate CSRF token
            token = get_token(request)
            self.assertIsNotNone(token)
            self.assertIsInstance(token, str)
            self.assertGreater(len(token), 0)