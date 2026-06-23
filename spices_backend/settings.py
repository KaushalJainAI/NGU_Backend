from pathlib import Path
from datetime import timedelta
import os
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# Security Settings
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# Support for HTTPS when behind a reverse proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = config('USE_X_FORWARDED_HOST', default=False, cast=bool)

# Application definition
INSTALLED_APPS = [
    # Must precede django.contrib.admin so translated fields appear in the admin.
    'modeltranslation',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    
    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'storages',
    'cloudinary_storage',
    'cloudinary',
    'django_filters',
    'adminsortable2',

    # Auth & Social Login
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'dj_rest_auth',
    'dj_rest_auth.registration',
    
    # Local apps
    'users.apps.UsersConfig',
    'products.apps.ProductsConfig',
    'cart.apps.CartConfig',
    'orders.apps.OrdersConfig',
    'payments.apps.PaymentsConfig',
    'reviews.apps.ReviewsConfig',
    'admin_panel.apps.AdminPanelConfig',
    'support.apps.SupportConfig',
    'assistant.apps.AssistantConfig',
    'analytics.apps.AnalyticsConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # Activates ?lang= / X-Language for modeltranslation content.
    'spices_backend.middleware.LanguageQueryMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'spices_backend.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'spices_backend.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.sqlite3'),
        'NAME': config('DB_NAME', default=str(BASE_DIR / 'db.sqlite3')),
        'USER': config('DB_USER', default=''),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default=''),
        'PORT': config('DB_PORT', default=''),
        # Connection pooling - reuse connections for 60 seconds
        # Reduces connection overhead significantly
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,  # Django 4.1+ - check connection health
    }
}


# Password validation
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

# Internationalization
LANGUAGE_CODE = 'en'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Languages the storefront content can be translated into. Mirrors the frontend
# src/i18n SUPPORTED_LANGUAGES and the chat assistant language codes.
LANGUAGES = [
    ('en', 'English'),
    ('hi', 'Hindi'),
    ('hinglish', 'Hinglish'),
    ('gu', 'Gujarati'),
    ('mr', 'Marathi'),
    ('pa', 'Punjabi'),
]

# django-modeltranslation: per-language columns for Product/Category content.
MODELTRANSLATION_DEFAULT_LANGUAGE = 'en'
MODELTRANSLATION_LANGUAGES = ('en', 'hi', 'hinglish', 'gu', 'mr', 'pa')
# Any empty translation transparently falls back to English so newly added
# products (and untranslated fields) always render.
MODELTRANSLATION_FALLBACK_LANGUAGES = ('en',)

# Media / static storage configuration
#
# Media files (product/category/profile images, chat attachments) are served from
# Cloudinary's image CDN when USE_CLOUDINARY is on (the storefront default), giving
# fast global delivery. Static files (CSS/JS) continue to use S3 or local storage.
#
# Precedence for the `default` (media) storage backend:
#   USE_CLOUDINARY  ->  Cloudinary   (preferred)
#   USE_S3          ->  AWS S3
#   neither         ->  local filesystem
USE_CLOUDINARY = config('USE_CLOUDINARY', default=True, cast=bool)
USE_S3 = config('USE_S3', default=False, cast=bool)

if USE_CLOUDINARY:
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME'),
        'API_KEY': config('CLOUDINARY_API_KEY'),
        'API_SECRET': config('CLOUDINARY_API_SECRET'),
        'PREFIX': 'ngu',  # namespace all NGU media under the ngu/ folder in Cloudinary
    }

if USE_S3:
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='ap-south-1')
    AWS_S3_SIGNATURE_VERSION = config('AWS_S3_SIGNATURE_VERSION', default='s3v4')
    
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'
    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
    AWS_DEFAULT_ACL = None  # Use bucket policy instead of ACL (AWS default)
    AWS_S3_FILE_OVERWRITE = False
    AWS_QUERYSTRING_AUTH = False  # No signed URLs for public files
    
    # Django 4.2+ / 5.x storage configuration
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "location": "media",  # Upload media files to 'media/' folder in bucket
            },
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3boto3.S3StaticStorage",
            "OPTIONS": {
                "location": "static",  # Static files go to 'static/' folder
            },
        },
    }
    
    STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
    
    # Also define STATIC_ROOT for collectstatic command
    STATIC_ROOT = BASE_DIR / 'staticfiles'
else:
    STATIC_URL = '/static/'
    STATIC_ROOT = BASE_DIR / 'staticfiles'
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

