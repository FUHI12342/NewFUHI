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

# Database configuration
# SQLite (current) or DATABASE_URL (future RDS migration)
_db_url = os.getenv("DATABASE_URL")
if _db_url:
    import dj_database_url
    DATABASES = {"default": dj_database_url.parse(_db_url)}
else:
    DATABASES = {
        "default": {
            "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
            "NAME": os.getenv("DB_NAME", os.path.join(BASE_DIR, "db.sqlite3")),
        }
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
# HSTS is set by Nginx to avoid duplicate headers
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True
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

# LINE OAuth settings (set real values in .env.production)
LINE_CHANNEL_ID = os.getenv("LINE_CHANNEL_ID", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_REDIRECT_URL = os.getenv("LINE_REDIRECT_URL", "https://timebaibai.com/booking/login/line/success/")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN", "")

# Payment settings
PAYMENT_API_KEY = os.getenv("PAYMENT_API_KEY", "")
PAYMENT_API_URL = os.getenv("PAYMENT_API_URL", "")

# Webhook settings
WEBHOOK_URL_BASE = os.getenv("WEBHOOK_URL_BASE", "https://timebaibai.com/booking/coiney_webhook/")
CANCEL_URL = os.getenv("CANCEL_URL", "")

# Gemini AI Chat
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Email settings
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@timebaibai.com")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)

# Celery settings
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = env_list("CELERY_ACCEPT_CONTENT", ["json"])
CELERY_TASK_SERIALIZER = os.getenv("CELERY_TASK_SERIALIZER", "json")

# LINE user ID protection
LINE_USER_ID_ENCRYPTION_KEY = os.getenv("LINE_USER_ID_ENCRYPTION_KEY", "")
LINE_USER_ID_HASH_PEPPER = os.getenv("LINE_USER_ID_HASH_PEPPER", "")

# IoT encryption
IOT_ENCRYPTION_KEY = os.getenv("IOT_ENCRYPTION_KEY", "")

# Webhook secret
COINEY_WEBHOOK_SECRET = os.getenv("COINEY_WEBHOOK_SECRET", "")

# ── Startup validation ──
# Fail fast if critical secrets are missing
import logging
logger = logging.getLogger(__name__)

_REQUIRED_SECRETS = [
    "SECRET_KEY",
    "LINE_CHANNEL_ID",
    "LINE_CHANNEL_SECRET",
    "LINE_USER_ID_ENCRYPTION_KEY",
    "LINE_USER_ID_HASH_PEPPER",
]
_missing = [k for k in _REQUIRED_SECRETS if not os.getenv(k)]
if _missing:
    logger.critical("Missing required env vars: %s", ", ".join(_missing))
    raise RuntimeError(
        f"Production startup aborted — missing env vars: {', '.join(_missing)}"
    )

_WARN_SECRETS = [
    "PAYMENT_API_KEY",
    "COINEY_WEBHOOK_SECRET",
    "GEMINI_API_KEY",
    "IOT_ENCRYPTION_KEY",
]
_warn_missing = [k for k in _WARN_SECRETS if not os.getenv(k)]
if _warn_missing:
    logger.warning("Optional env vars not set (features may be limited): %s", ", ".join(_warn_missing))

# Ensure rate limiter bypass is never active in production
if os.getenv("TESTING"):
    raise RuntimeError("TESTING env var must never be set in production")

logger.info("Production settings loaded (DEBUG=%s)", DEBUG)