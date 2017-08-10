from __future__ import absolute_import, division, print_function, unicode_literals

import collections
import json
import logging
import sys
import time

import six

from django import db
from django.core import exceptions as django_exceptions
from django.http import Http404

from rest_framework import request as api_request
from ws4redis import publisher, redis_store

from . import exceptions
from .connection import get_queryobserver_settings

# Logger.
logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

# Observable method options attribute name prefix.
OBSERVABLE_OPTIONS_PREFIX = 'observable_'


class Options(object):
    """
    Query observer options.
    """

    # Valid change detection types.
    CHANGE_DETECTION_PUSH = 'push'
    CHANGE_DETECTION_POLL = 'poll'

    def __init__(self, viewset, viewset_method):
        self._viewset = viewset
        self._viewset_method = viewset_method

        # Determine the primary key.
        self.primary_key = self.get_option('primary_key')
        if self.primary_key is None:
            # Primary key attribute is not defined, attempt to autodiscover it from the queryset.
            try:
                self.primary_key = viewset.get_queryset().model._meta.pk.name
            except AssertionError:
                # No queryset is defined.
                raise exceptions.MissingPrimaryKey(
                    "Observable method does not define a primary key and the viewset "
                    "does not provide a queryset. Define a queryset or use the primary_key "
                    "decorator."
                )

        # Determine change detection type.
        self.change_detection = self.get_option('change_detection', Options.CHANGE_DETECTION_PUSH)
        self.poll_interval = self.get_option('poll_interval')

    def get_option(self, name, default=None):
        return getattr(self._viewset_method, '{}{}'.format(OBSERVABLE_OPTIONS_PREFIX, name), default)


