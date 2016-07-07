from . import decorators


class ObservableViewSetMixin(object):
    @decorators.observable
    def list(self, request, *args, **kwargs):
        return super(ObservableViewSetMixin, self).list(request, *args, **kwargs)
