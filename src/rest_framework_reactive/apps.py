"""Application configuration."""
from django.apps import AppConfig


class BaseConfig(AppConfig):
    """Application configuration."""

    name = 'rest_framework_reactive'

    def ready(self):
        """Perform application initialization."""
        # Connect all signals.
        from . import signals
