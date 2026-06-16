"""Production settings for Render (Web Service + Postgres + Cloudinary).

Філософія: сервіс ЗАВЖДИ повинен підніматися. Якщо якогось секрету ще немає
(CLOUDINARY_URL, SMTP, кастомний домен) — вмикаємо безпечний fallback і
лише пишемо WARNING у логи. Це дозволяє побачити сайт одразу після першого
деплою і поступово підключати інтеграції через Render Dashboard.
"""
from __future__ import annotations

import logging
import os

import dj_database_url

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE

_log = logging.getLogger(__name__)


def _env(name: str, default: str = '') -> str:
    return os.environ.get(name, default)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(',') if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = False

# DJANGO_SECRET_KEY на Render генерується автоматично (`generateValue: true`).
# Якщо чомусь відсутній — генеруємо одноразовий, щоб процес стартанув.
# WARNING: при рестарті ключ зміниться → сесії інвалідуються. Налаштуй ENV.
SECRET_KEY = _env('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    import secrets
    SECRET_KEY = secrets.token_urlsafe(64)
    _log.warning(
        'DJANGO_SECRET_KEY не задано — згенеровано тимчасовий. '
        'Сесії і signed cookies не переживуть рестарт.'
    )

# Render автоматично виставляє RENDER_EXTERNAL_HOSTNAME для веб-сервісу.
RENDER_EXTERNAL_HOSTNAME = _env('RENDER_EXTERNAL_HOSTNAME')

# Кастомний домен (наприклад ofion.com.ua) — задається вручну в Render Env Vars.
CUSTOM_DOMAIN = _env('CUSTOM_DOMAIN')

ALLOWED_HOSTS = _split_csv(_env('DJANGO_ALLOWED_HOSTS'))
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
if CUSTOM_DOMAIN:
    for _host in [CUSTOM_DOMAIN, f'www.{CUSTOM_DOMAIN}']:
        if _host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_host)
# Якщо нічого не задано — приймаємо .onrender.com (стандартний домен Render).
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['.onrender.com', 'localhost', '127.0.0.1']
    _log.warning(
        'DJANGO_ALLOWED_HOSTS не задано — використовую fallback %s', ALLOWED_HOSTS
    )

CSRF_TRUSTED_ORIGINS = _split_csv(_env('CSRF_TRUSTED_ORIGINS'))
if RENDER_EXTERNAL_HOSTNAME:
    auto_origin = f'https://{RENDER_EXTERNAL_HOSTNAME}'
    if auto_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(auto_origin)
if CUSTOM_DOMAIN:
    for _origin in [f'https://{CUSTOM_DOMAIN}', f'https://www.{CUSTOM_DOMAIN}']:
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)
if not any('onrender.com' in o for o in CSRF_TRUSTED_ORIGINS):
    CSRF_TRUSTED_ORIGINS.append('https://*.onrender.com')

# Публічний URL (фіди GMC, листи, посилання) — SITE_DOMAIN або CUSTOM_DOMAIN з Render.
_site_domain_env = _env('SITE_DOMAIN')
if _site_domain_env:
    SITE_DOMAIN = _site_domain_env
elif CUSTOM_DOMAIN:
    SITE_DOMAIN = CUSTOM_DOMAIN
elif RENDER_EXTERNAL_HOSTNAME:
    SITE_DOMAIN = RENDER_EXTERNAL_HOSTNAME

_site_protocol_env = _env('SITE_PROTOCOL')
if _site_protocol_env:
    SITE_PROTOCOL = _site_protocol_env
elif CUSTOM_DOMAIN or RENDER_EXTERNAL_HOSTNAME:
    SITE_PROTOCOL = 'https'

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
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
    # Render Postgres зазвичай інжектує DATABASE_URL автоматично.
    # Якщо ні — fallback на локальний sqlite (ephemeral, лише для smoke-тесту).
    from .base import BASE_DIR
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    _log.warning('DATABASE_URL не задано — тимчасово використовую sqlite. '
                 'Підключи Render Postgres у Dashboard.')

