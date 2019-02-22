import asyncio
import collections
import pickle

from asgiref.sync import async_to_sync
from channels.consumer import AsyncConsumer, SyncConsumer
from channels.generic.websocket import JsonWebsocketConsumer

from django.core.cache import cache

from .connection import get_queryobserver_settings
from .models import Observer, Subscriber
from .observer import QueryObserver
from .protocol import *

# Maximum number of cached observer executors.
MAX_CACHED_EXECUTORS = 1024
# Throttle constants
THROTTLE_CACHE_PREFIX = 'drf_reactive_observer_throttle_'
THROTTLE_SEMAPHORE_DELAY = 'delay'
THROTTLE_SEMAPHORE_EVALUATE = 'evaluate'
THROTTLE_SEMAPHORE_IGNORE = 'ignore'


def throttle_cache_key(observer_id):
    return '{}{}'.format(THROTTLE_CACHE_PREFIX, observer_id)


def throttle_semaphore(observer_id):
    """Check if observer should be evaluated, delayed or ignored.

    Increase the observer counter if throttle cache exists.
    """
    cache_key = throttle_cache_key(observer_id)
    throttle_rate = get_queryobserver_settings()['throttle_rate']

    try:
        count = cache.incr(cache_key)
        # Ignore if delayed observer already scheduled.
        return THROTTLE_SEMAPHORE_DELAY if count == 2 else THROTTLE_SEMAPHORE_IGNORE
    except ValueError:
        count = cache.get_or_set(cache_key, default=1, timeout=throttle_rate)
        # Ignore if cache was set and increased in another thread.
        return THROTTLE_SEMAPHORE_EVALUATE if count == 1 else THROTTLE_SEMAPHORE_IGNORE

    assert False  # This should never happen.


class PollObserversConsumer(AsyncConsumer):
    """Consumer for polling observers."""

    async def poll_observer(self, message):
        """Poll observer after a delay."""
        # Sleep until we need to notify the observer.
        await asyncio.sleep(message['interval'])

        # Dispatch task to evaluate the observable.
        await self.channel_layer.send(
            CHANNEL_WORKER_NOTIFY,
            {'type': TYPE_EVALUATE_OBSERVER, 'observer': message['observer']},
        )


class ThrottleConsumer(AsyncConsumer):
    """Consumer for throttling observer evaluations."""

    async def delay_observer_evaluate(self, message):
        """Throttle observer evaluation."""
        observer_id = message['observer']
        throttle_rate = get_queryobserver_settings()['throttle_rate']

        # Sleep until we need to schedule the next evaluation.
        await asyncio.sleep(throttle_rate)

        # Dispatch task to evaluate the observable.
        await self.channel_layer.send(
            CHANNEL_WORKER_NOTIFY,
            {'type': TYPE_EVALUATE_OBSERVER, 'observer': observer_id},
        )


class WorkerConsumer(SyncConsumer):
    """Worker consumer."""

    def __init__(self, *args, **kwargs):
        """Construct observer worker consumer."""
        self._executor_cache = collections.OrderedDict()
        super().__init__(*args, **kwargs)

    def _get_executor(self, state):
        """Get executor for given observer's state."""
        try:
            executor = self._executor_cache[state.pk]
            self._executor_cache.move_to_end(state.pk)
        except KeyError:
            executor = QueryObserver(pickle.loads(state.request))
            self._executor_cache[state.pk] = executor
            if len(self._executor_cache) > MAX_CACHED_EXECUTORS:
                self._executor_cache.popitem(last=False)

        return executor

    def _evaluate(self, state):
        """Evaluate observer based on state."""
        # Load state into an executor.
        executor = self._get_executor(state)

        # Evaluate observer.
        executor.evaluate()

    def orm_notify_table(self, message):
        """Process notification from ORM."""
        # Find all observers with dependencies on the given table and notify them.
        observers = list(
            Observer.objects.filter(
                dependencies__table=message['table'], subscribers__isnull=False
            )
            .distinct('pk')
            .values_list('pk', flat=True)
        )

        for observer_id in observers:
            async_to_sync(self.channel_layer.send)(
                CHANNEL_WORKER_NOTIFY,
                {'type': TYPE_EVALUATE_OBSERVER, 'observer': observer_id},
            )

    def observer_evaluate(self, message):
        """Evaluate observer."""
        observer_id = message['observer']
        throttle_rate = get_queryobserver_settings()['throttle_rate']

        try:
            observer = Observer.objects.only('pk', 'request').get(pk=observer_id)
        except Observer.DoesNotExist:
            return

        if throttle_rate <= 0:
            # Evaluate observer.
            self._evaluate(observer)
            return

        action = throttle_semaphore(observer_id)
        if action == THROTTLE_SEMAPHORE_EVALUATE:
            # Evaluate observer.
            self._evaluate(observer)
        elif action == THROTTLE_SEMAPHORE_DELAY:
            # Delay observer by throttle rate.
            async_to_sync(self.channel_layer.send)(
                CHANNEL_THROTTLE, {'type': TYPE_THROTTLE, 'observer': observer_id}
            )


class ClientConsumer(JsonWebsocketConsumer):
    """Client consumer."""

    def websocket_connect(self, message):
        """Called when WebSocket connection is established."""
        self.session_id = self.scope['url_route']['kwargs']['subscriber_id']
        super().websocket_connect(message)

        # Create new subscriber object.
        Subscriber.objects.get_or_create(session_id=self.session_id)

    @property
    def groups(self):
        """Groups this channel should add itself to."""
        if not hasattr(self, 'session_id'):
            return []

        return [GROUP_SESSIONS.format(session_id=self.session_id)]

    def disconnect(self, code):
        """Called when WebSocket connection is closed."""
        Subscriber.objects.filter(session_id=self.session_id).delete()

    def observer_update(self, message):
        """Called when update from observer is received."""
        # Demultiplex observer update into multiple messages.
        for action in ('added', 'changed', 'removed'):
            for item in message[action]:
                self.send_json(
                    {
                        'msg': action,
                        'observer': message['observer'],
                        'primary_key': message['primary_key'],
                        'order': item['order'],
                        'item': item['data'],
                    }
                )
