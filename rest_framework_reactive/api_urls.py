from __future__ import absolute_import, division, print_function, unicode_literals

from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^unsubscribe', views.QueryObserverUnsubscribeView.as_view()),
]
