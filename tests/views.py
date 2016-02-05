"""
The views defined here are only used during testing.
"""
from rest_framework import mixins, viewsets

from . import models, serializers


class ExampleItemViewSet(mixins.RetrieveModelMixin,
                         mixins.ListModelMixin,
                         viewsets.GenericViewSet):

    queryset = models.ExampleItem.objects.all()
    serializer_class = serializers.ExampleItemSerializer
    filter_fields = ('name', 'enabled')


class ExampleSubItemViewSet(mixins.RetrieveModelMixin,
                            mixins.ListModelMixin,
                            viewsets.GenericViewSet):

    queryset = models.ExampleSubItem.objects.all()
    serializer_class = serializers.ExampleSubItemSerializer
    filter_fields = ('parent__enabled', 'enabled')
