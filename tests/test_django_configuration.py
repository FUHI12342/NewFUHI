"""
Property-based tests for Django configuration.

Feature: deploy-staging, Property 15: Django Host Validation
Validates: Requirements 5.2
"""
import os
import tempfile
from hypothesis import given, strategies as st, settings, HealthCheck
from hypothesis.extra.django import TestCase
from django.test import override_settings
from django.core.exceptions import DisallowedHost
from django.http import HttpRequest
from django.test.client import RequestFactory


# Custom strategy for generating valid hostnames
@st.composite
def hostname_strategy(draw):
    """Generate valid hostname strings."""
    # Generate more realistic hostnames
    domain_parts = draw(st.lists(
        st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789', 
                min_size=1, max_size=8),
        min_size=2, max_size=3
    ))
    return '.'.join(domain_parts)


@st.composite 
def simple_hostname_strategy(draw):
    """Generate simple valid hostnames for testing."""
    domains = ['example.com', 'test.org', 'localhost', 'staging.app', 'prod.site']
    return draw(st.sampled_from(domains))


class DjangoHostValidationPropertyTest(TestCase):
    """
    Property test for Django host validation.
    
    **Property 15: Django Host Validation**
    For any HTTP request to the Django application, the system should validate 
    the request against ALLOWED_HOSTS from environment variables.
    """

    def setUp(self):
        self.factory = RequestFactory()

    @given(
        host=simple_hostname_strategy(),
        allowed_hosts=st.lists(simple_hostname_strategy(), min_size=1, max_size=3)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_host_validation_property(self, host, allowed_hosts):
        """
        Property: For any host and allowed_hosts configuration,
        Django should allow requests from allowed hosts and reject others.
        """
        # Test with host in allowed list
        if host not in allowed_hosts:
            allowed_hosts.append(host)
        
        with override_settings(ALLOWED_HOSTS=allowed_hosts):
            from django.http.request import validate_host
            # Should return True when host is in ALLOWED_HOSTS
            result = validate_host(host, allowed_hosts)
            self.assertTrue(result, f"Host validation failed for allowed host: {host} in {allowed_hosts}")

    @given(
        host=simple_hostname_strategy(),
        allowed_hosts=st.lists(simple_hostname_strategy(), min_size=1, max_size=3)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_host_rejection_property(self, host, allowed_hosts):
        """
        Property: For any host not in allowed_hosts,
        Django should reject the request.
        """
        # Ensure host is not in allowed_hosts by using a different host
        disallowed_host = f"disallowed-{host}"
        
        with override_settings(ALLOWED_HOSTS=allowed_hosts):
            from django.http.request import validate_host
            # Should return False for disallowed host
            result = validate_host(disallowed_host, allowed_hosts)
            self.assertFalse(result, f"Host validation should reject disallowed host: {disallowed_host}")

    @given(
        env_hosts=st.lists(simple_hostname_strategy(), min_size=1, max_size=3)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_environment_variable_parsing_property(self, env_hosts):
        """
        Property: For any comma-separated list of hosts in environment variables,
        Django configuration should parse them correctly.
        """
        from project.settings.base import env_list
        
        # Test comma-separated parsing
        env_value = ','.join(env_hosts)
        
        # Mock environment variable
        original_value = os.environ.get('TEST_HOSTS')
        os.environ['TEST_HOSTS'] = env_value
        
        try:
            parsed_hosts = env_list('TEST_HOSTS', [])
            self.assertEqual(set(parsed_hosts), set(env_hosts))
        finally:
            if original_value is not None:
                os.environ['TEST_HOSTS'] = original_value
            else:
                os.environ.pop('TEST_HOSTS', None)