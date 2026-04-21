import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-key-change-in-production')

DEBUG = False

ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary_storage',
    'cloudinary',
    'django.contrib.sitemaps',
    'django.contrib.humanize',
    'django_cleanup.apps.CleanupConfig',
    'core',
    'products',
    'cart',
    'orders',
    'reviews',
    'accounts',
    'blog',
    'promotions',
    'shipping',
    'import_export_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.site_settings',
                'cart.context_processors.cart_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTH_USER_MODEL = 'accounts.CustomUser'

LANGUAGE_CODE = 'uk'
TIME_ZONE = 'Europe/Kyiv'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

SITE_NAME = 'Магазин книжок'
SITE_DOMAIN = os.getenv('SITE_DOMAIN', 'localhost:8000')
SITE_PROTOCOL = os.getenv('SITE_PROTOCOL', 'http')

LIQPAY_PUBLIC_KEY = os.getenv('LIQPAY_PUBLIC_KEY', '')
LIQPAY_PRIVATE_KEY = os.getenv('LIQPAY_PRIVATE_KEY', '')

MONOBANK_TOKEN = os.getenv('MONOBANK_TOKEN', '')

NOVAPOSHTA_API_KEY = os.getenv('NOVAPOSHTA_API_KEY', '')

TELEGRAM_BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME', '')
VIBER_BOT_URI = os.getenv('VIBER_BOT_URI', '')

PHONE_NUMBERS = [
    '+380 (96) 846-67-58',
    '+380 (63) 964-85-33',
    '+380 (99) 559-88-64',
]
