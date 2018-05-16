import inspect

from rest_framework import response, viewsets

from django.db import transaction

from . import observer, request as observer_request


def observable(method_or_viewset):
    """Make the specified ViewSet or ViewSet method  observable.

    Decorating a ViewSet class is the same as decorating its `list` method.

    If the decorated method returns a response containing a list of items, it
    must use the provided `LimitOffsetPagination` for any pagination. In case
    a non-list response is returned, the resulting item will be wrapped into
    a list.

    When multiple decorators are used, `observable` must be the first one to be
    applied as it needs access to the method name.
    """

    if inspect.isclass(method_or_viewset):
        list_method = getattr(method_or_viewset, 'list', None)
        if list_method is not None:
            method_or_viewset.list = observable(list_method)

        return method_or_viewset

    # Do not decorate an already observable method twice.
    if getattr(method_or_viewset, 'is_observable', False):
        return method_or_viewset

    def wrapper(self, request, *args, **kwargs):
        if observer_request.OBSERVABLE_QUERY_PARAMETER in request.query_params:
            # TODO: Validate the session identifier.
            session_id = request.query_params[observer_request.OBSERVABLE_QUERY_PARAMETER]

            # Create request and subscribe the session to given observer.
            request = observer_request.Request(self.__class__, method_or_viewset.__name__, request, args, kwargs)

            # Create and evaluate observer.
            instance = observer.QueryObserver(request)
            with transaction.atomic():
                data = instance.evaluate()
                observer.add_subscriber(session_id, instance.id)

            return response.Response({
                'observer': instance.id,
                'items': data,
            })
        else:
            # Non-reactive API.
            return method_or_viewset(self, request, *args, **kwargs)

    wrapper.is_observable = True

    # Copy over any special observable attributes.
    for attribute in dir(method_or_viewset):
        if attribute.startswith(observer.OBSERVABLE_OPTIONS_PREFIX):
            setattr(wrapper, attribute, getattr(method_or_viewset, attribute))

    return wrapper


def primary_key(name):
    """Set primary key for tracking observable items.

    :param name: Name of the primary key field
    """

    def decorator(method):
        method.observable_primary_key = name
        return method

    return decorator


def polling_observable(interval):
    """Set polling interval for a polling observable.

    A decorator which configures the given observable as a polling
    observable. Instead of tracking changes based on notifications from
    the ORM, the observer is polled periodically.

    :param interval: Poll interval
    """

    def decorator(method):
        method.observable_change_detection = observer.Options.CHANGE_DETECTION_POLL
        method.observable_poll_interval = interval
        return method

    return decorator
