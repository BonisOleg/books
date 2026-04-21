"""Production settings for Render (Web Service + Postgres + Cloudinary).

Філософія: модуль ВСЕ ОДНО має імпортуватися без помилок навіть якщо частина
секретів ще не задана — інакше падає `collectstatic` під час build (Render
виконує build до того, як stage env vars фіналізовано). Реальна валідація
обов'язкових ENV відбувається тільки коли запускається веб-процес.
"""
from __future__ import annotations

import os
import sys

import dj_database_url

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _env(name: str, default: str = '') -> str:
    """Read env var, повертає default замість того щоб падати."""
    return os.environ.get(name, default)


def _is_runtime() -> bool:
    """Чи працюємо ми зараз як веб-сервер / runserver / wsgi.

    Під час build-фази Render викликає `collectstatic`, `migrate`, `check` —
    у цих випадках ми НЕ маємо валити імпорт через відсутні рантайм-секрети.
    """
    argv = ' '.join(sys.argv)
    runtime_markers = ('runserver', 'gunicorn', 'uwsgi', 'daphne', 'uvicorn')
    return any(marker in argv for marker in runtime_markers)


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = False

# SECRET_KEY на Render генерується автоматично через `generateValue: true`.
# Дозволяємо тимчасовий fallback тільки під час build, щоб collectstatic не падав.
SECRET_KEY = _env('DJANGO_SECRET_KEY') or 'build-time-placeholder-not-used-at-runtime'

ALLOWED_HOSTS = [h.strip() for h in _env('DJANGO_ALLOWED_HOSTS').split(',') if h.strip()]

# Render автоматично виставляє RENDER_EXTERNAL_HOSTNAME для веб-сервісу.
RENDER_EXTERNAL_HOSTNAME = _env('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in _env('CSRF_TRUSTED_ORIGINS').split(',') if o.strip()
]
if RENDER_EXTERNAL_HOSTNAME:
    auto_origin = f'https://{RENDER_EXTERNAL_HOSTNAME}'
    if auto_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(auto_origin)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# DATABASE_URL інжектується Render Postgres. Локально під час build його може
# не бути → використовуємо безпечний sqlite-плейсхолдер тільки для імпорту.
_DATABASE_URL = _env('DATABASE_URL')
if _DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(
            _DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }

# ---------------------------------------------------------------------------
# Static (WhiteNoise) + Media (Cloudinary)
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    MIDDLEWARE[0],
    'whitenoise.middleware.WhiteNoiseMiddleware',
    *MIDDLEWARE[1:],
]

# Якщо CLOUDINARY_URL ще не заданий (наприклад під час першого build на Render,
# до того як секрети введені) — тимчасово вмикаємо FileSystemStorage, щоб
# `django_cleanup.apps.ready()` зміг імпортувати default storage без помилки.
# У runtime ця ситуація заборонена (див. блок `_is_runtime` нижче).
_CLOUDINARY_URL = _env('CLOUDINARY_URL')
_DEFAULT_STORAGE_BACKEND = (
    'cloudinary_storage.storage.MediaCloudinaryStorage'
    if _CLOUDINARY_URL
    else 'django.core.files.storage.FileSystemStorage'
)

STORAGES = {
    'default': {'BACKEND': _DEFAULT_STORAGE_BACKEND},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# Backward-compat для django-cloudinary-storage (читає legacy ключ).
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
DEFAULT_FILE_STORAGE = _DEFAULT_STORAGE_BACKEND

WHITENOISE_MAX_AGE = 60 * 60 * 24 * 30  # 30 днів
WHITENOISE_USE_FINDERS = False
WHITENOISE_AUTOREFRESH = False

CLOUDINARY_STORAGE = {'CLOUDINARY_URL': _CLOUDINARY_URL} if _CLOUDINARY_URL else {}

# ---------------------------------------------------------------------------
# Безпека (Django + рекомендації Render, квітень 2026)
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365  # 1 рік
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

# ---------------------------------------------------------------------------
# Email (Gmail SMTP, App Password)
# ---------------------------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_TIMEOUT = 15
EMAIL_HOST_USER = _env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = _env('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = _env('DEFAULT_FROM_EMAIL') or EMAIL_HOST_USER or 'webmaster@localhost'
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ---------------------------------------------------------------------------
# Logging (stdout → Render Logs)
# ---------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': _env('DJANGO_LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django.request': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'django.security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}

# ---------------------------------------------------------------------------
# Sentry (опційно)
# ---------------------------------------------------------------------------
SENTRY_DSN = _env('SENTRY_DSN').strip()
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=float(_env('SENTRY_TRACES_SAMPLE_RATE', '0.05')),
            send_default_pii=False,
            environment=_env('SENTRY_ENVIRONMENT', 'production'),
            release=_env('RENDER_GIT_COMMIT', 'unknown'),
        )
    except ImportError:
        pass

# ---------------------------------------------------------------------------
# Runtime-валідація: якщо нас запустив gunicorn/runserver — критичні секрети
# ОБОВ'ЯЗКОВІ. Падаємо швидко зі зрозумілим повідомленням.
# ---------------------------------------------------------------------------
if _is_runtime():
    _missing = [
        name for name in (
            'DJANGO_SECRET_KEY',
            'DJANGO_ALLOWED_HOSTS',
            'DATABASE_URL',
            'CLOUDINARY_URL',
            'EMAIL_HOST_USER',
            'EMAIL_HOST_PASSWORD',
        )
        if not os.environ.get(name)
    ]
    if _missing:
        raise RuntimeError(
            'Production runtime missing required env vars: '
            + ', '.join(_missing)
            + '. Задай їх у Render Dashboard → Environment.'
        )
