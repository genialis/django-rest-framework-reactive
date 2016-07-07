from rest_framework import response

from . import client, request as observer_request

observer_client = client.QueryObserverClient()


def observable(method):
    """
    A decorator, which makes the specified ViewSet method observable. The
    decorated method must return a list of items and must use the provided
    `LimitOffsetPagination` for any pagination.

    When multiple decorators are used, `observable` must be the first one
    to be applied as it needs access to the method name.
    """

    def wrapper(self, request, *args, **kwargs):
        if 'observe' in request.query_params:
            # TODO: Validate the session identifier.
            session_id = request.query_params['observe']
            data = observer_client.create_observer(
                observer_request.Request(self.__class__, method.__name__, request),
                session_id
            )
            return response.Response(data)
        else:
            # Non-reactive API.
            return method(self, request, *args, **kwargs)

    return wrapper
