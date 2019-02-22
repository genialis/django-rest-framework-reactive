from django.conf import settings


def get_queryobserver_settings():
    """Query observer connection configuration."""
    defaults = {
        # Observers going over these limits will emit warnings.
        'warnings': {'max_result_length': 1000, 'max_processing_time': 1.0},
        # Observers going over these limits will be stopped.
        'errors': {'max_processing_time': 20.0},
        # Throttle evaluation (in seconds). If a new update comes earlier than
        # given rate value, the evaluation will be delayed (and batched).
        # A higher value introduces more latency.
        'throttle_rate': 2,
    }
    defaults.update(getattr(settings, 'DJANGO_REST_FRAMEWORK_REACTIVE', {}))
    return defaults
