from __future__ import absolute_import, division, print_function, unicode_literals

import gevent
import gevent.event

from .base import ObserverBackend


class GeventBackend(ObserverBackend):
    """
    Gevent-based observer backend.
    """

    @property
    def thread_id(self):
        """Return the current thread identifier."""
        return gevent.getcurrent()

    def spawn(self, function, *args, **kwargs):
        """Spawn a new gevent greenlet."""
        return gevent.spawn(function, *args, **kwargs)

    def spawn_later(self, seconds, function, *args, **kwargs):
        """Spawn a new gevent greenlet later."""
        return gevent.spawn_later(seconds, function, *args, **kwargs)

    def create_future(self):
        """Create a future-like object on gevent."""
        return gevent.event.Event()

    def create_lock(self):
        """Gevent backend does not support locks."""
        return None
