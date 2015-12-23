from rest_framework import response

from . import client

observer_client = client.QueryObserverClient()


class ObservableViewSetMixin(object):
    def register_queryset_filter(self, filter, kwargs, queryset_kwarg='queryset'):
        """
        Registers a new deferred queryset filter. All arguments to this method must
        be serializable.

        :param filter: The filter function, which should return a filtered queryset
        :param kwargs: Keyword arguments to the filter function
        :param queryset_kwarg: Name of the argument accepting a queryset
        """

        if not hasattr(self, '_queryset_filters'):
            return

        self._queryset_filters.append((filter, kwargs, queryset_kwarg))

    def list(self, request, *args, **kwargs):
        if 'observe' in request.query_params:
            # TODO: Validate the session identifier.
            session_id = request.query_params['observe']
            self._queryset_filters = []
            try:
                queryset = self.filter_queryset(self.get_queryset())
                data = observer_client.create_observer(queryset, session_id, self._queryset_filters)
            finally:
                del self._queryset_filters

            return response.Response(data)
        else:
            # Standard REST API request without subscriptions.
            return super(ObservableViewSetMixin, self).list(request, *args, **kwargs)
