"""
The models defined here are only used during testing.
"""
from django.db import models


class ExampleItem(models.Model):
    enabled = models.BooleanField()
    name = models.CharField(max_length=30)

    class Meta:
        permissions = (
            ("view_exampleitem", "Can view example item"),
        )


class ExampleSubItem(models.Model):
    parent = models.ForeignKey(ExampleItem)
    enabled = models.BooleanField()

    class Meta:
        permissions = (
            ("view_examplesubitem", "Can view example sub item"),
        )
