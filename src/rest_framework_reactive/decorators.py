import functools
import inspect

from rest_framework import response

from . import observer
from . import request as observer_request


def observable(
    _method_or_viewset=None, poll_interval=None, primary_key=None, dependencies=None
):
    """Make ViewSet or ViewSet method observable.

    Decorating a ViewSet class is the same as decorating its `list` method.

    If decorated method returns a response containing a list of items, it must
    use the provided `LimitOffsetPagination` for any pagination. In case a
    non-list response is returned, the resulting item will be wrapped into a
    list.

    When multiple decorators are used, `observable` must be the first one to be
    applied as it needs access to the method name.

    :param poll_interval: Configure given observable as a polling observable
    :param primary_key: Primary key for tracking observable items
    :param dependencies: List of ORM to register as dependencies for
        orm_notify. If None the observer will subscribe to notifications from
        the queryset model.

    """
    if poll_interval and dependencies:
        raise ValueError('Only one of poll_interval and dependencies arguments allowed')

    def decorator_observable(method_or_viewset):

        if inspect.isclass(method_or_viewset):
            list_method = getattr(method_or_viewset, 'list', None)
            if list_method is not None:
                method_or_viewset.list = observable(
                    list_method,
                    poll_interval=poll_interval,
                    primary_key=primary_key,
                    dependencies=dependencies,
                )

            return method_or_viewset

        # Do not decorate an already observable method twice.
        if getattr(method_or_viewset, 'is_observable', False):
            return method_or_viewset

        @functools.wraps(method_or_viewset)
        def wrapper(self, request, *args, **kwargs):
            if observer_request.OBSERVABLE_QUERY_PARAMETER in request.query_params:
                # TODO: Validate the session identifier.
                session_id = request.query_params[
                    observer_request.OBSERVABLE_QUERY_PARAMETER
                ]

                # Create request and subscribe the session to given observer.
                request = observer_request.Request(
                    self.__class__, method_or_viewset.__name__, request, args, kwargs
                )

                # Initialize observer and subscribe.
                instance = observer.QueryObserver(request)
                data = instance.subscribe(session_id)

                return response.Response({'observer': instance.id, 'items': data})
            else:
                # Non-reactive API.
                return method_or_viewset(self, request, *args, **kwargs)

        wrapper.is_observable = True

        if poll_interval is not None:
            wrapper.observable_change_detection = observer.Options.CHANGE_DETECTION_POLL
            wrapper.observable_poll_interval = poll_interval

        if primary_key is not None:
            wrapper.observable_primary_key = primary_key

        if dependencies is not None:
            wrapper.observable_dependencies = dependencies

        return wrapper

    if _method_or_viewset is None:
        return decorator_observable
    else:
        return decorator_observable(_method_or_viewset)