# ---------------------------------------------------------------------------
# Static (WhiteNoise) + Media (Cloudinary або FileSystem fallback)
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    MIDDLEWARE[0],
    'whitenoise.middleware.WhiteNoiseMiddleware',
    *MIDDLEWARE[1:],
]

_CLOUDINARY_URL = _env('CLOUDINARY_URL')
_CN = _env('CLOUDINARY_CLOUD_NAME')
_AK = _env('CLOUDINARY_API_KEY')
_AS = _env('CLOUDINARY_API_SECRET')

# Якщо адмін додав три окремі ключі замість єдиного URL — збираємо URL самі
# і пробрасуємо у os.environ, щоб бібліотека `cloudinary` теж його прочитала.
if not _CLOUDINARY_URL and _CN and _AK and _AS:
    _CLOUDINARY_URL = f'cloudinary://{_AK}:{_AS}@{_CN}'
    os.environ.setdefault('CLOUDINARY_URL', _CLOUDINARY_URL)

if _CLOUDINARY_URL:
    _DEFAULT_STORAGE_BACKEND = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    CLOUDINARY_STORAGE = {'CLOUDINARY_URL': _CLOUDINARY_URL}
    if _CN and _AK and _AS:
        CLOUDINARY_STORAGE.update({
            'CLOUD_NAME': _CN,
            'API_KEY': _AK,
            'API_SECRET': _AS,
        })
else:
    # Fallback: локальна файлова система (ephemeral на Render — ок для першого
    # запуску, але на проді обов'язково задай Cloudinary).
    _DEFAULT_STORAGE_BACKEND = 'django.core.files.storage.FileSystemStorage'
    CLOUDINARY_STORAGE = {}
    _log.warning('Cloudinary не сконфігуровано (немає ні CLOUDINARY_URL, '
                 'ні трійки CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET) — '
                 'медіа зберігаються локально (ephemeral диск Render, '
                 'файли зникнуть при рестарті).')

STORAGES = {
    'default': {'BACKEND': _DEFAULT_STORAGE_BACKEND},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# Backward-compat для django-cloudinary-storage (читає legacy ключі).
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
DEFAULT_FILE_STORAGE = _DEFAULT_STORAGE_BACKEND

WHITENOISE_MAX_AGE = 60 * 60 * 24 * 30  # 30 днів
WHITENOISE_USE_FINDERS = False
WHITENOISE_AUTOREFRESH = False

# ---------------------------------------------------------------------------
# Безпека
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

DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024   # 20 MB — admin forms with TinyMCE
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB — threshold to temp-file
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

# ---------------------------------------------------------------------------
# Email
# Пріоритет: Resend API → Gmail SMTP → console (логи Render)
# ---------------------------------------------------------------------------
_RESEND_KEY = _env('RESEND_API_KEY')
_EMAIL_USER = _env('EMAIL_HOST_USER')
_EMAIL_PASSWORD = _env('EMAIL_HOST_PASSWORD')

if _RESEND_KEY:
    INSTALLED_APPS = INSTALLED_APPS + ['anymail']  # type: ignore[name-defined]
    EMAIL_BACKEND = 'anymail.backends.resend.EmailBackend'
    ANYMAIL = {'RESEND_API_KEY': _RESEND_KEY}
    DEFAULT_FROM_EMAIL = _env('DEFAULT_FROM_EMAIL') or 'onboarding@resend.dev'
elif _EMAIL_USER and _EMAIL_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_TIMEOUT = 15
    EMAIL_HOST_USER = _EMAIL_USER
    EMAIL_HOST_PASSWORD = _EMAIL_PASSWORD
    DEFAULT_FROM_EMAIL = _env('DEFAULT_FROM_EMAIL') or _EMAIL_USER
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = _env('DEFAULT_FROM_EMAIL') or 'webmaster@localhost'
    _log.warning('Жодного email backend не сконфігуровано — листи пишуться у '
                 'Render Logs. Додай RESEND_API_KEY у Environment Variables.')

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
