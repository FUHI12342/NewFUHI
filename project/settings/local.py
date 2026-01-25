"""
Local development settings for NewFUHI project.

Settings for local development environment.
"""
import os
from dotenv import load_dotenv
from .base import *

# Load local environment variables
ENV = os.getenv("ENV", "local").strip().lower()
env_candidates = [
    os.path.join(BASE_DIR, f".env.{ENV}"),
    os.path.join(BASE_DIR, ".env.local"),
    os.path.join(BASE_DIR, ".env"),
]

_loaded = False
for p in env_candidates:
    if os.path.exists(p):
        load_dotenv(p, override=False)
        _loaded = True
        break

# Core settings
SECRET_KEY = env_required("SECRET_KEY")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", ["127.0.0.1", "localhost", "testserver"])

# Test environment additional hosts
import sys
if 'test' in sys.argv or 'shell' in sys.argv:
    if 'testserver' not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append('testserver')

# Database
DB_ENGINE = os.getenv("DB_ENGINE", "django.db.backends.sqlite3")
DB_NAME = os.getenv("DB_NAME", os.path.join(BASE_DIR, "db.sqlite3"))

# Support DATABASE_URL for RDS migration path
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    try:
        import dj_database_url
        DATABASES = {
            "default": dj_database_url.parse(DATABASE_URL)
        }
    except ImportError:
        # Fallback if dj_database_url not available
        DATABASES = {
            "default": {
                "ENGINE": DB_ENGINE,
                "NAME": DB_NAME,
            }
        }
else:
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": DB_NAME,
        }
    }

# Static and media files
STATIC_ROOT = os.getenv("STATIC_ROOT", os.path.join(BASE_DIR, "staticfiles"))
MEDIA_ROOT = os.getenv("MEDIA_ROOT", os.path.join(BASE_DIR, "media"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if DEBUG else "INFO")
LOG_FILE = os.getenv("LOG_FILE", os.path.join(BASE_DIR, "debug.log"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
        "file": {
            "level": LOG_LEVEL,
            "class": "logging.FileHandler",
            "filename": LOG_FILE,
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
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@example.com")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)

# Celery settings
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
accept_content = env_list("CELERY_ACCEPT_CONTENT", ["json"])
task_serializer = os.getenv("CELERY_TASK_SERIALIZER", "json")

# LINE user ID protection
LINE_USER_ID_ENCRYPTION_KEY = env_required("LINE_USER_ID_ENCRYPTION_KEY")
LINE_USER_ID_HASH_PEPPER = env_required("LINE_USER_ID_HASH_PEPPER")

# Log environment loading
import logging
logger = logging.getLogger(__name__)
logger.info("Local settings loaded (ENV=%s, DEBUG=%s, env_loaded=%s)", ENV, DEBUG, _loaded)