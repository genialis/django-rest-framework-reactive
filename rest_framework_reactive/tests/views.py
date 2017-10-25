"""
The views defined here are only used during testing.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

from rest_framework import mixins, viewsets
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from . import models, serializers


class ExampleItemViewSet(mixins.RetrieveModelMixin,
                         mixins.ListModelMixin,
                         viewsets.GenericViewSet):

    queryset = models.ExampleItem.objects.all()
    serializer_class = serializers.ExampleItemSerializer
    filter_fields = ('name', 'enabled', 'items')


class ExampleSubItemViewSet(mixins.RetrieveModelMixin,
                            mixins.ListModelMixin,
                            viewsets.GenericViewSet):

    queryset = models.ExampleSubItem.objects.all()
    serializer_class = serializers.ExampleSubItemSerializer
    filter_fields = ('parent__enabled', 'enabled')


class PaginatedViewSet(mixins.RetrieveModelMixin,
                       mixins.ListModelMixin,
                       viewsets.GenericViewSet):

    queryset = models.ExampleItem.objects.all()
    serializer_class = serializers.ExampleItemSerializer
    pagination_class = LimitOffsetPagination


class AggregationTestViewSet(mixins.RetrieveModelMixin,
                             mixins.ListModelMixin,
                             viewsets.GenericViewSet):

    queryset = models.ExampleItem.objects.all()
    serializer_class = serializers.ExampleItemSerializer
    filter_fields = ('items',)

    def list(self, request, *args, **kwargs):
        """Filtered query, which just returns a count.

        Such a formulation is used to force the compiler to generate a
        subquery, which uses the M2M relation.
        """
        queryset = self.filter_queryset(self.get_queryset())
        return Response({
            'count': queryset.count(),
        })
