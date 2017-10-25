from __future__ import absolute_import, division, print_function, unicode_literals

import contextlib
import types

import six

from django.db.models.sql import compiler

from . import exceptions, decorators
from .observer import QueryObserver
from .backends.base import ObserverBackend
from .backends.dummy import DummyBackend


def serializable(function):
    """
    A helper decorator to make query observer pool methods serializable
    using a local lock object.
    """

    def wrapper(self, *args, **kwargs):
        lock = self.backend.create_lock()
        if lock is None:
            return function(self, *args, **kwargs)

        with lock:
            return function(self, *args, **kwargs)

    return wrapper


class QueryInterceptor(object):
    def __init__(self, pool):
        self.pool = pool
        self.intercepting_queries = 0
        self.tables = {}

    def _thread_id(self):
        return id(self.pool.backend.thread_id)

    def _patch(self):
        """
        Monkey patch the SQLCompiler class to get all the referenced tables in a code block.
        """

        self.intercepting_queries += 1
        if self.intercepting_queries > 1:
            return

        self._original_as_sql = compiler.SQLCompiler.as_sql

        def as_sql(compiler, *args, **kwargs):
            try:
                return self._original_as_sql(compiler, *args, **kwargs)
            finally:
                self.tables.setdefault(self._thread_id(), set()).update(compiler.query.tables)

        if six.PY2:
            compiler.SQLCompiler.as_sql = types.MethodType(as_sql, None, compiler.SQLCompiler)
        else:
            compiler.SQLCompiler.as_sql = as_sql

    def _unpatch(self):
        """
        Restore SQLCompiler monkey patches.
        """

        self.intercepting_queries -= 1
        assert self.intercepting_queries >= 0

        if self.intercepting_queries:
            return

        compiler.SQLCompiler.as_sql = self._original_as_sql

    @contextlib.contextmanager
    def intercept(self, tables):
        """
        Intercepts all tables used inside a codeblock.

        :param tables: Output tables set
        """

        self._patch()

        try:
            # Run the code block.
            yield
        finally:
            self._unpatch()

            if self._thread_id() in self.tables:
                tables.update(self.tables[self._thread_id()])
                del self.tables[self._thread_id()]


