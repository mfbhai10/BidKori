"""
Django settings for BidKori — the real-time auction marketplace.

All sensitive values are loaded from environment variables (see .env.example).
"""
import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ──────────────────────────────────────────────────────────
# Security
# ──────────────────────────────────────────────────────────
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'insecure-dev-key-change-in-production')
DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0').split(',')
if DEBUG:
    ALLOWED_HOSTS = ['*']


# ──────────────────────────────────────────────────────────
# Installed Applications
# ──────────────────────────────────────────────────────────
INSTALLED_APPS = [
    # Daphne ASGI server (must be first for runserver override)
    'daphne',

    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'corsheaders',
    'channels',

    # Local apps
    'users',
    'products',
    'auctions',
    'billing',
    'moderation',
]

# ──────────────────────────────────────────────────────────
# Middleware
# ──────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ──────────────────────────────────────────────────────────
# URL & Template Configuration
# ──────────────────────────────────────────────────────────
ROOT_URLCONF = 'bidkori_core.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'bidkori_core.wsgi.application'
ASGI_APPLICATION = 'bidkori_core.asgi.application'

# ──────────────────────────────────────────────────────────
# Database — PostgreSQL 16
# ──────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'bidkori_db'),
        'USER': os.getenv('POSTGRES_USER', 'bidkori_user'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'bidkori_pass'),
        'HOST': os.getenv('POSTGRES_HOST', 'db'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}

# ──────────────────────────────────────────────────────────
# Custom User Model
# ──────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'users.User'

# ──────────────────────────────────────────────────────────
# Password Validation
# ──────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ──────────────────────────────────────────────────────────
# Internationalization
# ──────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

# ──────────────────────────────────────────────────────────
# Static & Media Files
# ──────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ──────────────────────────────────────────────────────────
# Default Primary Key Type
# ──────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ──────────────────────────────────────────────────────────
# Django REST Framework
# ──────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# ──────────────────────────────────────────────────────────
# Simple JWT
# ──────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ──────────────────────────────────────────────────────────
# Django Channels — Redis Channel Layer
# ──────────────────────────────────────────────────────────
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [os.getenv('REDIS_URL', 'redis://redis:6379/0')],
        },
    },
}

# ──────────────────────────────────────────────────────────
# Celery — Redis Broker
# ──────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Dhaka'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 minutes hard limit

# Celery Beat — Periodic Tasks
CELERY_BEAT_SCHEDULE = {
    'transition-auction-states': {
        'task': 'auctions.tasks.transition_auction_states',
        'schedule': 5.0,  # every 5 seconds
    },
}

# ──────────────────────────────────────────────────────────
# CORS
# ──────────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = os.getenv(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:8000,http://127.0.0.1:8000',
).split(',')

# ──────────────────────────────────────────────────────────
# Google Gemini AI (Phase 2)
# ──────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
