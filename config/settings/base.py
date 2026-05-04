import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-key-change-in-production')

DEBUG = False

ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    'modeltranslation',
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
    'tinymce',
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
    'django.middleware.locale.LocaleMiddleware',
    'core.middleware.LanguageGuardMiddleware',
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
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ('uk', 'Українська'),
    ('en', 'English'),
    ('ru', 'Русский'),
]

LOCALE_PATHS = [BASE_DIR / 'locale']

MODELTRANSLATION_DEFAULT_LANGUAGE = 'uk'
MODELTRANSLATION_PREPOPULATE_LANGUAGE = 'uk'
MODELTRANSLATION_FALLBACK_LANGUAGES = ('uk',)

LANGUAGE_COOKIE_NAME = 'bookshop_language'
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365
LANGUAGE_COOKIE_SECURE = False
LANGUAGE_COOKIE_HTTPONLY = False
LANGUAGE_COOKIE_SAMESITE = 'Lax'

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

TINYMCE_DEFAULT_CONFIG = {
    'height': 360,
    'menubar': False,
    'plugins': (
        'advlist autolink lists link image charmap preview anchor '
        'searchreplace visualblocks code fullscreen '
        'insertdatetime media table paste help wordcount'
    ),
    'toolbar': (
        'undo redo | formatselect | bold italic underline | '
        'alignleft aligncenter alignright | '
        'bullist numlist outdent indent | link image | '
        'removeformat | code fullscreen'
    ),
    'images_upload_url': '/admin/tinymce-upload/',
    'images_upload_credentials': True,
    'automatic_uploads': True,
    'images_reuse_filename': False,
    # Paragraph blocks on Enter (not <br>)
    'forced_root_block': 'p',
    # Paste: strip margin/padding inline styles, keep text formatting
    'paste_as_text': False,
    'paste_data_images': True,
    'paste_webkit_styles': 'color background-color font-weight font-style text-decoration text-align',
    'paste_retain_style_properties': 'color background-color font-weight font-style text-decoration text-align',
    # Only allow these inline styles on any element (strips margin, padding, etc.)
    'valid_styles': {
        '*': 'color,background-color,font-weight,font-style,text-decoration,text-align',
    },
    'browser_spellcheck': True,
    'language': 'uk',
    # Mirror frontend CSS so admin preview matches the live site
    'content_style': (
        'body { font-family: Segoe UI, sans-serif; font-size: 14px; line-height: 1.6; } '
        'p { margin: 0 0 10px 0; line-height: 1.6; font-size: 0.875rem; } '
        'ul, ol { padding-left: 18px; margin-bottom: 8px; } '
        'li { margin-bottom: 4px; } '
        'h1, h2, h3, h4 { margin: 12px 0 6px; line-height: 1.3; }'
    ),
}
