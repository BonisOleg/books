"""Production settings for Render (Web Service + Postgres + Cloudinary)."""
import os

import dj_database_url

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE, BASE_DIR

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = False

SECRET_KEY = os.environ['DJANGO_SECRET_KEY']

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')
    if h.strip()
]

# Render автоматично додає зовнішнє ім'я сервісу у RENDER_EXTERNAL_HOSTNAME —
# гарантуємо, що воно завжди допускається, навіть якщо ALLOWED_HOSTS не задано.
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if o.strip()
]
if RENDER_EXTERNAL_HOSTNAME:
    auto_origin = f'https://{RENDER_EXTERNAL_HOSTNAME}'
    if auto_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(auto_origin)

# ---------------------------------------------------------------------------
# Database (Render Postgres)
# ---------------------------------------------------------------------------
DATABASES = {
    'default': dj_database_url.config(
        env='DATABASE_URL',
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=True,
    )
}

# ---------------------------------------------------------------------------
# Static (WhiteNoise) + Media (Cloudinary)
# ---------------------------------------------------------------------------
# WhiteNoise має йти одразу після SecurityMiddleware.
MIDDLEWARE = [
    MIDDLEWARE[0],
    'whitenoise.middleware.WhiteNoiseMiddleware',
    *MIDDLEWARE[1:],
]

STORAGES = {
    'default': {
        'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Backward-compat для django-cloudinary-storage (читає legacy ключ).
# Можна прибрати, коли пакет повністю перейде на нову схему STORAGES.
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

WHITENOISE_MAX_AGE = 60 * 60 * 24 * 30  # 30 днів
WHITENOISE_USE_FINDERS = False
WHITENOISE_AUTOREFRESH = False

CLOUDINARY_STORAGE = {
    'CLOUDINARY_URL': os.environ['CLOUDINARY_URL'],
}

# ---------------------------------------------------------------------------
# Безпека (за документацією Django + рекомендаціями Render, квітень 2026)
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

# Argon2 — основний хешер (паролі), додатковий PBKDF2 для backward compatibility.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# Обмеження розміру upload (5 MB у пам'яті, далі — диск).
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
EMAIL_HOST_USER = os.environ['EMAIL_HOST_USER']
EMAIL_HOST_PASSWORD = os.environ['EMAIL_HOST_PASSWORD']
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ---------------------------------------------------------------------------
# Logging — структурований stdout, читається Render Logs.
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
        'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# ---------------------------------------------------------------------------
# Sentry (опційно — активується лише якщо задано SENTRY_DSN).
# ---------------------------------------------------------------------------
SENTRY_DSN = os.environ.get('SENTRY_DSN', '').strip()
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.05')),
            send_default_pii=False,
            environment=os.environ.get('SENTRY_ENVIRONMENT', 'production'),
            release=os.environ.get('RENDER_GIT_COMMIT', 'unknown'),
        )
    except ImportError:  # пакет ще не встановлено локально — не валимо запуск
        pass
