"""
The models defined here are only used during testing.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

from django.db import models


class ExampleItem(models.Model):
    enabled = models.BooleanField()
    name = models.CharField(max_length=30)

    class Meta:
        permissions = (
            ("view_exampleitem", "Can view example item"),
        )
        ordering = ['pk']


class ExampleSubItem(models.Model):
    parent = models.ForeignKey(ExampleItem)
    enabled = models.BooleanField()

    class Meta:
        permissions = (
            ("view_examplesubitem", "Can view example sub item"),
        )
        ordering = ['pk']


class ExampleM2MItem(models.Model):
    value = models.IntegerField(default=1)
    items = models.ManyToManyField(ExampleItem, related_name='items')

    class Meta:
        ordering = ['pk']