class QueryObserverPool(object):
    """
    A pool of query observers.
    """

    def __init__(self):
        """
        Creates a new query observer pool.
        """

        self._viewsets = set()
        self._observers = {}
        self._tables = {}
        self._subscribers = {}
        self._queue = set()
        self._pending_process = False
        self._evaluations = 0
        self._running = 0
        self._sleeping = 0
        self._poll_updates = 0
        self._db_updates = 0
        self._creations = 0
        self._destructions = 0

        self.backend = DummyBackend()
        self.query_interceptor = QueryInterceptor(self)

    def set_backend(self, backend):
        """
        Set the backend class that should be used for scheduling observers.
        """

        if not isinstance(backend, ObserverBackend):
            raise ValueError("Observer backends must subclass ObserverBackend.")

        self.backend = backend

    @property
    def statistics(self):
        """
        Return pool statistics.
        """

        observers_by_status = {}
        for observer in self._observers.values():
            observers_by_status[observer.status] = observers_by_status.get(observer.status, 0) + 1

        return {
            'viewsets': len(self._viewsets),
            'observers': {
                'total': len(self._observers),
                'creations': self._creations,
                'destructions': self._destructions,
                'evaluations': self._evaluations,
                'running': self._running,
                'sleeping': self._sleeping,
                'status': observers_by_status,
            },
            'updates': {
                'database': self._db_updates,
                'poll': self._poll_updates,
                'queue': len(self._queue),
            },
            'tables': len(self._tables),
            'subscribers': len(self._subscribers),
        }

    @serializable
    def register_viewset(self, viewset):
        """
        Registers a new observable viewset.

        :param viewset: DRF viewset
        """

        if viewset in self._viewsets:
            raise exceptions.ViewSetAlreadyRegistered
        self._viewsets.add(viewset)

        # Patch list method if one exists.
        list_method = getattr(viewset, 'list', None)
        if list_method is not None and not getattr(list_method, 'is_observable', False):
            viewset.list = decorators.observable(list_method)

    @serializable
    def register_dependency(self, observer, table):
        """
        Registers a new dependency.

        :param observer: Query observer instance
        :param table: Dependent database table name
        """

        self._tables.setdefault(table, set()).add(observer)

    @serializable
    def register_poller(self, observer):
        """
        Register a new poller for the given observer.

        :param observer: Query observer instance
        """

        self._poll_updates += 1
        self.backend.spawn_later(observer._meta.poll_interval, observer.evaluate, return_full=False)

    @serializable
    def unregister_dependency(self, observer, table):
        """
        Removes a registered dependency.

        :param observer: Query observer instance
        :param table: Dependent database table name
        """

        self._tables[table].remove(observer)

    @serializable
    def observe_viewset(self, request, subscriber):
        """
        Subscribes to observing of a viewset.

        :param request: The `queryobservers.request.Request` to observe
        :param subscriber: Channel identifier of the subscriber
        :return: Query observer instance
        """

        query_observer = QueryObserver(self, request)
        if query_observer.id in self._observers:
            existing = self._observers[query_observer.id]
            if not existing.stopped:
                query_observer = existing
            else:
                self._observers[query_observer.id] = query_observer
                self._creations += 1
        else:
            self._observers[query_observer.id] = query_observer
            self._creations += 1

        query_observer.subscribe(subscriber)
        self._subscribers.setdefault(subscriber, set()).add(query_observer)
        return query_observer

    @serializable
    def unobserve_viewset(self, observer_id, subscriber):
        """
        Unsubscribes from observing a viewset.

        :param observer_id: Query observer identifier
        :param subscriber: Channel identifier of the subscriber
        """

        try:
            query_observer = self._observers[observer_id]
            query_observer.unsubscribe(subscriber)

            # Update subscribers map.
            self._remove_subscriber(query_observer, subscriber)
        except KeyError:
            pass

    def _remove_subscriber(self, observer, subscriber):
        observers = self._subscribers[subscriber]
        observers.remove(observer)
        if not observers:
            del self._subscribers[subscriber]

    def _remove_observer(self, observer):
        self._destructions += 1
        del self._observers[observer.id]

    @serializable
    def stop_all(self):
        """
        Stops all query observers.
        """

        # We need to make a copy of the values as `observer.stop()` will cause
        # the observer dictionary to be modified.
        for observer in list(self._observers.values()):
            observer.stop()

        self._observers = {}
        self._subscribers = {}

    @serializable
    def remove_subscriber(self, subscriber):
        """
        Removes a subscriber from all subscribed query observers.

        :param subscriber: Channel identifier of the subscriber
        """

        try:
            for observer in self._subscribers[subscriber]:
                observer.unsubscribe(subscriber)
            del self._subscribers[subscriber]
        except KeyError:
            pass

    @serializable
    def notify_update(self, table):
        """
        Notifies the observer pool that a database table has been updated.

        :param table: Database table name
        """

        if table not in self._tables:
            return

        # Add all observers that depend on this table to the notification queue.
        self._db_updates += 1
        self._queue.update(self._tables[table])
        self.process_notifications()

    @serializable
    def process_notifications(self):
        """
        Schedules the notification queue processing.
        """

        if self._pending_process:
            return

        self._pending_process = True
        self.backend.spawn(self._process_notifications)

    def _process_notifications(self):
        """
        Processes the notification queue.
        """

        self._pending_process = False
        queue = self._queue
        self._queue = set()

        for observer in queue:
            # Spawn evaluator for each observer.
            self.backend.spawn(observer.evaluate, return_full=False)

# Global pool instance.
pool = QueryObserverPool()
