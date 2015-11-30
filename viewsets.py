from rest_framework import response

from . import client

observer_client = client.QueryObserverClient()


class ObservableViewSetMixin(object):
    def list(self, request, *args, **kwargs):
        if 'observe' in request.query_params:
            # TODO: Validate the session identifier.
            session_id = request.query_params['observe']
            queryset = self.filter_queryset(self.get_queryset())
            data = observer_client.create_observer(queryset, session_id)
            return response.Response(data)
        else:
            # Standard REST API request without subscriptions.
            return super(ObservableViewSetMixin, self).list(request, *args, **kwargs)
