from django.conf.urls import url

from channels.routing import ChannelNameRouter, ProtocolTypeRouter, URLRouter

from .consumers import ClientConsumer, PollObserversConsumer, WorkerConsumer
from .protocol import CHANNEL_POLL_OBSERVER, CHANNEL_WORKER_NOTIFY

application = ProtocolTypeRouter({
    # Client-facing consumers.
    'websocket': URLRouter([
        # To change the prefix, you can import ClientConsumer in your custom
        # Channels routing definitions instead of using these defaults.
        url(r'^ws/(?P<subscriber_id>.+)$', ClientConsumer),
    ]),

    # Background worker consumers.
    'channel': ChannelNameRouter({
        CHANNEL_POLL_OBSERVER: PollObserversConsumer,
        CHANNEL_WORKER_NOTIFY: WorkerConsumer,
    })
})