class QueryObserver(object):
    """
    A query observer observes a specific viewset for changes and propagates these
    changes to all interested subscribers.
    """

    # Valid observer statuses.
    STATUS_NEW = 'new'
    STATUS_INITIALIZING = 'initializing'
    STATUS_OBSERVING = 'observing'
    STATUS_STOPPED = 'stopped'

    # Valid message types.
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
        viewset.request.method = request.method
        viewset.format_kwarg = None
        viewset.args = request.args
        viewset.kwargs = request.kwargs
        self._viewset = viewset
        self._request = request
        self._viewset_method = getattr(viewset, request.viewset_method)
        self._meta = Options(viewset, self._viewset_method)

        self._evaluating = 0
        self._last_evaluation = None
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

    @property
    def last_evaluation(self):
        """
        Timestamp of last evaluation. May be None if the observer was
        never evaluated.
        """

        return self._last_evaluation

    def _get_logging_extra(self, stopped=False, duration=None, results=None):
        """Extra information for logger."""
        return {
            'stopped': stopped,
            'duration': duration,
            'results': results,
            'observer_id': self.id,
            'viewset': '{}.{}'.format(
                self._request.viewset_class.__module__,
                self._request.viewset_class.__name__
            ),
            'method': self._request.viewset_method,
            'path': self._request.path,
            'get': self._request.GET,
            'pool': self._pool.statistics,
        }

    def _get_logging_id(self):
        """Get logging identifier."""
        return "{}.{}/{}".format(
            self._request.viewset_class.__module__,
            self._request.viewset_class.__name__,
            self._request.viewset_method,
        )

    def evaluate(self, return_full=True, return_emitted=False):
        """
        Evaluates the query observer and checks if there have been any changes. This function
        may yield.

        :param return_full: True if the full set of rows should be returned
        :param return_emitted: True if the emitted diffs should be returned
        """

        # Sanity check (should never happen).
        if self._evaluating < 0:
            logger.error("Corrupted internal observer state: _evaluating < 0",
                         extra=self._get_logging_extra(stopped=True))
            self.stop()
            return []

        if self._evaluating and not return_full:
            # Ignore evaluate requests if the observer is already being evaluated. Do
            # not ignore requests when full results are requested as in that case we
            # need to wait for the results (the caller needs them).
            return

        self._evaluating += 1

        try:
            # Increment evaluation statistics counter.
            self._pool._evaluations += 1
            self._pool._running += 1
            settings = get_queryobserver_settings()

            # After an update is processed, all incoming requests are batched until
            # the update batch delay passes. Batching is not performed when full
            # results are requested as in that case we want them as fast as possible.
            if self._last_evaluation is not None and not return_full:
                delta = time.time() - self._last_evaluation
                remaining = settings['update_batch_delay'] - delta

                if remaining > 0:
                    try:
                        self._pool._sleeping += 1

                        # We assume that time.sleep has been patched and will correctly yield.
                        time.sleep(remaining)
                    finally:
                        self._pool._sleeping -= 1

            start = time.time()
            result = self._evaluate(return_full, return_emitted)
            duration = time.time() - start
            self._last_evaluation = time.time()

            # Log slow observers.
            if duration > settings['warnings']['max_processing_time']:
                logger.warning(
                    "Slow observed viewset ({})".format(self._get_logging_id()),
                    extra=self._get_logging_extra(duration=duration)
                )

            # Stop really slow observers.
            if duration > settings['errors']['max_processing_time']:
                logger.error(
                    "Stopped extremely slow observed viewset ({})".format(self._get_logging_id()),
                    extra=self._get_logging_extra(stopped=True, duration=duration)
                )
                self.stop()

            return result
        except exceptions.ObserverStopped:
            return []
        except:  # pylint: disable=bare-except
            # Stop crashing observers.
            self.stop()

            logger.exception(
                "Error while evaluating observer ({})".format(self._get_logging_id()),
                extra=self._get_logging_extra()
            )
            return []
        finally:
            self._evaluating -= 1
            self._pool._running -= 1

            # Cleanup any leftover connections. This is something that should not be executed
            # during tests as it would terminate the database connection.
            is_testing = sys.argv[1:2] == ['test']
            if not is_testing:
                db.close_old_connections()

    def _evaluate(self, return_full=True, return_emitted=False):
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
            self._initialization_future = self._pool.backend.create_future()
            self.status = QueryObserver.STATUS_INITIALIZING

        # Evaluate the query (this operation yields).
        tables = set()
        stop_observer = False
        with self._pool.query_interceptor.intercept(tables):
            try:
                response = self._viewset_method(
                    self._viewset.request,
                    *self._request.args,
                    **self._request.kwargs
                )

                if response.status_code == 200:
                    results = response.data

                    if not isinstance(results, list):
                        if isinstance(results, dict):
                            if 'results' in results and isinstance(results['results'], list):
                                # Support paginated results.
                                results = results['results']
                            else:
                                results[self._meta.primary_key] = 1
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

        if self._meta.change_detection == Options.CHANGE_DETECTION_PUSH:
            # Register table dependencies for push observables.
            for table in tables:
                self.add_dependency(table)
        elif self._meta.change_detection == Options.CHANGE_DETECTION_POLL:
            # Register poller.
            self._pool.register_poller(self)
        else:
            raise NotImplementedError("Change detection mechanism '{}' not implemented.".format(
                self._meta.change_detection
            ))

        # TODO: Only compute difference between old and new, ideally on the SQL server using hashes.
        new_results = collections.OrderedDict()

        if self.status == QueryObserver.STATUS_STOPPED:
            return []

        # Log viewsets with too much output.
        if len(results) > get_queryobserver_settings()['warnings']['max_result_length']:
            logger.warning(
                "Observed viewset returned too many results ({})".format(self._get_logging_id()),
                extra=self._get_logging_extra(results=len(results))
            )

        for order, row in enumerate(results):
            if not isinstance(row, dict):
                raise ValueError("Observable views must return a dictionary or a list of dictionaries!")

            row._order = order
            try:
                new_results[row[self._meta.primary_key]] = row
            except KeyError:
                raise KeyError("Observable view did not return primary key field '{}'!".format(self._meta.primary_key))

        # Process difference between old results and new results.
        added = []
        changed = []
        removed = []
        for row_id, row in six.iteritems(self._last_results):
            if row_id not in new_results:
                removed.append(row)

        for row_id, row in six.iteritems(new_results):
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
            # Must be wrapped in a list as it would otherwise not be JSON serializable
            # under Python 3, which returns an unserializable view instance.
            return list(self._last_results.values())

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
                        'primary_key': self._meta.primary_key,
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
        self._last_results.clear()

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

    def __repr__(self):
        return '<QueryObserver id="{id}" request={request}>'.format(
            id=self.id,
            request=repr(self._request)
        )
