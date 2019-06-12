from django.urls import path

from . import views

urlpatterns = [path('unsubscribe', views.QueryObserverUnsubscribeView.as_view())]
