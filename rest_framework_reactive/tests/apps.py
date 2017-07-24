from __future__ import absolute_import, division, print_function, unicode_literals

from django import apps


class QueryObserverTestsConfig(apps.AppConfig):
    name = 'rest_framework_reactive.tests'
    label = 'rest_framework_reactive_tests'
