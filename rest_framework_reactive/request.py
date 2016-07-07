import hashlib

from django.http import request as http_request


class Request(http_request.HttpRequest):
    """
    A fake request used by the query observer to interact with the DRF views. This
    request class is picklable.
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
        self.GET = request._request.GET.copy()
        if 'observe' in self.GET:
            # Remove the original observe query parameter.
            del self.GET['observe']
        self.path = request._request.path
        self.path_info = request._request.path_info
        self._force_auth_user = request.user
        self._observe_id = None

    @property
    def observe_id(self):
        """
        Unique identifier that identifies the observer, which will be handling
        this request.
        """

        if self._observe_id is None:
            hasher = hashlib.sha256()
            hasher.update(self.viewset_class.__module__)
            hasher.update(self.viewset_class.__name__)
            hasher.update(self.viewset_method)
            # Arguments do not need to be taken into account as they are
            # derived from the request path, which is already accounted for.
            for key in sorted(self.GET.keys()):
                hasher.update(key)
                hasher.update(self.GET[key])
            hasher.update(self.path)
            hasher.update(self.path_info)
            if self._force_auth_user is not None:
                hasher.update(str(self._force_auth_user.id) or 'anonymous')
            else:
                hasher.update('anonymous')
            self._observe_id = hasher.hexdigest()

        return self._observe_id

    def __getstate__(self):
        return {
            'viewset_class': self.viewset_class,
            'viewset_method': self.viewset_method,
            'args': self.args,
            'kwargs': self.kwargs,
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
        self.GET = state['GET']
        self.path = state['path']
        self.path_info = state['path_info']
        self._force_auth_user = state['user']
        self._observe_id = state['observe_id']
