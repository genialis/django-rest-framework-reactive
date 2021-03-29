import asyncio
import collections
import pickle

from channels.consumer import AsyncConsumer
from channels.db import database_sync_to_async
from channels.generic.websocket import JsonWebsocketConsumer
from django.core.cache import cache

from .connection import get_queryobserver_settings
from .models import Observer, Subscriber
from .observer import QueryObserver
from .protocol import *

# Maximum number of cached observer executors.
MAX_CACHED_EXECUTORS = 1024
# Throttle constants
THROTTLE_CACHE_PREFIX = 'rest_framework_reactive_throttle_'


def throttle_cache_key(observer_id):
    return '{}{}'.format(THROTTLE_CACHE_PREFIX, observer_id)


class MainConsumer(AsyncConsumer):
    """Consumer for polling observers."""

    async def observer_orm_notify(self, message):
        """Process notification from ORM."""

        @database_sync_to_async
        def get_observers(table):
            # Find all observers with dependencies on the given table.
            return list(
                Observer.objects.filter(
                    dependencies__table=table, subscribers__isnull=False
                )
                .distinct('pk')
                .values_list('pk', flat=True)
            )

        observers_ids = await get_observers(message['table'])

        for observer_id in observers_ids:
            await self.channel_layer.send(
                CHANNEL_WORKER, {'type': TYPE_EVALUATE, 'observer': observer_id}
            )

    async def observer_poll(self, message):
        """Poll observer after a delay."""
        # Sleep until we need to notify the observer.
        await asyncio.sleep(message['interval'])

        # Dispatch task to evaluate the observable.
        await self.channel_layer.send(
            CHANNEL_WORKER, {'type': TYPE_EVALUATE, 'observer': message['observer']}
        )


class WorkerConsumer(AsyncConsumer):
    """Worker consumer."""

    def __init__(self, *args, **kwargs):
        """Construct observer worker consumer."""
        self._executor_cache = collections.OrderedDict()

    async def _evaluate(self, observer_id):
        # Get Observer from database.
        @database_sync_to_async
        def get_observer(observer_id):
            try:
                return Observer.objects.only('pk', 'request').get(pk=observer_id)
            except Observer.DoesNotExist:
                return None

        observer = await get_observer(observer_id)
        if not observer:
            return

        # Get QueryObserver executor from cache and evaluate.
        try:
            executor = self._executor_cache[observer.pk]
            self._executor_cache.move_to_end(observer.pk)
        except KeyError:
            executor = QueryObserver(pickle.loads(observer.request))
            self._executor_cache[observer.pk] = executor
            if len(self._executor_cache) > MAX_CACHED_EXECUTORS:
                self._executor_cache.popitem(last=False)

        await executor.evaluate()

    async def observer_evaluate(self, message):
        """Execute observer evaluation on the worker or throttle."""
        observer_id = message['observer']
        throttle_rate = get_queryobserver_settings()['throttle_rate']
        if throttle_rate <= 0:
            await self._evaluate(observer_id)
            return

        cache_key = throttle_cache_key(observer_id)
        try:
            count = cache.incr(cache_key)
            # Ignore if delayed observer already scheduled.
            if count == 2:
                await self.channel_layer.send(
                    CHANNEL_MAIN,
                    {
                        'type': TYPE_POLL,
                        'observer': observer_id,
                        'interval': throttle_rate,
                    },
                )
        except ValueError:
            count = cache.get_or_set(cache_key, default=1, timeout=throttle_rate)
            # Ignore if cache was set and increased in another thread.
            if count == 1:
                await self._evaluate(observer_id)


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
