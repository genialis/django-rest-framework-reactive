from channels.generic.websockets import JsonWebsocketConsumer

from .connection import get_subscriber_group_id
from .client import QueryObserverClient


class ObserversConsumer(JsonWebsocketConsumer):
    """Consumer for handling observer websockets."""

    def __init__(self, *args, **kwargs):
        """Initialize consumer."""
        self._client = QueryObserverClient()
        super(ObserversConsumer, self).__init__(*args, **kwargs)

    def connection_groups(self, subscriber_id, **kwargs):
        """Groups the client should be in."""
        return [get_subscriber_group_id(subscriber_id)]

    def connect(self, message, subscriber_id, **kwargs):
        """New client has connected."""
        self.message.reply_channel.send({'accept': True})

    def receive(self, content, subscriber_id, **kwargs):
        """Message received from client."""
        pass

    def disconnect(self, message, subscriber_id, **kwargs):
        """Client has disconnected."""
        self._client.notify_subscriber_gone(subscriber_id)
