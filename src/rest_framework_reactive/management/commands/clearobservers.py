from django.core.cache import cache
from django.core.management.base import BaseCommand

from ... import models
from ...consumers import THROTTLE_CACHE_PREFIX


class Command(BaseCommand):
    """Clear observer state."""

    help = "Clear observer state: delete all observers and subscribers."

    def handle(self, *args, **options):
        """Command handle."""
        models.Observer.objects.all().delete()
        models.Subscriber.objects.all().delete()

        for cache_key in cache.keys(search='{}*'.format(THROTTLE_CACHE_PREFIX)):
            cache.delete(cache_key)
