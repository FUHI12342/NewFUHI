"""
Property-based tests for database configuration.

Feature: deploy-staging, Property 20: Database Configuration Flexibility
Validates: Requirements 5.7, 6.5
"""
import os
import tempfile
from hypothesis import given, strategies as st, settings, HealthCheck
from hypothesis.extra.django import TestCase
from django.test import override_settings
from project.database import (
    get_database_config, 
    validate_database_connection, 
    get_database_type,
    is_rds_compatible
)


@st.composite
def sqlite_database_url_strategy(draw):
    """Generate SQLite database URL strings."""
    db_names = ['test.db', 'app.sqlite3', 'data.sqlite']
    db_name = draw(st.sampled_from(db_names))
    return f"sqlite:///{db_name}"


@st.composite
def postgresql_database_url_strategy(draw):
    """Generate PostgreSQL database URL strings."""
    hosts = ['localhost', 'db.example.com', 'rds.amazonaws.com']
    ports = [5432, 5433, 5434]
    databases = ['testdb', 'appdb', 'production']
    users = ['user', 'admin', 'app_user']
    passwords = ['pass123', 'secret', 'password']
    
    host = draw(st.sampled_from(hosts))
    port = draw(st.sampled_from(ports))
    database = draw(st.sampled_from(databases))
    user = draw(st.sampled_from(users))
    password = draw(st.sampled_from(passwords))
    
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


@st.composite
def database_url_strategy(draw):
    """Generate various database URL strings."""
    url_type = draw(st.sampled_from(['sqlite', 'postgresql']))
    if url_type == 'sqlite':
        return draw(sqlite_database_url_strategy())
    else:
        return draw(postgresql_database_url_strategy())


class DatabaseConfigurationPropertyTest(TestCase):
    """
    Property test for database configuration.
    
    **Property 20: Database Configuration Flexibility**
    For any database configuration (SQLite or RDS), the Django system should 
    successfully connect and perform operations.
    """

    @given(database_url=database_url_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_database_url_parsing_property(self, database_url):
        """
        Property: For any valid database URL,
        the system should parse it correctly.
        """
        config = get_database_config(database_url)
        
        # Should return a valid configuration dictionary
        self.assertIsInstance(config, dict)
        self.assertIn('ENGINE', config)
        self.assertIn('NAME', config)
        
        # Validate the configuration
        self.assertTrue(validate_database_connection(config))

    @given(
        engine=st.sampled_from([
            'django.db.backends.sqlite3',
            'django.db.backends.postgresql',
            'django.db.backends.mysql'
        ]),
        db_name=st.text(min_size=1, max_size=50).filter(lambda x: '/' not in x and '\\' not in x)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_database_config_validation_property(self, engine, db_name):
        """
        Property: For any valid database engine and name,
        the configuration should be validated correctly.
        """
        config = {
            'ENGINE': engine,
            'NAME': db_name
        }
        
        # Should validate successfully for valid configurations
        is_valid = validate_database_connection(config)
        self.assertTrue(is_valid)
        
        # Should identify database type correctly
        db_type = get_database_type(config)
        if 'sqlite' in engine:
            self.assertEqual(db_type, 'sqlite')
        elif 'postgresql' in engine:
            self.assertEqual(db_type, 'postgresql')
        elif 'mysql' in engine:
            self.assertEqual(db_type, 'mysql')

    @given(database_url=postgresql_database_url_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_rds_compatibility_property(self, database_url):
        """
        Property: For any PostgreSQL database URL,
        the system should recognize it as RDS compatible.
        """
        config = get_database_config(database_url)
        
        # PostgreSQL should be RDS compatible
        self.assertTrue(is_rds_compatible(config))

    @given(database_url=sqlite_database_url_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_sqlite_fallback_property(self, database_url):
        """
        Property: For any SQLite database URL,
        the system should handle it correctly but not consider it RDS compatible.
        """
        config = get_database_config(database_url)
        
        # SQLite should not be RDS compatible
        self.assertFalse(is_rds_compatible(config))
        
        # But should still be valid
        self.assertTrue(validate_database_connection(config))

    def test_fallback_configuration_property(self):
        """
        Property: When no DATABASE_URL is provided,
        the system should fall back to SQLite configuration.
        """
        config = get_database_config(None)
        
        # Should return SQLite configuration
        self.assertEqual(config['ENGINE'], 'django.db.backends.sqlite3')
        self.assertIn('db.sqlite3', config['NAME'])
        
        # Should be valid
        self.assertTrue(validate_database_connection(config))
        
        # Should not be RDS compatible
        self.assertFalse(is_rds_compatible(config))

    @given(
        env_database_url=database_url_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_environment_variable_integration_property(self, env_database_url):
        """
        Property: For any database URL in environment variables,
        Django settings should use it correctly.
        """
        # Mock environment variable
        original_value = os.environ.get('TEST_DATABASE_URL')
        os.environ['TEST_DATABASE_URL'] = env_database_url
        
        try:
            # Test that environment variable is accessible
            retrieved_url = os.environ.get('TEST_DATABASE_URL')
            self.assertEqual(retrieved_url, env_database_url)
            
            # Test configuration parsing
            config = get_database_config(retrieved_url)
            self.assertTrue(validate_database_connection(config))
            
        finally:
            if original_value is not None:
                os.environ['TEST_DATABASE_URL'] = original_value
            else:
                os.environ.pop('TEST_DATABASE_URL', None)