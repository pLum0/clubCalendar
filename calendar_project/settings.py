"""
Django settings for calendar_project project.
"""

import os
from pathlib import Path
from urllib.parse import urlparse
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-change-in-production')

DEBUG = os.environ.get('DEBUG', '1') == '1'

SITE_NAME = os.environ.get('SITE_NAME', 'Sports Club Calendar')
SITE_LOGO = os.environ.get('SITE_LOGO', '')
SITE_URL = os.environ.get('SITE_URL', '').rstrip('/')
SECRET_PATH = os.environ.get('SECRET_PATH', '').strip('/')

if SITE_URL:
    CSRF_TRUSTED_ORIGINS = [SITE_URL]
    ALLOWED_HOSTS = [urlparse(SITE_URL).hostname]
else:
    CSRF_TRUSTED_ORIGINS = []
    ALLOWED_HOSTS = ['*']

NTFY_ALLOWED_HOSTS = os.environ.get('NTFY_ALLOWED_HOSTS', '')

INSTALLED_APPS = [
    'calendar_app',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'recurrence',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'calendar_app.middleware.AdminXFrameOptionsMiddleware',
]

ROOT_URLCONF = 'calendar_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'calendar_project.context_processors.site_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'calendar_project.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'calendar'),
        'USER': os.environ.get('POSTGRES_USER', 'calendar'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'calendar'),
        'HOST': os.environ.get('POSTGRES_HOST', 'db'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

LANGUAGES = [
    ('en', _('English')),
    ('de', _('German')),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

if SECRET_PATH:
    LOGIN_URL = f'/{SECRET_PATH}/admin/'
    CSRF_COOKIE_PATH = f'/{SECRET_PATH}/'
    SESSION_COOKIE_PATH = f'/{SECRET_PATH}/'
    LANGUAGE_COOKIE_PATH = f'/{SECRET_PATH}/'
else:
    LOGIN_URL = '/admin/'

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
