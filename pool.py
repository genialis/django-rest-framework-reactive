import gevent

from . import observer, exceptions


class QueryObserverPool(object):
    """
    A pool of query observers.
    """

    def __init__(self):
        """
        Creates a new query observer pool.
        """

        self._serializers = {}
        self._observers = {}
        self._tables = {}
        self._queue = set()
        self._pending_process = False

    def register_model(self, model, serializer):
        """
        Registers a new observable model.

        :param model: Model class
        :param serializer: Serializer class
        """

        if model in self._serializers:
            raise exceptions.SerializerAlreadyRegistered

        self._serializers[model] = serializer

    def register_dependency(self, observer, table):
        """
        Registers a new dependency.

        :param observer: Query observer instance
        :param table: Dependent database table name
        """

        self._tables.setdefault(table, set()).add(observer)

    def unregister_dependency(self, observer, table):
        """
        Removes a registered dependency.

        :param observer: Query observer instance
        :param table: Dependent database table name
        """

        self._tables[table].remove(observer)

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

    def observe_queryset(self, queryset, subscriber):
        """
        Subscribes to observing of a queryset.

        :param queryset: The queryset to observe
        :param subscriber: Channel identifier of the subscriber
        """

        query_observer = observer.QueryObserver(self, queryset)
        if query_observer in self._observers:
            existing = self._observers[query_observer]
            if not existing.stopped:
                query_observer = existing
            else:
                self._observers[query_observer] = query_observer
        else:
            self._observers[query_observer] = query_observer

        query_observer.subscribe(subscriber)
        return query_observer.evaluate()

    def notify_update(self, table):
        """
        Notifies the observer pool that a database table has been updated.

        :param table: Database table name
        """

        # Add all observers that depend on this table to the notification queue.
        self._queue.update(self._tables[table])
        self.process_notifications()

    def process_notifications(self):
        """
        Schedules the notification queue processing.
        """

        if self._pending_process:
            return
        self._pending_process = True
        gevent.spawn(self._process_notifications)

    def _process_notifications(self):
        """
        Processes the notification queue.
        """

        self._pending_process = False
        queue = self._queue
        self._queue = set()

        for observer in queue:
            observer.evaluate(return_full=False)

# Global pool instance.
pool = QueryObserverPool()
