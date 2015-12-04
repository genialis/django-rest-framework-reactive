from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^unsubscribe', views.QueryObserverUnsubscribeView.as_view()),
]
