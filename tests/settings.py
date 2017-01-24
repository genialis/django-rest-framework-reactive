"""
Django settings for running tests for django-rest-framework-reactive package.

"""
from __future__ import absolute_import, division, print_function, unicode_literals

import os

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = 'secret'

DEBUG = True

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
)

# Apps from this project
PROJECT_APPS = (
    'rest_framework_reactive',
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',

    'rest_framework',
    'ws4redis',
    'guardian',
) + PROJECT_APPS

ROOT_URLCONF = 'tests.urls'

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
            ],
        },
    },
]

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)

ANONYMOUS_USER_NAME = 'public'

# Get the current Tox testing environment
# NOTE: This is useful for concurrently running tests with separate environments
toxenv = os.environ.get('TOXENV', '')

# Check if PostgreSQL settings are set via environment variables
pgname = os.environ.get('DRFR_POSTGRESQL_NAME', 'drfr')
pguser = os.environ.get('DRFR_POSTGRESQL_USER', 'drfr')
pghost = os.environ.get('DRFR_POSTGRESQL_HOST', 'localhost')
pgport = int(os.environ.get('DRFR_POSTGRESQL_PORT', 55435))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': pgname,
        'USER': pguser,
        'HOST': pghost,
        'PORT': pgport,
        'TEST': {
            'NAME': 'drfr_test' + toxenv
        }
    }
}

STATIC_URL = '/static/'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'rest_framework_filters.backends.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
    ),
}

REDIS_CONNECTION = {
    'host': 'localhost',
    'port': int(os.environ.get('DRFR_REDIS_PORT', 56380)),
    'db': 0,
}

WS4REDIS_CONNECTION = REDIS_CONNECTION

WS4REDIS_PREFIX = 'ws'

WS4REDIS_SUBSCRIBER = 'rest_framework_reactive.websockets.QueryObserverSubscriber'
