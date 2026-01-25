"""
Database configuration utilities for NewFUHI project.

Provides database configuration abstraction supporting both SQLite and RDS.
"""
import os
from typing import Dict, Any


def get_database_config(database_url: str = None) -> Dict[str, Any]:
    """
    Get database configuration from DATABASE_URL or fallback to SQLite.
    
    Args:
        database_url: Database URL string (optional)
        
    Returns:
        Django database configuration dictionary
    """
    if database_url:
        try:
            import dj_database_url
            return dj_database_url.parse(database_url)
        except ImportError:
            raise RuntimeError("dj-database-url package required for DATABASE_URL parsing")
    
    # Fallback to SQLite configuration
    from django.conf import settings
    base_dir = getattr(settings, 'BASE_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(base_dir, "db.sqlite3"),
    }


def validate_database_connection(database_config: Dict[str, Any]) -> bool:
    """
    Validate database connection configuration.
    
    Args:
        database_config: Django database configuration dictionary
        
    Returns:
        True if configuration is valid, False otherwise
    """
    required_keys = ['ENGINE', 'NAME']
    
    for key in required_keys:
        if key not in database_config:
            return False
    
    # Validate engine
    valid_engines = [
        'django.db.backends.sqlite3',
        'django.db.backends.postgresql',
        'django.db.backends.mysql',
    ]
    
    if database_config['ENGINE'] not in valid_engines:
        return False
    
    # Validate SQLite path
    if database_config['ENGINE'] == 'django.db.backends.sqlite3':
        db_path = database_config['NAME']
        if not db_path or not isinstance(db_path, str):
            return False
        
        # Check if directory exists for SQLite file
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            return False
    
    return True


def get_database_type(database_config: Dict[str, Any]) -> str:
    """
    Get database type from configuration.
    
    Args:
        database_config: Django database configuration dictionary
        
    Returns:
        Database type string ('sqlite', 'postgresql', 'mysql', 'unknown')
    """
    engine = database_config.get('ENGINE', '')
    
    if 'sqlite' in engine:
        return 'sqlite'
    elif 'postgresql' in engine:
        return 'postgresql'
    elif 'mysql' in engine:
        return 'mysql'
    else:
        return 'unknown'


def is_rds_compatible(database_config: Dict[str, Any]) -> bool:
    """
    Check if database configuration is RDS compatible.
    
    Args:
        database_config: Django database configuration dictionary
        
    Returns:
        True if RDS compatible, False otherwise
    """
    db_type = get_database_type(database_config)
    return db_type in ['postgresql', 'mysql']