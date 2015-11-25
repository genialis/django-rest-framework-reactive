import gevent


class QueryObserver(object):
    STATUS_INITIALIZING = 'initializing'
    STATUS_OBSERVING = 'observing'
    STATUS_STOPPED = 'stopped'

    def __init__(self, pool, queryset):
        """
        Creates a new query observer.

        :param pool: QueryObserverPool instance
        :param queryset: A QuerySet that should be observed
        """

        self.status = QueryObserver.STATUS_INITIALIZING
        self._queryset = queryset.all()
        self._query = queryset.query.sql_with_params()
        self._last_results = []
        self._subscribers = set()
        # TODO: Compute dependent models.
        # TODO: Subscribe to updates of dependent models?

        # Ensure that the target model is registered with a specific serializer.
        self._serializer = pool.get_serializer(self._queryset.model)

    def evaluate(self):
        # TODO: Evaluate the query again and compare results.
        pass

    def subscribe(self, subscriber):
        self._subscribers.add(subscriber)

    def unsubscribe(self, subscriber):
        self._subscribers.pop(subscriber)
        if not self._subscribers:
            self.stop()

    def stop(self):
        # TODO
        pass

    def __eq__(self, other):
        return self._query == other._query

    def __hash__(self):
        return hash(self._query)
