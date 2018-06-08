from django.core.management.base import BaseCommand

from ... import models


class Command(BaseCommand):
    """Clear observer state."""

    help = "Clear observer state."

    def handle(self, *args, **options):
        """Command handle."""
        models.Observer.objects.all().delete()
        models.Subscriber.objects.all().delete()
