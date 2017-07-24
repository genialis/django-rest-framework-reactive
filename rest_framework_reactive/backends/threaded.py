from __future__ import absolute_import, division, print_function, unicode_literals

import threading

from .base import ObserverBackend


class ThreadedBackend(ObserverBackend):
    """
    Threaded observer backend, mainly suitable for use in tests. This
    backend should not be used in production.
    """

    @property
    def thread_id(self):
        """Return the current thread identifier."""
        return threading.current_thread()

    def spawn(self, function, *args, **kwargs):
        """Threaded spawner just runs the function immediately."""
        return function(*args, **kwargs)

    def spawn_later(self, seconds, function, *args, **kwargs):
        """Threaded spawner just runs the function immediately."""
        return function(*args, **kwargs)

    def create_future(self):
        """Create a future-like threaded object."""
        return threading.Event()

    def create_lock(self):
        """Create a lock-like threaded object."""
        return threading.RLock()
