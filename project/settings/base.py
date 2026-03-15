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
    "jazzmin",
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
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "booking.middleware.SecurityAuditMiddleware",
]

X_FRAME_OPTIONS = "DENY"

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
                "django.template.context_processors.i18n",
                "booking.context_processors.global_context",
                "booking.context_processors.admin_user_flags",
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

LANGUAGES = [
    ("ja", "日本語"),
    ("en", "English"),
    ("zh-hant", "繁體中文"),
    ("zh-hans", "简体中文"),
    ("ko", "한국어"),
    ("es", "Español"),
    ("pt", "Português"),
]

LOCALE_PATHS = [os.path.join(BASE_DIR, "locale")]

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

MEDIA_URL = "/media/"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Auth redirects
LOGIN_URL = "booking:login"
LOGIN_REDIRECT_URL = "booking:login_redirect"
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


# ====================================
# django-jazzmin (Admin UI theme)
# ====================================
JAZZMIN_SETTINGS = {
    "site_title": "占いサロンチャンス 管理画面",
    "site_header": "占いサロンチャンス 管理画面",
    "site_brand": "占いサロンチャンス",
    "welcome_sign": "占いサロンチャンス 管理画面へようこそ",
    "copyright": "占いサロンチャンス",

    # サイドバーナビ設定
    "show_sidebar": True,
    "navigation_expanded": False,
    "icons": {
        "booking.Schedule": "fas fa-calendar-alt",
        "booking.Staff": "fas fa-users",
        "booking.Menu": "fas fa-utensils",
        "booking.Shop": "fas fa-store",
        "booking.ShiftPeriod": "fas fa-clock",
        "booking.ShiftAssignment": "fas fa-tasks",
        "booking.TableOrder": "fas fa-receipt",
        "auth.User": "fas fa-user",
        "auth.Group": "fas fa-users-cog",
    },

    # カスタムリンク（ダッシュボード等）
    "custom_links": {
        "booking": [{
            "name": "売上ダッシュボード",
            "url": "/admin/dashboard/sales/",
            "icon": "fas fa-chart-line",
        }, {
            "name": "デバッグパネル",
            "url": "/admin/debug/",
            "icon": "fas fa-bug",
        }],
    },

    "hide_apps": [],

    # トップメニュー
    "topmenu_links": [
        {"name": "ホーム", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "本番サイト", "url": "/", "new_window": True},
    ],

    # UI設定
    "changeform_format": "horizontal_tabs",
    "language_chooser": True,
    "custom_css": "css/jazzmin_overrides.css",
}

# ====================================
# Django REST Framework defaults
# ====================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "300/min",
    },
}

# ====================================
# Session & Cookie security
# ====================================
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 28800  # 8 hours
CSRF_COOKIE_HTTPONLY = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# ====================================
# Password hashing
# ====================================
# Argon2/BCrypt preferred when libraries are installed.
# PBKDF2 is always available as fallback.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": False,
    "accent": "accent-primary",
    "navbar": "navbar-dark navbar-primary",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-indigo",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-outline-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}