"""
Django settings module with environment-specific configuration.

Environment detection and loading logic.
"""
import os

# Determine environment from DJANGO_ENVIRONMENT variable
DJANGO_ENVIRONMENT = os.getenv("DJANGO_ENVIRONMENT", "local").strip().lower()

# Import appropriate settings module based on environment
if DJANGO_ENVIRONMENT == "production":
    from .production import *
elif DJANGO_ENVIRONMENT == "staging":
    from .staging import *
else:
    from .local import *

# Log which settings module was loaded
import logging
logger = logging.getLogger(__name__)
logger.info(f"Django settings loaded: {DJANGO_ENVIRONMENT}")