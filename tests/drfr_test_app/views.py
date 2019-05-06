"""The views defined here are only used during testing."""
import time

from rest_framework import mixins, viewsets
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from rest_framework_reactive.decorators import observable

from . import models, serializers


@observable
class ExampleItemViewSet(
    mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):

    queryset = models.ExampleItem.objects.all()
    serializer_class = serializers.ExampleItemSerializer
    filterset_fields = ('name', 'enabled', 'items')


@observable(dependencies=[models.ExampleSubItem, models.ExampleItem])
class ExampleSubItemViewSet(
    mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):

    queryset = models.ExampleSubItem.objects.all()
    serializer_class = serializers.ExampleSubItemSerializer
    filterset_fields = ('parent__enabled', 'enabled')


@observable
class PaginatedViewSet(
    mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):

    queryset = models.ExampleItem.objects.all()
    serializer_class = serializers.ExampleItemSerializer
    pagination_class = LimitOffsetPagination


@observable(dependencies=[models.ExampleItem, models.ExampleM2MItem.items.through])
class AggregationTestViewSet(
    mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):

    queryset = models.ExampleItem.objects.all()
    serializer_class = serializers.ExampleItemSerializer
    filterset_fields = ('items',)

    def list(self, request, *args, **kwargs):
        """Filtered query, which just returns a count.

        Such a formulation is used to force the compiler to generate a
        subquery, which uses the M2M relation.
        """
        queryset = self.filter_queryset(self.get_queryset())
        return Response({'count': queryset.count()})


class PollingObservableViewSet(
    mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):

    queryset = models.ExampleItem.objects.none()
    serializer_class = serializers.ExampleItemSerializer

    @observable(poll_interval=2)
    def list(self, request, *args, **kwargs):
        return Response(
            {'static': 'This is a polling observable: {}'.format(time.time())}
        )


class NoDependenciesViewSet(
    mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):

    queryset = models.ExampleItem.objects.none()
    serializer_class = serializers.ExampleItemSerializer

    @observable
    def list(self, request, *args, **kwargs):
        return Response({'static': 'This has no dependencies'})
