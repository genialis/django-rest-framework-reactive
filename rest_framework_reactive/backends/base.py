from __future__ import absolute_import, division, print_function, unicode_literals


class ObserverBackend(object):
    """
    Abstract observer backend, which defines primitives for scheduling
    observers.
    """

    @property
    def thread_id(self):
        """Return the current thread identifier."""
        raise NotImplementedError

    def spawn(self, function, *args, **kwargs):
        """Spawn a new scheduling unit."""
        raise NotImplementedError

    def spawn_later(self, seconds, function, *args, **kwargs):
        """Spawn a new scheduling unit at a later time."""
        raise NotImplementedError

    def create_future(self):
        """Create a future-like object.

        If the backend does not support futures, it will return None.
        """

        raise NotImplementedError

    def create_lock(self):
        """Create a lock-like object.

        If the backend does not support locking, it will return None.
        """

        raise NotImplementedError
