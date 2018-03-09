from django.conf import settings


def get_queryobserver_settings():
    """Query observer connection configuration."""
    defaults = {
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
