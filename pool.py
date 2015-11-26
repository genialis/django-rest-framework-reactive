from . import observer, exceptions


class QueryObserverPool(object):
    def __init__(self):
        self._serializers = {}
        self._observers = {}

    def register_model(self, model, serializer):
        if model in self._serializers:
            raise exceptions.SerializerAlreadyRegistered

        self._serializers[model] = serializer

    def get_serializer(self, model):
        try:
            return self._serializers[model]
        except KeyError:
            raise exceptions.SerializerNotRegistered

    def observe_queryset(self, queryset, subscriber):
        query_observer = observer.QueryObserver(self, queryset)
        if query_observer in self._observers:
            query_observer = self._observers[query_observer]
        else:
            self._observers[query_observer] = query_observer

        query_observer.subscribe(subscriber)
        return query_observer.evaluate()

pool = QueryObserverPool()
