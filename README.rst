==============================
Django REST Framework Reactive
==============================

|build|

.. |build| image:: https://travis-ci.org/genialis/django-rest-framework-reactive.svg?branch=master
    :target: https://travis-ci.org/genialis/django-rest-framework-reactive
    :alt: Build Status

This package enables regular Django REST Framework views to become reactive,
that is so that client-side applications may get notified of changes to the
underlying data as soon as they happen, without the need to poll the API
again. While the initial request is done as a regular HTTP request, all the
update notifications come through WebSockets.

Install
=======

Prerequisites
-------------

The reactive extensions for Django REST Framework require the use of `Django Channels`_
for push notifications via WebSockets.

.. _`Django Channels`: https://channels.readthedocs.io

From PyPI
---------

.. code::

    pip install djangorestframework-reactive

From source
-----------

.. code::

   pip install https://github.com/genialis/django-rest-framework-reactive/archive/<git-tree-ish>.tar.gz

where ``<git-tree-ish>`` can represent any commit SHA, branch name, tag name,
etc. in `DRF Reactive's GitHub repository`_. For example, to install the latest
version from the ``master`` branch, use:

.. code::

   pip install https://github.com/genialis/django-rest-framework-reactive/archive/master.tar.gz

.. _`DRF Reactive's GitHub repository`: https://github.com/genialis/django-rest-framework-reactive/


Configure
=========

First, add ``rest_framework_reactive`` to ``INSTALLED_APPS``.

Configure your Django Channels ``routing.py`` to include the required paths:

.. code::

    from django.conf.urls import url

    from channels.routing import ChannelNameRouter, ProtocolTypeRouter, URLRouter

    from rest_framework_reactive.consumers import ClientConsumer, PollObserversConsumer, WorkerConsumer
    from rest_framework_reactive.protocol import CHANNEL_POLL_OBSERVER, CHANNEL_WORKER_NOTIFY

    application = ProtocolTypeRouter({
        # Client-facing consumers.
        'websocket': URLRouter([
            # To change the prefix, you can import ClientConsumer in your custom
            # Channels routing definitions instead of using these defaults.
            url(r'^ws/(?P<subscriber_id>.+)$', ClientConsumer),
        ]),

        # Background worker consumers.
        'channel': ChannelNameRouter({
            CHANNEL_POLL_OBSERVER: PollObserversConsumer,
            CHANNEL_WORKER_NOTIFY: WorkerConsumer,
        })
    })

Also, ``urls.py`` need to be updated to include some additional paths:

.. code::

   urlpatterns = [
     # ...
     url(r'^api/queryobserver/', include('rest_framework_reactive.api_urls')),
     # ...
   ]

Run
===

In addition to running a Django application server instance, you need to also run a
separate observer worker process (or multiple of them). You may start it by running:

.. code::

   python manage.py runworker rest_framework_reactive.worker rest_framework_reactive.poll_observer
