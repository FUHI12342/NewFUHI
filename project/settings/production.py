"""
Production environment settings for NewFUHI project.

Secure production settings with full security hardening.
"""
import os
from dotenv import load_dotenv
from .base import *

# Load production environment variables
load_dotenv(os.path.join(BASE_DIR, ".env.production"), override=False)

# Core settings - maximum security
SECRET_KEY = env_required("SECRET_KEY")
DEBUG = False  # Never True in production
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", [])

# CSRF trusted origins for production
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", [])

# Database configuration - RDS preferred
DATABASE_URL = env_required("DATABASE_URL")
import dj_database_url
DATABASES = {
    "default": dj_database_url.parse(DATABASE_URL)
}

# Static and media files
STATIC_ROOT = env_required("STATIC_ROOT")
MEDIA_ROOT = env_required("MEDIA_ROOT")

# Full security hardening
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"

# Production logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING")
LOG_FILE = os.getenv("LOG_FILE", "/var/log/newfuhi/django.log")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_FILE,
            "maxBytes": 1024*1024*10,  # 10MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file", "console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "booking": {
            "handlers": ["file", "console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["file", "console"],
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

# Gemini AI Chat
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Email settings
DEFAULT_FROM_EMAIL = env_required("DEFAULT_FROM_EMAIL")
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

# Log production settings loaded
import logging
logger = logging.getLogger(__name__)
logger.info("Production settings loaded (DEBUG=%s)", DEBUG)