# Cloudinary takes over the `default` (media) storage backend. Static files keep
# whatever backend the S3/local branch above selected. Because Cloudinary's storage
# returns absolute res.cloudinary.com URLs, MEDIA_URL is unused for media but is left
# defined above as a harmless fallback.
if USE_CLOUDINARY:
    STORAGES = globals().get('STORAGES', {})
    STORAGES.setdefault(
        'staticfiles',
        {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    )
    STORAGES['default'] = {
        'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
    }

# File Upload Configuration (500MB limit for photos/videos)
DATA_UPLOAD_MAX_MEMORY_SIZE = 524288000
FILE_UPLOAD_MAX_MEMORY_SIZE = 524288000

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.User'
SITE_ID = 1

# Authentication Backends for allauth
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'users.authentication.CookieJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 12,
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Custom exception handler: returns JSON 400/500 instead of HTML errors
    'EXCEPTION_HANDLER': 'spices_backend.exceptions.custom_exception_handler',
    # Rate Limiting / Throttling
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '1000/hour',      # Anonymous users: 1000 requests per hour
        'user': '10000/hour',     # Authenticated users: 10000 requests per hour
        'login': '5/minute',     # Login attempts: 5 per minute
        'register': '3/minute',  # Registration: 3 per minute
        'contact': '5/hour',     # Contact form: 5 per hour
        'password_reset': '10/day',  # Password reset OTP: 10 per day
        'assistant': '20/min',   # AI assistant: 20 messages per minute
        'assistant_day': '500/day',  # AI assistant: hard daily cap (cost guard)
        'events': '600/hour',    # Behavioral event ingest (batched on client)
        'search_suggest': '60/min',  # Autocomplete: keystroke-friendly but bounded
        'geocode': '60/hour',    # Reverse-geocode proxy (respects Nominatim policy)
    }
}

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# dj-rest-auth configuration
REST_AUTH = {
    'USE_JWT': True,
    'TOKEN_MODEL': None,
    'JWT_AUTH_COOKIE': 'access_token',
    'JWT_AUTH_REFRESH_COOKIE': 'refresh_token',
    'JWT_AUTH_HTTPONLY': True,
    'USER_DETAILS_SERIALIZER': 'users.serializers.UserSerializer',
}

# allauth configuration
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'
ACCOUNT_EMAIL_VERIFICATION = 'none'

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': config('GOOGLE_CLIENT_ID', default=''),
            'secret': config('GOOGLE_CLIENT_SECRET', default=''),
            'key': ''
        },
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    }
}

# CORS Settings - SECURITY CRITICAL
# In production, CORS_ALLOW_ALL_ORIGINS should ALWAYS be False
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://127.0.0.1:3000,http://localhost:3000,http://localhost:3001'
).split(',')

# WARNING: Set to False in production! True bypasses the whitelist above
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)
CORS_ALLOW_CREDENTIALS = True

# Allow the storefront's language header (used for modeltranslation content).
from corsheaders.defaults import default_headers as _cors_default_headers
CORS_ALLOW_HEADERS = list(_cors_default_headers) + ['x-language']

CORS_ALLOW_METHODS = [
    'GET',
    'POST',
    'PUT',
    'PATCH',
    'DELETE',
    'OPTIONS'
]

# CSRF Trusted Origins - Required for admin panel login
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:3001,http://localhost:8000,http://127.0.0.1:8000'
).split(',')

# CSRF Cookie Settings
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'

# =============================================================================
# PRODUCTION SECURITY SETTINGS
# =============================================================================
# These are automatically enabled when DEBUG=False
if not DEBUG:
    # HTTPS Security
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    
    # HSTS - Force HTTPS (1 year)
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Secure cookies — override via env when running on HTTP (no SSL)
    SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=True, cast=bool)
    CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=True, cast=bool)
    
    # SSL redirect (set to False if load balancer handles SSL)
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)

# Payment Gateway Settings
STRIPE_PUBLIC_KEY = config('STRIPE_PUBLIC_KEY', default='')
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')

RAZORPAY_KEY_ID = config('RAZORPAY_KEY_ID', default='')
RAZORPAY_KEY_SECRET = config('RAZORPAY_KEY_SECRET', default='')

# Email Configuration
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
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
        'level': 'INFO',
    },
    # S3/AWS logging - captures upload failures and connection issues
    'loggers': {
        'boto3': {
            'handlers': ['console'],
            'level': 'WARNING',  # Change to DEBUG for verbose S3 debugging
            'propagate': False,
        },
        'botocore': {
            'handlers': ['console'],
            'level': 'WARNING',  # Change to DEBUG for verbose S3 debugging
            'propagate': False,
        },
        's3transfer': {
            'handlers': ['console'],
            'level': 'WARNING',  # Change to DEBUG for transfer details
            'propagate': False,
        },
        'storages': {
            'handlers': ['console'],
            'level': 'DEBUG',  # Django-storages logging
            'propagate': False,
        },
    },
}

# =============================================================================
# CACHE CONFIGURATION
# =============================================================================
# Redis caching - works on both Windows (Memurai) and Linux
# Set REDIS_URL in .env to enable Redis, otherwise falls back to local memory cache
#
# Examples:
#   - Local development: REDIS_URL=redis://127.0.0.1:6379/0
#   - Production Linux:  REDIS_URL=redis://redis-server:6379/0
#   - With password:     REDIS_URL=redis://:password@host:6379/0

REDIS_URL = config('REDIS_URL', default='')

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                # Connection settings
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
                'RETRY_ON_TIMEOUT': True,
                # Serialization
                'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
            },
            'KEY_PREFIX': 'ngu',
            'TIMEOUT': 300,  # 5 minutes default timeout
        }
    }
    # Use Redis for sessions too (optional, for better performance)
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    # Fallback to local memory cache (for development without Redis)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }

# Cache timeout constants (in seconds)
CACHE_TTL_SHORT = 60          # 1 minute - for frequently changing data
CACHE_TTL_MEDIUM = 300        # 5 minutes - for product lists
CACHE_TTL_LONG = 900          # 15 minutes - for categories, static data
CACHE_TTL_DASHBOARD = 120     # 2 minutes - for dashboard stats

# Celery Configuration (optional - only if using background tasks)
# CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'
# CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Triggering auto-reload again to pick up .env changes
