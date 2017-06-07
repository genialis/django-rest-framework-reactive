from rest_framework import response

from . import client, observer, request as observer_request

observer_client = client.QueryObserverClient()


def observable(method):
    """
    A decorator, which makes the specified ViewSet method observable. If the
    decorated method returns a response containing a list of items, it must use
    the provided `LimitOffsetPagination` for any pagination. In case a non-list
    response is returned, the resulting item will be wrapped into a list.

    When multiple decorators are used, `observable` must be the first one
    to be applied as it needs access to the method name.
    """

    def wrapper(self, request, *args, **kwargs):
        if observer_request.OBSERVABLE_QUERY_PARAMETER in request.query_params:
            # TODO: Validate the session identifier.
            session_id = request.query_params[observer_request.OBSERVABLE_QUERY_PARAMETER]
            data = observer_client.create_observer(
                observer_request.Request(self.__class__, method.__name__, request, args, kwargs),
                session_id
            )
            return response.Response(data)
        else:
            # Non-reactive API.
            return method(self, request, *args, **kwargs)

    wrapper.is_observable = True

    # Copy over any special observable attributes.
    for attribute in dir(method):
        if attribute.startswith(observer.OBSERVABLE_OPTIONS_PREFIX):
            setattr(wrapper, attribute, getattr(method, attribute))

    return wrapper


def primary_key(name):
    """
    A decorator, which configures the primary key that should be used for
    tracking objects in an observable method.

    :param name: Name of the primary key field
    """

    def decorator(method):
        method.observable_primary_key = name
        return method

    return decorator


def polling_observable(interval):
    """
    A decorator, which configures the given observable as a polling
    observable. Instead of tracking changes based on notifications from
    the ORM, the observer is polled periodically.

    :param interval: Poll interval
    """

    def decorator(method):
        method.observable_change_detection = observer.Options.CHANGE_DETECTION_POLL
        method.observable_poll_interval = interval
        return method

    return decorator
