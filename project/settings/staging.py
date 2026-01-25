"""
Staging environment settings for NewFUHI project.

Production-like settings for staging environment with enhanced logging.
"""
import os
from dotenv import load_dotenv
from .base import *

# Load staging environment variables
load_dotenv(os.path.join(BASE_DIR, ".env.staging"), override=False)

# Core settings - production-like behavior
SECRET_KEY = env_required("SECRET_KEY")
DEBUG = False  # Always False for staging
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", [])

# CSRF trusted origins for staging
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", [])

# Database configuration with URL parsing support
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    # Parse DATABASE_URL for RDS compatibility
    import dj_database_url
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL)
    }
else:
    # Fallback to SQLite
    DB_ENGINE = os.getenv("DB_ENGINE", "django.db.backends.sqlite3")
    DB_NAME = os.getenv("DB_NAME", os.path.join(BASE_DIR, "db.sqlite3"))
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": DB_NAME,
        }
    }

# Static and media files
STATIC_ROOT = env_required("STATIC_ROOT")
MEDIA_ROOT = os.getenv("MEDIA_ROOT", os.path.join(BASE_DIR, "media"))

# Security settings for reverse proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Enhanced logging for staging observation
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "/var/log/newfuhi/django.log")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": LOG_FILE,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "booking": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": LOG_LEVEL,
    },
}

# LINE OAuth settings
LINE_CHANNEL_ID = env_required("LINE_CHANNEL_ID")
LINE_CHANNEL_SECRET = env_required("LINE_CHANNEL_SECRET")
LINE_REDIRECT_URL = env_required("LINE_REDIRECT_URL")
LINE_ACCESS_TOKEN = env_required("LINE_ACCESS_TOKEN")

# Payment settings
PAYMENT_API_KEY = env_required("PAYMENT_API_KEY")
PAYMENT_API_URL = env_required("PAYMENT_API_URL")

# Webhook settings
WEBHOOK_URL_BASE = env_required("WEBHOOK_URL_BASE")
CANCEL_URL = env_required("CANCEL_URL")

# Email settings
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@newfuhi.com")
EMAIL_HOST = env_required("EMAIL_HOST")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env_required("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env_required("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)

# Celery settings
CELERY_BROKER_URL = env_required("CELERY_BROKER_URL")
accept_content = env_list("CELERY_ACCEPT_CONTENT", ["json"])
task_serializer = os.getenv("CELERY_TASK_SERIALIZER", "json")

# LINE user ID protection
LINE_USER_ID_ENCRYPTION_KEY = env_required("LINE_USER_ID_ENCRYPTION_KEY")
LINE_USER_ID_HASH_PEPPER = env_required("LINE_USER_ID_HASH_PEPPER")

# Log staging settings loaded
import logging
logger = logging.getLogger(__name__)
logger.info("Staging settings loaded (DEBUG=%s)", DEBUG)