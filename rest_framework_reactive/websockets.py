import cPickle as pickle

from django.conf import settings
from ws4redis import subscriber

from . import connection


class QueryObserverSubscriber(subscriber.RedisSubscriber):
    def set_pubsub_channels(self, request, channels):
        # Store the subscriber identifier so we can later unsubscribe.
        self._subscriber = request.path_info.replace(settings.WEBSOCKET_URL, '', 1)
        super(QueryObserverSubscriber, self).set_pubsub_channels(request, channels)

    def release(self):
        if hasattr(self, '_subscriber'):
            # Publish a message that the client has disconnected.
            self._connection.publish(connection.QUERYOBSERVER_REDIS_CHANNEL, pickle.dumps({
                'event': 'subscriber_gone',
                'subscriber': self._subscriber,
            }))

        super(QueryObserverSubscriber, self).release()
