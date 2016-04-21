from rest_framework import views, response

from . import client

observer_client = client.QueryObserverClient()


class QueryObserverUnsubscribeView(views.APIView):
    def post(self, request):
        """
        Handles a query observer unsubscription request.
        """

        try:
            observer = request.query_params['observer']
            subscriber = request.query_params['subscriber']
        except KeyError:
            return response.Response(status=400)

        observer_client.unsubscribe_observer(observer, subscriber)
        return response.Response()
