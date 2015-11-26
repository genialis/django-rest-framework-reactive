import gevent

from . import observer, exceptions


class QueryObserverPool(object):
    def __init__(self):
        self._serializers = {}
        self._observers = {}
        self._tables = {}
        self._queue = set()
        self._pending_process = False

    def register_model(self, model, serializer):
        if model in self._serializers:
            raise exceptions.SerializerAlreadyRegistered

        self._serializers[model] = serializer

    def register_dependency(self, observer, table):
        self._tables.setdefault(table, set()).add(observer)

    def unregister_dependency(self, observer, table):
        self._tables[table].remove(observer)

    def get_serializer(self, model):
        try:
            return self._serializers[model]
        except KeyError:
            raise exceptions.SerializerNotRegistered

    def observe_queryset(self, queryset, subscriber):
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
        # Add all observers that depend on this table to the notification queue.
        self._queue.update(self._tables[table])
        self.process_notifications()

    def process_notifications(self):
        if self._pending_process:
            return
        self._pending_process = True
        gevent.spawn(self._process_notifications)

    def _process_notifications(self):
        self._pending_process = False
        queue = self._queue
        self._queue = set()

        for observer in queue:
            observer.evaluate()

pool = QueryObserverPool()
