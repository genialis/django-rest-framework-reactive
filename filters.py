import guardian
from guardian import shortcuts
from rest_framework import filters


class QueryObservableFilterMixin(object):
    def is_observer_request(self, request):
        return 'observe' in request.query_params


class DjangoObjectPermissionsFilter(QueryObservableFilterMixin, filters.DjangoObjectPermissionsFilter):
    """
    A modified DjangoObjectPermissionsFilter, which properly supports query observers. This is
    needed because the original filter performs multiple queries, which would then cause the
    observed queryset to always return statically defined instances.
    """

    def filter_queryset(self, request, queryset, view):
        extra = {}
        user = request.user
        model_cls = queryset.model
        kwargs = {
            'app_label': model_cls._meta.app_label,
            'model_name': model_cls._meta.model_name
        }
        permission = self.perm_format % kwargs
        if guardian.VERSION >= (1, 3):
            # Maintain behavior compatibility with versions prior to 1.3
            extra = {'accept_global_perms': False}
        else:
            extra = {}

        if self.is_observer_request(request):
            # If this is a query observer, we must request the permissions filter to be executed
            # only later, during the observe cycle after the initial query is executed unchanged.
            extra.update({
                'user': user,
                'perms': permission,
            })
            view.register_queryset_filter(shortcuts.get_objects_for_user, extra, queryset_kwarg='klass')
            return queryset
        else:
            return shortcuts.get_objects_for_user(user, permission, queryset, **extra)
