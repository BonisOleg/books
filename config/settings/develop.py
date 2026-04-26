import os

from .base import *  # noqa: F401,F403
from .base import BASE_DIR

DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(',')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

_DEV_EMAIL_USER = os.getenv('EMAIL_HOST_USER')
_DEV_EMAIL_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
if _DEV_EMAIL_USER and _DEV_EMAIL_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_TIMEOUT = 15
    EMAIL_HOST_USER = _DEV_EMAIL_USER
    EMAIL_HOST_PASSWORD = _DEV_EMAIL_PASSWORD
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL') or _DEV_EMAIL_USER
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL') or 'noreply@localhost'

# In develop we keep the default Django filesystem storage so uploads land in
# MEDIA_ROOT and we don't need Cloudinary credentials locally.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
