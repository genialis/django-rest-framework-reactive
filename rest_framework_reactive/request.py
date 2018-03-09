import hashlib

from six import string_types, text_type

from django.http import request as http_request

# Observable query parameter name.
OBSERVABLE_QUERY_PARAMETER = 'observe'


class Request(http_request.HttpRequest):
    """Request used by the query observer to interact with the viewsets.

    This request class is picklable.
    """

    def __init__(self, viewset_class, viewset_method, request, args=None, kwargs=None):
        """
        :param request: The original API request
        """

        super(Request, self).__init__()

        self.viewset_class = viewset_class
        self.viewset_method = viewset_method
        self.args = args or []
        self.kwargs = kwargs or {}

        # Copy relevant fields from the original request.
        self.method = request.method
        self.META = {}
        for key, value in request._request.META.items():
            if isinstance(value, string_types):
                self.META[key] = value
        self.GET = request._request.GET.copy()
        if OBSERVABLE_QUERY_PARAMETER in self.GET:
            # Remove the original observe query parameter.
            del self.GET[OBSERVABLE_QUERY_PARAMETER]
        self.path = request._request.path
        self.path_info = request._request.path_info
        self._force_auth_user = request.user
        self._observe_id = None

    @property
    def observe_id(self):
        """Unique identifier that identifies the observer."""
        if self._observe_id is None:
            hasher = hashlib.sha256()
            hasher.update(self.viewset_class.__module__.encode('utf8'))
            hasher.update(self.viewset_class.__name__.encode('utf8'))
            hasher.update(self.viewset_method.encode('utf8'))
            # Arguments do not need to be taken into account as they are
            # derived from the request path, which is already accounted for.
            for key in sorted(self.GET.keys()):
                hasher.update(key.encode('utf8'))
                hasher.update(self.GET[key].encode('utf8'))
            hasher.update(self.path.encode('utf8'))
            hasher.update(self.path_info.encode('utf8'))
            if self._force_auth_user is not None:
                hasher.update((text_type(self._force_auth_user.id) or 'anonymous').encode('utf8'))
            else:
                hasher.update(b'anonymous')
            self._observe_id = hasher.hexdigest()

        return self._observe_id

    def __getstate__(self):
        return {
            'viewset_class': self.viewset_class,
            'viewset_method': self.viewset_method,
            'args': self.args,
            'kwargs': self.kwargs,
            'method': self.method,
            'META': self.META,
            'GET': self.GET,
            'path': self.path,
            'path_info': self.path_info,
            'user': self._force_auth_user,
            'observe_id': self._observe_id
        }

    def __setstate__(self, state):
        self.viewset_class = state['viewset_class']
        self.viewset_method = state['viewset_method']
        self.args = state['args']
        self.kwargs = state['kwargs']
        self.method = state['method']
        self.META = state['META']
        self.GET = state['GET']
        self.path = state['path']
        self.path_info = state['path_info']
        self._force_auth_user = state['user']
        self._observe_id = state['observe_id']

    def __repr__(self):
        return '<Request: viewset={viewset} method={method} path={path} query={get}>'.format(
            viewset=repr(self.viewset_class),
            method=self.viewset_method,
            path=self.path,
            get=repr(self.GET),
        )
