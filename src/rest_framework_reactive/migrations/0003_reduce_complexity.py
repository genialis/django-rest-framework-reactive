# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-02-15 09:36
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('rest_framework_reactive', '0002_defer_order_constraint')]

    operations = [
        migrations.RemoveField(model_name='observer', name='status'),
        migrations.AlterField(
            model_name='observer',
            name='last_evaluation',
            field=models.DateTimeField(null=True),
        ),
    ]
