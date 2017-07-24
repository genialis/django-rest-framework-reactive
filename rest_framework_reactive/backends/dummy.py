from __future__ import absolute_import, division, print_function, unicode_literals

from .base import ObserverBackend


class DummyBackend(ObserverBackend):
    """
    Dummy observer backend.
    """

    @property
    def thread_id(self):
        """Dummy thread identifier is always None."""
        return None

    def spawn(self, function, *args, **kwargs):
        """Dummy spawner just runs the function immediately."""
        return function(*args, **kwargs)

    def spawn_later(self, seconds, function, *args, **kwargs):
        """Dummy spawner just runs the function immediately."""
        return function(*args, **kwargs)

    def create_future(self):
        """Dummy backend does not support futures."""
        return None

    def create_lock(self):
        """Dummy backend does not support locks."""
        return None
