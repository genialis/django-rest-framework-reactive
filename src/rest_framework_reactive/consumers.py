import asyncio
import collections
import pickle

from asgiref.sync import async_to_sync
from channels.consumer import AsyncConsumer, SyncConsumer
from channels.generic.websocket import JsonWebsocketConsumer

from .models import Observer, Subscriber
from .observer import QueryObserver
from .protocol import *

# Maximum number of cached observer executors.
MAX_CACHED_EXECUTORS = 1024


class PollObserversConsumer(AsyncConsumer):
    """Consumer for polling observers."""

    async def poll_observer(self, message):
        """Poll observer after a delay."""
        # Sleep until we need to notify the observer.
        await asyncio.sleep(message['interval'])

        # Dispatch task to evaluate the observable.
        await self.channel_layer.send(
            CHANNEL_WORKER_NOTIFY,
            {
                'type': TYPE_EVALUATE_OBSERVER,
                'observer': message['observer'],
            }
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
        executor.evaluate(return_full=False)

    def orm_notify_table(self, message):
        """Process notification from ORM."""
        # Find all observers with dependencies on the given table and notify them.
        observers = list(
            Observer.objects.filter(
                dependencies__table=message['table']
            ).distinct('pk').values_list('pk', flat=True)
        )

        for observer in observers:
            async_to_sync(self.channel_layer.send)(
                CHANNEL_WORKER_NOTIFY,
                {
                    'type': TYPE_EVALUATE_OBSERVER,
                    'observer': observer,
                }
            )

    def observer_evaluate(self, message):
        """Evaluate observer."""
        try:
            observer = Observer.objects.only('pk', 'request').get(pk=message['observer'])
        except Observer.DoesNotExist:
            return

        self._evaluate(observer)


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
                self.send_json({
                    'msg': action,
                    'observer': message['observer'],
                    'primary_key': message['primary_key'],
                    'order': item['order'],
                    'item': item['data'],
                })
