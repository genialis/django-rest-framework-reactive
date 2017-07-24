from __future__ import absolute_import, division, print_function, unicode_literals

from django.conf import settings


# Redis channel for receiving control messages.
QUERYOBSERVER_REDIS_CHANNEL = 'django-rest-framework-reactive:control'


def get_redis_settings():
    """
    Returns the Redis connection configuration.
    """

    defaults = {
        'host': 'localhost',
        'port': 6379,
        'db': 0,
    }
    defaults.update(getattr(settings, 'REDIS_CONNECTION', {}))
    return defaults


def get_queryobserver_settings():
    """
    Returns the query observer connection configuration.
    """

    defaults = {
        'host': 'localhost',
        'port': 9432,
        # Observers going over these limits will emit warnings.
        'warnings': {
            'max_result_length': 1000,
            'max_processing_time': 1.0,
        },
        # Observers going over these limits will be stopped.
        'errors': {
            'max_processing_time': 20.0,
        },
        # Update batch delay (in seconds). If a new update comes earlier than the
        # delay value, queue processing will be delayed so multiple updates can be
        # batched. A higher value introduces more latency.
        'update_batch_delay': 5,
    }
    defaults.update(getattr(settings, 'DJANGO_REST_FRAMEWORK_REACTIVE', {}))
    return defaults
