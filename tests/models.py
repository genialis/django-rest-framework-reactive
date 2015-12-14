"""
The models defined here are only used during testing.
"""
from django.db import models


class ExampleItem(models.Model):
    enabled = models.BooleanField()
    name = models.CharField(max_length=30)


class ExampleSubItem(models.Model):
    parent = models.ForeignKey(ExampleItem)
    enabled = models.BooleanField()
