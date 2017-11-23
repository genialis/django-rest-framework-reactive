from .consumers import ObserversConsumer


default_channel_routing = [
    # To change the prefix, you can import ObserversConsumer in your custom
    # Channels routing definitions instead of using these defaults.
    ObserversConsumer.as_route(path=r'^/ws/(?P<subscriber_id>.+)$'),
]
