"""
The models defined here are only used during testing.
"""
from django.db import models


class ExampleItem(models.Model):
    enabled = models.BooleanField()
    name = models.CharField(max_length=30)

    class Meta:
        permissions = (("view_exampleitem", "Can view example item"),)
        default_permissions = ()
        ordering = ['pk']


class ExampleSubItem(models.Model):
    parent = models.ForeignKey(ExampleItem, on_delete=models.CASCADE)
    enabled = models.BooleanField()

    class Meta:
        permissions = (("view_examplesubitem", "Can view example sub item"),)
        default_permissions = ()
        ordering = ['pk']


class ExampleM2MItem(models.Model):
    value = models.IntegerField(default=1)
    items = models.ManyToManyField(ExampleItem, related_name='items')

    class Meta:
        ordering = ['pk']
