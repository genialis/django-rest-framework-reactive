import asyncio
import pickle

from channels.consumer import AsyncConsumer, SyncConsumer
from channels.generic.websocket import JsonWebsocketConsumer

from .models import Observer, Subscriber
from .observer import QueryObserver
from .protocol import GROUP_SESSIONS, TYPE_POLL_OBSERVER


class PollObserversConsumer(AsyncConsumer):
    """Consumer for polling observers."""

    async def poll_observer(self, message):
        """Poll observer after a delay."""
        # Sleep until we need to notify the observer.
        await asyncio.sleep(message['interval'])

        # Dispatch task to evaluate the observable.
        await self.send({
            'type': TYPE_POLL_OBSERVER,
            'observer': message['observer'],
        })


class WorkerConsumer(SyncConsumer):
    """Worker consumer."""

    def __init__(self, *args, **kwargs):
        """Construct observer worker consumer."""
        self._executor_cache = {}
        super().__init__(*args, **kwargs)

    def _get_executor(self, state):
        """Get executor for given observer's state."""
        try:
            return self._executor_cache[state.pk]
        except KeyError:
            executor = QueryObserver(pickle.loads(state.request))
            self._executor_cache[state.pk] = executor
            return executor

    def _evaluate(self, state):
        """Evaluate observer based on state."""
        # Load state into an executor.
        executor = self._get_executor(state)

        # Evaluate observer.
        executor.evaluate(return_full=False)

    def orm_notify_table(self, message):
        """Process notification from ORM."""
        # Find all observers with dependencies on the given table. Instantiate it immediately
        # to prevent us holding any locks on the table.
        observers = list(
            Observer.objects.filter(dependencies__table=message['table'])
                .distinct()
                .only('pk', 'request')
        )

        for state in observers:
            self._evaluate(state)

    def poll_observer(self, message):
        """Evaluate poll observer."""
        try:
            observer = Observer.objects.get(pk=message['observer'])
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
        Subscriber.objects.create(session_id=self.session_id)

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
        message.pop('type')

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
