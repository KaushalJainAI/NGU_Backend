"""Self-contained settings for the local feature-demo run.

File-based SQLite (so the runserver process and the seeder share one DB) +
locmem cache. Nothing here touches the production Postgres/Redis. Run with:

    python manage.py <cmd> --settings=spices_backend.demo_settings
"""
import os

from .settings import *  # noqa: F401,F403

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEBUG = True
ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(_BASE, 'demo', 'demo.sqlite3'),
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'demo',
    }
}

# Scripted demo fires requests back-to-back; don't let throttles 429 the run.
try:
    REST_FRAMEWORK = {**REST_FRAMEWORK}  # noqa: F405
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
        k: '100000/day' for k in (REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES') or {})
    }
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].update({
        'events': '100000/day', 'assistant_burst': '100000/min',
        'assistant_daily': '100000/day',
    })
except NameError:
    pass

# Local filesystem storage for the demo — never touch S3 (the thumbnail signal
# and image validators would otherwise round-trip to the bucket).
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(_BASE, 'demo', 'media')
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
