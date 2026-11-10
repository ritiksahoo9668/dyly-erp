"""Base Django settings shared by every environment."""

from datetime import timedelta
from pathlib import Path

from kombu import Queue

from utils.env import env, env_bool, env_int, env_list

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = env("SECRET_KEY", "dev-only-change-me")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,backend")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "apps.common.apps.CommonConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.procurement.apps.ProcurementConfig",
    "apps.production.apps.ProductionConfig",
    "apps.sales.apps.SalesConfig",
    "apps.hr.apps.HrConfig",
    "apps.master.apps.MasterConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "erp"),
        "USER": env("POSTGRES_USER", "erp"),
        "PASSWORD": env("POSTGRES_PASSWORD", "erp"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", "redis://localhost:6379/0"),
    }
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Kolkata"
# Keep request-side publishing short if Redis is unreachable (mail enqueue then marks FAILED).
CELERY_BROKER_CONNECTION_TIMEOUT = 2
CELERY_BROKER_TRANSPORT_OPTIONS = {"socket_connect_timeout": 2}
CELERY_REDIS_SOCKET_CONNECT_TIMEOUT = 2
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# Email has its own queue so long jobs (e.g. Master Excel imports) cannot delay delivery.
# A worker started without ``-Q`` consumes every queue declared here; use ``-Q mail`` only
# for a dedicated mail worker.
CELERY_TASK_DEFAULT_QUEUE = "celery"
CELERY_TASK_QUEUES = (Queue("celery"), Queue("mail"))
CELERY_TASK_ROUTES = {
    "accounts.send_*": {"queue": "mail"},
    "common.mail.*": {"queue": "mail"},
}
CELERY_BEAT_SCHEDULE = {
    "accounts-expire-user-invitations": {
        "task": "accounts.expire_user_invitations",
        "schedule": 15 * 60,
    },
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Master Excel background import
MASTER_IMPORT_BATCH_SIZE = 500

# Material images
BACKEND_URL = env("BACKEND_URL", "http://localhost:8000").rstrip("/")
MATERIAL_IMAGE_MAX_BYTES = int(env("MATERIAL_IMAGE_MAX_BYTES", str(5 * 1024 * 1024)))
MATERIAL_IMAGE_MAX_PIXELS = int(env("MATERIAL_IMAGE_MAX_PIXELS", str(40_000_000)))
MATERIAL_IMAGE_THUMB_SIZE = int(env("MATERIAL_IMAGE_THUMB_SIZE", "480"))
MATERIAL_IMAGE_URL_MAX_LENGTH = 500
SERVE_MATERIAL_MEDIA = env_bool("SERVE_MATERIAL_MEDIA", True)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

PASSWORD_RESET_TIMEOUT = 3600

FRONTEND_URL = env("FRONTEND_URL", "") or "http://localhost:5173"

# Outgoing email (centralized in apps.common.mail). Credentials come only from the environment.
EMAIL_BACKEND = env("EMAIL_BACKEND", "") or "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", "") or "localhost"
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 15)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "") or "DYLY ERP <no-reply@localhost>"
SERVER_EMAIL = DEFAULT_FROM_EMAIL
USER_INVITE_EXPIRY_HOURS = env_int("USER_INVITE_EXPIRY_HOURS", 48)
CORS_ALLOWED_ORIGINS = list(
    dict.fromkeys(
        [
            FRONTEND_URL,
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
)
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "erp": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
