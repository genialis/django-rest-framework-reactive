import collections
import json

from django.core import exceptions as django_exceptions
from django.http import Http404

from rest_framework import request as api_request
from ws4redis import publisher, redis_store

from . import exceptions


class QueryObserver(object):
    """
    A query observer observes a specific viewset for changes and propagates these
    changes to all interested subscribers.
    """

    STATUS_NEW = 'new'
    STATUS_INITIALIZING = 'initializing'
    STATUS_OBSERVING = 'observing'
    STATUS_STOPPED = 'stopped'

    MESSAGE_ADDED = 'added'
    MESSAGE_CHANGED = 'changed'
    MESSAGE_REMOVED = 'removed'

    def __init__(self, pool, request):
        """
        Creates a new query observer.

        :param pool: QueryObserverPool instance
        :param request: A `queryobserver.request.Request` instance
        """

        self.status = QueryObserver.STATUS_NEW
        self._pool = pool

        # Obtain a serializer by asking the viewset to provide one. We instantiate the
        # viewset with a fake request, so that the viewset methods work as expected.
        viewset = request.viewset_class()
        viewset.request = api_request.Request(request)
        viewset.format_kwarg = None
        viewset.args = request.args
        viewset.kwargs = request.kwargs
        self._viewset = viewset
        self._request = request

        self._last_results = collections.OrderedDict()
        self._subscribers = set()
        self._dependencies = set()
        self._initialization_future = None
        self.id = request.observe_id

    def add_dependency(self, table):
        """
        Registers a new dependency for this query observer.

        :param table: Name of the dependent database table
        """

        if table in self._dependencies:
            return

        self._dependencies.add(table)
        self._pool.register_dependency(self, table)

    @property
    def stopped(self):
        """
        True if the query observer has been stopped.
        """

        return self.status == QueryObserver.STATUS_STOPPED

    def evaluate(self, return_full=True, return_emitted=False):
        """
        Evaluates the query observer and checks if there have been any changes. This function
        may yield.

        :param return_full: True if the full set of rows should be returned
        :param return_emitted: True if the emitted diffs should be returned
        """

        if self.status == QueryObserver.STATUS_STOPPED:
            raise exceptions.ObserverStopped

        # Be sure to handle status changes before any yields, so that the other greenlets
        # will see the changes and will be able to wait on the initialization future.
        if self.status == QueryObserver.STATUS_INITIALIZING:
            self._initialization_future.wait()
        elif self.status == QueryObserver.STATUS_NEW:
            if self._pool.future_class is not None:
                self._initialization_future = self._pool.future_class()
            self.status = QueryObserver.STATUS_INITIALIZING

        # Evaluate the query (this operation yields).
        tables = set()
        stop_observer = False
        with self._pool.query_interceptor.intercept(tables):
            try:
                observable_view = getattr(self._viewset, self._request.viewset_method)
                response = observable_view(
                    self._viewset.request,
                    *self._request.args,
                    **self._request.kwargs
                )

                if response.status_code == 200:
                    results = response.data
                    self.primary_key = getattr(
                        observable_view,
                        'primary_key',
                        self._viewset.get_queryset().model._meta.pk.name
                    )

                    if not isinstance(results, list):
                        if isinstance(results, dict):
                            self.primary_key = 'id'
                            results['id'] = 1
                            results = [collections.OrderedDict(results)]
                        else:
                            raise ValueError("Observable views must return a dictionary or a list of dictionaries!")
                else:
                    results = []
            except Http404:
                results = []
            except django_exceptions.ObjectDoesNotExist:
                # The evaluation may fail when certain dependent objects (like users) are removed
                # from the database. In this case, the observer is stopped.
                stop_observer = True

        if stop_observer:
            self.stop()
            return []

        # Register table dependencies.
        for table in tables:
            self.add_dependency(table)

        # TODO: Only compute difference between old and new, ideally on the SQL server using hashes.
        new_results = collections.OrderedDict()

        if self.status == QueryObserver.STATUS_STOPPED:
            return []

        for order, row in enumerate(results):
            if not isinstance(row, dict):
                raise ValueError("Observable views must return a dictionary or a list of dictionaries!")

            row._order = order
            new_results[row[self.primary_key]] = row

        # Process difference between old results and new results.
        added = []
        changed = []
        removed = []
        for row_id, row in self._last_results.iteritems():
            if row_id not in new_results:
                removed.append(row)

        for row_id, row in new_results.iteritems():
            if row_id not in self._last_results:
                added.append(row)
            else:
                old_row = self._last_results[row_id]
                if row != old_row:
                    changed.append(row)
                if row._order != old_row._order:
                    changed.append(row)

        self._last_results = new_results

        if self.status == QueryObserver.STATUS_INITIALIZING:
            self.status = QueryObserver.STATUS_OBSERVING
            if self._initialization_future is not None:
                future = self._initialization_future
                self._initialization_future = None
                future.set()
        elif self.status == QueryObserver.STATUS_OBSERVING:
            self.emit(added, changed, removed)

            if return_emitted:
                return (added, changed, removed)

        if return_full:
            return self._last_results.values()

    def emit(self, added, changed, removed):
        """
        Notifies all subscribers about query changes.

        :param added: A list of rows there were added
        :param changed: A list of rows that were changed
        :param removed: A list of rows that were removed
        """

        # TODO: Instead of duplicating messages to all subscribers, handle subscriptions within redis.
        for message_type, rows in (
            (QueryObserver.MESSAGE_ADDED, added),
            (QueryObserver.MESSAGE_CHANGED, changed),
            (QueryObserver.MESSAGE_REMOVED, removed),
        ):
            # Make a copy of the subscribers set as the publish operation may yield and modify the set.
            for subscriber in self._subscribers.copy():
                session_publisher = publisher.RedisPublisher(facility=subscriber, broadcast=True)
                for row in rows:
                    session_publisher.publish_message(redis_store.RedisMessage(json.dumps({
                        'msg': message_type,
                        'observer': self.id,
                        'primary_key': self.primary_key,
                        'order': getattr(row, '_order', None),
                        'item': row,
                    })))

    def subscribe(self, subscriber):
        """
        Adds a new subscriber.
        """

        self._subscribers.add(subscriber)

    def unsubscribe(self, subscriber):
        """
        Unsubscribes a specific subscriber to this query observer. If no subscribers
        are left, this query observer is stopped.
        """

        try:
            self._subscribers.remove(subscriber)
        except KeyError:
            pass

        if not self._subscribers:
            self.stop()

    def stop(self):
        """
        Stops this query observer.
        """

        if self.status == QueryObserver.STATUS_STOPPED:
            return

        self.status = QueryObserver.STATUS_STOPPED

        # Unregister all dependencies.
        for dependency in self._dependencies:
            self._pool.unregister_dependency(self, dependency)

        # Unsubscribe all subscribers.
        for subscriber in self._subscribers:
            self._pool._remove_subscriber(self, subscriber)

        self._pool._remove_observer(self)

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)
