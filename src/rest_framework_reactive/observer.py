import collections
import logging
import pickle
import time

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.core import exceptions as django_exceptions
from django.db import IntegrityError, connection, transaction
from django.http import Http404
from django.utils import timezone
from rest_framework import request as api_request

from . import exceptions, models
from .connection import get_queryobserver_settings
from .protocol import *

# Logger.
logger = logging.getLogger(__name__)

# Observable method options attribute name prefix.
OBSERVABLE_OPTIONS_PREFIX = 'observable_'
# Maximum number of retries in case of concurrent observer creates.
MAX_INTEGRITY_ERROR_RETRIES = 3


class Options:
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
        self.change_detection = self.get_option(
            'change_detection', Options.CHANGE_DETECTION_PUSH
        )
        self.poll_interval = self.get_option('poll_interval')
        self.dependencies = self.get_option('dependencies')

    def get_option(self, name, default=None):
        return getattr(
            self._viewset_method,
            '{}{}'.format(OBSERVABLE_OPTIONS_PREFIX, name),
            default,
        )


class QueryObserver:
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
        self._request = request
        self._viewset = viewset
        self._viewset_method = getattr(viewset, request.viewset_method)
        self._meta = Options(viewset, self._viewset_method)

    @property
    def id(self):
        """Unique observer identifier."""
        return self._request.observe_id

    def _get_logging_extra(self, duration=None, results=None):
        """Extra information for logger."""
        return {
            'duration': duration,
            'results': results,
            'observer_id': self.id,
            'viewset': '{}.{}'.format(
                self._request.viewset_class.__module__,
                self._request.viewset_class.__name__,
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

    def _warning(self, msg, duration=None, results=None):
        """Log warnings."""
        logger.warning(
            "{} ({})".format(msg, self._get_logging_id()),
            extra=self._get_logging_extra(duration=duration, results=results),
        )

    def subscribe(self, session_id):
        """Initialize observer and register subscriber.

        :param session_id: Subscriber's session identifier
        """
        try:
            change_detection = self._meta.change_detection
            if change_detection not in [
                Options.CHANGE_DETECTION_PUSH,
                Options.CHANGE_DETECTION_POLL,
            ]:
                raise NotImplementedError(
                    "Change detection mechanism '{}' not implemented.".format(
                        change_detection
                    )
                )

            poll_interval = (
                self._meta.poll_interval
                if change_detection == Options.CHANGE_DETECTION_POLL
                else None
            )

            dependencies = self._meta.dependencies

            viewset_results = self._viewset_results()

            # Subscribe to observer in a single query. First, create an
            # observer, then create a subscriber, and finally subscribe to
            # the observer. If already subscribed, ignore the conflict.
            for retry in range(MAX_INTEGRITY_ERROR_RETRIES):
                is_subscribed = False
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        """
                        WITH inserted_observer AS (
                            INSERT into {observer_table} ("id", "request", "poll_interval")
                            VALUES (%(observer_id)s, %(request)s, %(poll_interval)s)
                            ON CONFLICT DO NOTHING
                        ), inserted_subscriber AS (
                            INSERT into {subscriber_table} ("session_id", "created")
                            VALUES (%(subscriber_id)s, NOW())
                            ON CONFLICT DO NOTHING
                        )
                        INSERT INTO {observer_subscribers_table} ("observer_id", "subscriber_id")
                        VALUES (%(observer_id)s, %(subscriber_id)s)
                        """.format(
                            observer_table=models.Observer._meta.db_table,
                            subscriber_table=models.Subscriber._meta.db_table,
                            observer_subscribers_table=models.Observer.subscribers.through._meta.db_table,
                        ),
                        params={
                            'observer_id': self.id,
                            'request': pickle.dumps(self._request),
                            'poll_interval': poll_interval,
                            'subscriber_id': session_id,
                        },
                    )
                    is_subscribed = True
                except IntegrityError as err:
                    msg = str(err)
                    if (
                        'Key (observer_id, subscriber_id)' in msg
                        and 'already exists' in msg
                    ):
                        # Subscriber already subscribed, we're good.
                        is_subscribed = True
                    elif (
                        'Key (observer_id)' in msg or 'Key (subscriber_id)' in msg
                    ) and 'not present in table' in msg:
                        # Could not subscribe because observer, subscriber or
                        # both are missing, retry.
                        if retry == MAX_INTEGRITY_ERROR_RETRIES - 1:
                            raise
                    else:
                        raise
                finally:
                    cursor.close()

                if is_subscribed:
                    break

            # Determine who should notify us based on the configured change
            # detection mechanism.
            if change_detection == Options.CHANGE_DETECTION_PUSH:
                if dependencies:
                    tables = [model._meta.db_table for model in dependencies]
                else:
                    tables = [self._viewset.get_queryset().model._meta.db_table]

                # Register table dependencies for push observables.
                for table in tables:
                    try:
                        models.Dependency.objects.get_or_create(
                            observer_id=self.id, table=table
                        )
                    except models.Observer.DoesNotExist:
                        # The observer was removed before dependency tables
                        # were created.
                        return viewset_results

            elif self._meta.change_detection == Options.CHANGE_DETECTION_POLL:
                # Register poller.
                async_to_sync(get_channel_layer().send)(
                    CHANNEL_MAIN,
                    {
                        'type': TYPE_POLL,
                        'observer': self.id,
                        'interval': self._meta.poll_interval,
                    },
                )

            self._evaluate(viewset_results)

        except Exception:
            logger.exception(
                "Error while subscribing to observer ({})".format(
                    self._get_logging_id()
                ),
                extra=self._get_logging_extra(),
            )

        return viewset_results

    async def evaluate(self):
        """Evaluate the query observer.

        :param return_emitted: True if the emitted diffs should be returned (testing only)
        """

        @database_sync_to_async
        def remove_subscribers():
            models.Observer.subscribers.through.objects.filter(
                observer_id=self.id
            ).delete()

        @database_sync_to_async
        def get_subscriber_sessions():
            return list(
                models.Observer.subscribers.through.objects.filter(observer_id=self.id)
                .distinct('subscriber_id')
                .values_list('subscriber_id', flat=True)
            )

        try:
            settings = get_queryobserver_settings()

            start = time.time()
            # Evaluate the observer
            added, changed, removed = await database_sync_to_async(self._evaluate)()
            duration = time.time() - start

            # Log slow observers.
            if duration > settings['warnings']['max_processing_time']:
                self._warning("Slow observed viewset", duration=duration)

            # Remove subscribers of really slow observers.
            if duration > settings['errors']['max_processing_time']:
                logger.error(
                    "Removing subscribers to extremely slow observed viewset ({})".format(
                        self._get_logging_id()
                    ),
                    extra=self._get_logging_extra(duration=duration),
                )
                await remove_subscribers()

            if self._meta.change_detection == Options.CHANGE_DETECTION_POLL:
                # Register poller.
                await get_channel_layer().send(
                    CHANNEL_MAIN,
                    {
                        'type': TYPE_POLL,
                        'observer': self.id,
                        'interval': self._meta.poll_interval,
                    },
                )

            message = {
                'type': TYPE_ITEM_UPDATE,
                'observer': self.id,
                'primary_key': self._meta.primary_key,
                'added': added,
                'changed': changed,
                'removed': removed,
            }

            # Only generate notifications in case there were any changes.
            if added or changed or removed:
                for session_id in await get_subscriber_sessions():
                    await get_channel_layer().group_send(
                        GROUP_SESSIONS.format(session_id=session_id), message
                    )

        except Exception:
            logger.exception(
                "Error while evaluating observer ({})".format(self._get_logging_id()),
                extra=self._get_logging_extra(),
            )

    def _viewset_results(self):
        """Parse results from the viewset response."""
        results = []
        try:
            response = self._viewset_method(
                self._viewset.request, *self._request.args, **self._request.kwargs
            )

            if response.status_code == 200:
                results = response.data

                if not isinstance(results, list):
                    if isinstance(results, dict):
                        # XXX: This can incidently match if a single
                        # object has results key
                        if 'results' in results and isinstance(
                            results['results'], list
                        ):
                            # Support paginated results.
                            results = results['results']
                        else:
                            results.setdefault(self._meta.primary_key, 1)
                            results = [collections.OrderedDict(results)]
                    else:
                        raise ValueError(
                            "Observable views must return a dictionary or a list of dictionaries!"
                        )
        except Http404:
            pass
        except django_exceptions.ObjectDoesNotExist:
            # The evaluation may fail when certain dependent objects (like users) are removed
            # from the database. In this case, the observer is stopped.
            pass

        return results

    def _evaluate(self, viewset_results=None):
        """Evaluate query observer.

        :param viewset_results: Objects returned by the viewset query
        """
        if viewset_results is None:
            viewset_results = self._viewset_results()

        try:
            observer = models.Observer.objects.get(id=self.id)
            # Do not evaluate the observer if there are no subscribers
            if observer.subscribers.count() == 0:
                return (None, None, None)

            # Update last evaluation time.
            models.Observer.objects.filter(id=self.id).update(
                last_evaluation=timezone.now()
            )

            # Log viewsets with too much output.
            max_result = get_queryobserver_settings()['warnings']['max_result_length']
            if len(viewset_results) > max_result:
                self._warning(
                    "Observed viewset returns too many results",
                    results=len(viewset_results),
                )
            new_results = collections.OrderedDict()
            for order, item in enumerate(viewset_results):
                if not isinstance(item, dict):
                    raise ValueError(
                        "Observable views must return a dictionary or a list of dictionaries!"
                    )

                item = {'order': order, 'data': item}

                try:
                    new_results[str(item['data'][self._meta.primary_key])] = item
                except KeyError:
                    raise KeyError(
                        "Observable view did not return primary key field '{}'!".format(
                            self._meta.primary_key
                        )
                    )

            # Process difference between old results and new results.
            added, changed = [], []
            new_ids = list(new_results.keys())

            removed_qs = observer.items.exclude(primary_key__in=new_results.keys())
            removed = list(removed_qs.values('order', 'data'))

            maybe_changed_qs = observer.items.filter(primary_key__in=new_results.keys())

            with transaction.atomic():
                # Removed items.
                removed_qs.delete()

                # Defer unique ordering constraint before processing order updates.
                # NOTE: The name of the constrait is generated by Django ORM.
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SET CONSTRAINTS rest_framework_reactive_item_observer_id_order_9b8adde6_uniq DEFERRED"
                    )

                # Changed items.
                for item_id, old_order, old_data in maybe_changed_qs.values_list(
                    'primary_key', 'order', 'data'
                ):
                    new_item = new_results[item_id]
                    new_ids.remove(item_id)

                    if new_item['data'] != old_data:
                        changed.append(new_item)
                        observer.items.filter(primary_key=item_id).update(
                            data=new_item['data'], order=new_item['order']
                        )
                    elif new_item['order'] != old_order:
                        # TODO: If only order has changed, don't transmit
                        # full data (needs frontend support).
                        changed.append(new_item)
                        observer.items.filter(primary_key=item_id).update(
                            order=new_item['order']
                        )

                # Added items.
                for item_id in new_ids:
                    item = new_results[item_id]
                    added.append(item)
                    observer.items.create(
                        primary_key=item_id, order=item['order'], data=item['data']
                    )

            return (added, changed, removed)

        except models.Observer.DoesNotExist:
            # Observer removed, ignore evaluation
            return (None, None, None)

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return '<QueryObserver: id={id} request={request}>'.format(
            id=self.id, request=repr(self._request)
        )


def remove_subscriber(session_id, observer_id):
    """Remove subscriber from the given observer.

    :param session_id: Subscriber's session identifier
    :param observer_id: Observer identifier
    """
    models.Observer.subscribers.through.objects.filter(
        subscriber_id=session_id, observer_id=observer_id
    ).delete()
