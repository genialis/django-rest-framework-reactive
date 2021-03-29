"""
Django settings for running tests for django-rest-framework-reactive package.

"""
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
    'drfr_test_app.apps.QueryObserverTestsConfig',
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'rest_framework',
    'channels',
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
            ]
        },
    }
]

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)

ANONYMOUS_USER_NAME = 'public'

# Get the current Tox testing environment
# NOTE: This is useful for concurrently running tests with separate environments
toxenv = os.environ.get('TOXENV', '')

# Check if PostgreSQL settings are set via environment variables
pgname = os.environ.get('DRFR_POSTGRESQL_NAME', 'drfr')
pguser = os.environ.get('DRFR_POSTGRESQL_USER', 'drfr')
pgpass = os.environ.get('DRFR_POSTGRESQL_PASS', 'drfr')
pghost = os.environ.get('DRFR_POSTGRESQL_HOST', 'localhost')
pgport = int(os.environ.get('DRFR_POSTGRESQL_PORT', 55435))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': pgname,
        'USER': pguser,
        'PASSWORD': pgpass,
        'HOST': pghost,
        'PORT': pgport,
        'TEST': {'NAME': 'drfr_test' + toxenv},
    }
}

STATIC_URL = '/static/'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.backends.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
    ),
}

CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}

ASGI_APPLICATION = 'rest_framework_reactive.routing.application'

DJANGO_REST_FRAMEWORK_REACTIVE = {
    # Set throttle rate to zero during tests as otherwise they can be delayed
    # and cause test timeouts.
    'throttle_rate': 0
}
