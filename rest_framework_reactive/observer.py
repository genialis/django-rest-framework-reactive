import collections
import pickle
import json
import logging
import sys
import time

import six

from django.core import exceptions as django_exceptions
from django.db import connection, transaction, IntegrityError
from django.http import Http404
from django.utils import timezone

from rest_framework import request as api_request

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from . import exceptions, models
from .connection import get_queryobserver_settings
from .interceptor import QueryInterceptor
from .protocol import *

# Logger.
logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

# Observable method options attribute name prefix.
OBSERVABLE_OPTIONS_PREFIX = 'observable_'
# Maximum number of retries in case of concurrent observer creates.
MAX_INTEGRITY_ERROR_RETRIES = 3


class Options(object):
    """Query observer options."""

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
    """Query observer.

    A query observer observes a specific viewset for changes and propagates these
    changes to all interested subscribers.
    """

    def __init__(self, request):
        """Create new query observer.

        :param request: A `queryobserver.request.Request` instance
        """

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

    @property
    def id(self):
        """Unique observer identifier."""
        return self._request.observe_id

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
        }

    def _get_logging_id(self):
        """Get logging identifier."""
        return "{}.{}/{}".format(
            self._request.viewset_class.__module__,
            self._request.viewset_class.__name__,
            self._request.viewset_method,
        )

    def evaluate(self, return_full=True, return_emitted=False):
        """Evaluate the query observer.

        :param return_full: True if the full set of rows should be returned
        :param return_emitted: True if the emitted diffs should be returned
        """

        try:
            settings = get_queryobserver_settings()

            for retry in range(MAX_INTEGRITY_ERROR_RETRIES):
                try:
                    with transaction.atomic():
                        # Obtain the observer state and lock it. This prevents an observer from being
                        # processed in parallel from multiple different workers.
                        observer, _ = models.Observer.objects.select_for_update().get_or_create(
                            id=self.id,
                            defaults={
                                'request': pickle.dumps(self._request),
                            },
                        )

                        # Evaluate the observer.
                        start = time.time()
                        result = self._evaluate(observer, return_full, return_emitted)
                        duration = time.time() - start

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
                            observer.delete()

                        return result
                except IntegrityError:
                    # If an IntegrityError occurrs we need to rollback the transaction and retry observer
                    # evaluation as another transaction may be creating an observer concurrently.
                    if retry == MAX_INTEGRITY_ERROR_RETRIES - 1:
                        raise

                    continue

            # Should never be reached.
            assert False
        except:  # pylint: disable=bare-except
            logger.exception(
                "Error while evaluating observer ({})".format(self._get_logging_id()),
                extra=self._get_logging_extra()
            )
            return []

    def _evaluate(self, observer, return_full=True, return_emitted=False):
        """Evaluates the query observer.

        This method must be run in a transaction with the `observer` locked
        for update.

        :param observer: Observer state model instance
        :param return_full: True if the full set of rows should be returned
        :param return_emitted: True if the emitted diffs should be returned
        """
        # Evaluate the viewset, intercepting all queries to evaluate dependencies.
        tables = set()
        stop_observer = False
        with QueryInterceptor().intercept(tables):
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
                                results.setdefault(self._meta.primary_key, 1)
                                results = [collections.OrderedDict(results)]
                        else:
                            raise ValueError(
                                "Observable views must return a dictionary or a list of dictionaries!"
                            )
                else:
                    results = []
            except Http404:
                results = []
            except django_exceptions.ObjectDoesNotExist:
                # The evaluation may fail when certain dependent objects (like users) are removed
                # from the database. In this case, the observer is stopped.
                stop_observer = True

        # Check if observer should be stopped.
        if stop_observer:
            observer.delete()
            return []

        # Determine who should notify us based on the configured change detection mechanism.
        if self._meta.change_detection == Options.CHANGE_DETECTION_PUSH:
            # Register table dependencies for push observables.
            for table in tables:
                models.Dependency.objects.get_or_create(
                    observer=observer,
                    table=table,
                )

            # If there are no dependencies, this observer should be stopped.
            if not tables:
                logger.warning(
                    "Stopping push-based observer without dependencies ({})".format(self._get_logging_id()),
                    extra=self._get_logging_extra(stopped=True)
                )

                stop_observer = True
        elif self._meta.change_detection == Options.CHANGE_DETECTION_POLL:
            # Register poller.
            observer.poll_interval = self._meta.poll_interval

            async_to_sync(get_channel_layer().send)(
                CHANNEL_POLL_OBSERVER,
                {
                    'type': TYPE_POLL_OBSERVER,
                    'observer': self.id,
                    'interval': self._meta.poll_interval,
                },
            )
        else:
            raise NotImplementedError("Change detection mechanism '{}' not implemented.".format(
                self._meta.change_detection
            ))

        # Update last evaluation time.
        if not stop_observer:
            observer.last_evaluation = timezone.now()
            observer.save()

        # Log viewsets with too much output.
        max_result_length = get_queryobserver_settings()['warnings']['max_result_length']
        if len(results) > max_result_length:
            logger.warning(
                "Observed viewset returned too many results ({})".format(self._get_logging_id()),
                extra=self._get_logging_extra(results=len(results))
            )

        new_results = collections.OrderedDict()
        for order, item in enumerate(results):
            if not isinstance(item, dict):
                raise ValueError("Observable views must return a dictionary or a list of dictionaries!")

            item = {
                'order': order,
                'data': item,
            }

            try:
                new_results[str(item['data'][self._meta.primary_key])] = item
            except KeyError:
                raise KeyError(
                    "Observable view did not return primary key field '{}'!".format(self._meta.primary_key)
                )

        # Process difference between old results and new results.
        added = []
        changed = []
        removed = []

        new_ids = list(new_results.keys())
        removed_qs = observer.items.exclude(primary_key__in=new_results.keys())
        maybe_changed_qs = observer.items.filter(primary_key__in=new_results.keys())

        # Removed items.
        removed = list(removed_qs.values('order', 'data'))
        removed_qs.delete()

        # Defer unique ordering constraint before processing order updates.
        # NOTE: The name of the constrait is generated by Django ORM.
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS rest_framework_reactive_item_observer_id_order_9b8adde6_uniq DEFERRED")

        # Changed items.
        for item_id, old_order, old_data in maybe_changed_qs.values_list('primary_key', 'order', 'data'):
            new_item = new_results[item_id]
            new_ids.remove(item_id)

            if new_item['data'] != old_data:
                changed.append(new_item)
                observer.items.filter(primary_key=item_id).update(data=new_item['data'], order=new_item['order'])
            elif new_item['order'] != old_order:
                # TODO: If only order has changed, don't transmit full data (needs frontend support).
                changed.append(new_item)
                observer.items.filter(primary_key=item_id).update(order=new_item['order'])

        # Added items.
        for item_id in new_ids:
            item = new_results[item_id]
            added.append(item)
            observer.items.create(
                primary_key=item_id,
                order=item['order'],
                data=item['data'],
            )

        # Check whether to emit results.
        if observer.status == models.Observer.STATUS_OBSERVING:
            message = {
                'type': TYPE_ITEM_UPDATE,
                'observer': self.id,
                'primary_key': self._meta.primary_key,
                'added': added,
                'changed': changed,
                'removed': removed,
            }

            # Stop an observer if there are no subscribers and we are in OBSERVING state.
            if not observer.subscribers.exists():
                stop_observer = True

            # Only generate notifications in case there were any changes.
            if added or changed or removed:
                for subscriber in observer.subscribers.all():
                    async_to_sync(get_channel_layer().group_send)(
                        GROUP_SESSIONS.format(session_id=subscriber.session_id),
                        message,
                    )

            if return_emitted:
                if stop_observer:
                    observer.delete()

                return (added, changed, removed)
        elif not stop_observer:
            # Switch observer status to OBSERVING.
            observer.status = models.Observer.STATUS_OBSERVING
            observer.save()

        if stop_observer:
            observer.delete()

        if return_full:
            return [item['data'] for item in new_results.values()]

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return '<QueryObserver: id={id} request={request}>'.format(
            id=self.id,
            request=repr(self._request)
        )


def add_subscriber(session_id, observer_id):
    """Add subscriber to the given observer.

    :param session_id: Subscriber's session identifier
    :param observer_id: Observer identifier
    """
    with transaction.atomic():
        try:
            observer = models.Observer.objects.get(pk=observer_id)
        except models.Observer.DoesNotExist:
            return

        subscriber, _ = models.Subscriber.objects.get_or_create(session_id=session_id)
        observer.subscribers.add(subscriber)


def remove_subscriber(session_id, observer_id):
    """Remove subscriber from the given observer.

    :param session_id: Subscriber's session identifier
    :param observer_id: Observer identifier
    """
    models.Observer.subscribers.through.objects.filter(
        subscriber_id=session_id,
        observer_id=observer_id
    ).delete()
