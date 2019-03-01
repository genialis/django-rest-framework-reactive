from rest_framework import response, views

from . import observer


class QueryObserverUnsubscribeView(views.APIView):
    def post(self, request):
        """Handle a query observer unsubscription request."""
        try:
            observer_id = request.query_params['observer']
            session_id = request.query_params['subscriber']
        except KeyError:
            return response.Response(status=400)

        observer.remove_subscriber(session_id, observer_id)
        return response.Response()
