"""
The serializers defined here are only used during testing.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

from rest_framework import serializers

from . import models


class ExampleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ExampleItem
        fields = ('id', 'enabled', 'name')


class ExampleSubItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ExampleSubItem
        fields = ('id', 'parent', 'enabled')
