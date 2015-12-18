from django import db

from . import observer, exceptions, viewsets


def serializable(function):
    """
    A helper decorator to make query observer pool methods serializable
    using a local lock object.
    """

    def wrapper(self, *args, **kwargs):
        if self.lock is None:
            return function(self, *args, **kwargs)

        with self.lock:
            return function(self, *args, **kwargs)

    return wrapper


class QueryObserverPool(object):
    """
    A pool of query observers.
    """

    # Callable for deferring execution (for example gevent.spawn).
    spawner = lambda function: function()
    # Mutex for serializing access to the query observer pool. By default, a
    # dummy implementation that does no locking is used as multi-threaded
    # operation is only used during tests.
    lock = None

    def __init__(self):
        """
        Creates a new query observer pool.
        """

        self._serializers = {}
        self._observers = {}
        self._tables = {}
        self._subscribers = {}
        self._queue = set()
        self._pending_process = False

    @serializable
    def register_model(self, model, serializer, viewset=None):
        """
        Registers a new observable model.

        :param model: Model class
        :param serializer: Serializer class
        :param viewset: Optional DRF viewset
        """

        if model in self._serializers:
            raise exceptions.SerializerAlreadyRegistered

        self._serializers[model] = serializer

        # Patch viewset with our observable viewset mixin.
        if viewset is not None:
            viewset.__bases__ = (viewsets.ObservableViewSetMixin,) + viewset.__bases__

    @serializable
    def register_dependency(self, observer, table):
        """
        Registers a new dependency.

        :param observer: Query observer instance
        :param table: Dependent database table name
        """

        self._tables.setdefault(table, set()).add(observer)

    @serializable
    def unregister_dependency(self, observer, table):
        """
        Removes a registered dependency.

        :param observer: Query observer instance
        :param table: Dependent database table name
        """

        self._tables[table].remove(observer)

    @serializable
    def get_serializer(self, model):
        """
        Returns a registered model serializer.

        :param model: Model class
        :return: Serializer instance
        """

        try:
            return self._serializers[model]
        except KeyError:
            raise exceptions.SerializerNotRegistered

    @serializable
    def observe_queryset(self, queryset, subscriber):
        """
        Subscribes to observing of a queryset.

        :param queryset: The queryset to observe
        :param subscriber: Channel identifier of the subscriber
        :return: Query observer instance
        """

        query_observer = observer.QueryObserver(self, queryset)
        if query_observer.id in self._observers:
            existing = self._observers[query_observer.id]
            if not existing.stopped:
                query_observer = existing
            else:
                self._observers[query_observer.id] = query_observer
        else:
            self._observers[query_observer.id] = query_observer

        query_observer.subscribe(subscriber)
        self._subscribers.setdefault(subscriber, set()).add(query_observer)
        return query_observer

    @serializable
    def unobserve_queryset(self, observer_id, subscriber):
        """
        Unsubscribes from observing a queryset.

        :param observer_id: Query observer identifier
        :param subscriber: Channel identifier of the subscriber
        """

        try:
            query_observer = self._observers[observer_id]
            query_observer.unsubscribe(subscriber)

            # Update subscribers map.
            observers = self._subscribers[subscriber]
            observers.remove(query_observer)
            if not observers:
                del self._subscribers[subscriber]
        except KeyError:
            pass

    @serializable
    def stop_all(self):
        """
        Stops all query observers.
        """

        for observer in self._observers.values():
            observer.stop()

        self._observers = {}
        self._subscribers = {}

    @serializable
    def remove_subscriber(self, subscriber):
        """
        Removes a subscriber from all subscribed query observers.

        :param subscriber: Channel identifier of the subscriber
        """

        try:
            for observer in self._subscribers[subscriber]:
                observer.unsubscribe(subscriber)
            del self._subscribers[subscriber]
        except KeyError:
            pass

    @serializable
    def notify_update(self, table):
        """
        Notifies the observer pool that a database table has been updated.

        :param table: Database table name
        """

        if table not in self._tables:
            return

        # Add all observers that depend on this table to the notification queue.
        self._queue.update(self._tables[table])
        self.process_notifications()

    @serializable
    def process_notifications(self):
        """
        Schedules the notification queue processing.
        """

        if self._pending_process:
            return
        self._pending_process = True
        self.spawner(self._process_notifications)

    def _process_notifications(self):
        """
        Processes the notification queue.
        """

        self._pending_process = False
        queue = self._queue
        self._queue = set()

        try:
            for observer in queue:
                observer.evaluate(return_full=False)
        finally:
            db.close_old_connections()

# Global pool instance.
pool = QueryObserverPool()
