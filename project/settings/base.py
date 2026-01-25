"""
Base Django settings for NewFUHI project.

Common settings shared across all environments.
"""
import os
import datetime
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Environment variable helpers
def env_required(key: str) -> str:
    """Get required environment variable or raise error."""
    val = os.getenv(key)
    if val is None or str(val).strip() == "":
        raise RuntimeError(f"Missing required env var: {key}")
    return val

def env_bool(key: str, default: bool = False) -> bool:
    """Parse boolean environment variable."""
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")

def env_list(key: str, default=None):
    """Parse comma-separated list environment variable."""
    if default is None:
        default = []
    val = os.getenv(key)
    if not val:
        return default
    return [x.strip() for x in val.split(",") if x.strip()]

def env_int(key: str, default: int) -> int:
    """Parse integer environment variable safely."""
    val = os.getenv(key)
    if val is None or str(val).strip() == "":
        return default
    try:
        return int(str(val).strip())
    except ValueError:
        raise RuntimeError(f"Invalid int env var: {key}={val!r}")

# Application definition
INSTALLED_APPS = [
    "social_django",
    "booking.apps.BookingConfig",
    "booking.custom_auth.CustomAuthConfig",
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "social_core.backends.line.LineOAuth2",
]

ROOT_URLCONF = "project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(BASE_DIR, "templates"),
            os.path.join(BASE_DIR, "booking", "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "booking.context_processors.global_context",
                "social_django.context_processors.backends",
                "social_django.context_processors.login_redirect",
            ],
        },
    },
]

WSGI_APPLICATION = "project.wsgi.application"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

MEDIA_URL = "/media/"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Auth redirects
LOGIN_URL = "booking:login"
LOGIN_REDIRECT_URL = "booking:store_list"
LOGOUT_REDIRECT_URL = "booking:login"

# Public holidays (preserved from original settings)
PUBLIC_HOLIDAYS = [
    # 2020
    datetime.date(year=2020, month=1, day=1),
    datetime.date(year=2020, month=1, day=13),
    datetime.date(year=2020, month=2, day=11),
    datetime.date(year=2020, month=2, day=23),
    datetime.date(year=2020, month=2, day=24),
    datetime.date(year=2020, month=3, day=20),
    datetime.date(year=2020, month=4, day=29),
    datetime.date(year=2020, month=5, day=3),
    datetime.date(year=2020, month=5, day=4),
    datetime.date(year=2020, month=5, day=5),
    datetime.date(year=2020, month=7, day=20),
    datetime.date(year=2020, month=8, day=11),
    datetime.date(year=2020, month=9, day=21),
    datetime.date(year=2020, month=9, day=22),
    datetime.date(year=2020, month=10, day=12),
    datetime.date(year=2020, month=11, day=3),
    datetime.date(year=2020, month=11, day=23),
    # 2021
    datetime.date(year=2021, month=1, day=1),
    datetime.date(year=2021, month=1, day=11),
    datetime.date(year=2021, month=2, day=11),
    datetime.date(year=2021, month=2, day=23),
    datetime.date(year=2021, month=3, day=20),
    datetime.date(year=2021, month=4, day=29),
    datetime.date(year=2021, month=5, day=3),
    datetime.date(year=2021, month=5, day=4),
    datetime.date(year=2021, month=5, day=5),
    datetime.date(year=2021, month=7, day=19),
    datetime.date(year=2021, month=8, day=11),
    datetime.date(year=2021, month=9, day=20),
    datetime.date(year=2021, month=9, day=23),
    datetime.date(year=2021, month=10, day=11),
    datetime.date(year=2021, month=11, day=3),
    datetime.date(year=2021, month=11, day=23),
]