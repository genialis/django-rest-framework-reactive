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
    }
    defaults.update(getattr(settings, 'DJANGO_REST_FRAMEWORK_REACTIVE', {}))
    return defaults
