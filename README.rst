==============================
Django REST Framework Reactive
==============================

This package enables regular Django REST Framework views to become reactive,
that is so that client-side applications may get notified of changes to the
underlying data as soon as they happen, without the need to poll the API
again. While the initial request is done as a regular HTTP request, all the
update notifications come through WebSockets.

Install
=======

Prerequisites
-------------

The reactive extensions for Django REST Framework currently require the use of
`django-websocket-redis` for push notifications. When Channels get merged into
Django mainline, we will probably migrate to using those.

.. _`django-websocket-redis`: https://github.com/jrief/django-websocket-redis

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

There are several things that need to be configured in the Django settings file:

* ``rest_framework_reactive`` needs to be added to ``INSTALLED_APPS``.
* ``DEFAULT_PAGINATION_CLASS`` needs to be set to ``rest_framework_reactive.pagination.LimitOffsetPagination`` (optionally, this pagination class can instead be set for all viewsets configured for reactivity).
* ``WS4REDIS_SUBSCRIBER`` needs to be set to ``rest_framework_reactive.websockets.QueryObserverSubscriber``.
* ``DJANGO_REST_FRAMEWORK_REACTIVE`` needs to be configured with hostname and port where the internal RPC will live. It should be set to something like::

     DJANGO_REST_FRAMEWORK_REACTIVE = {
        'host': 'localhost',
        'port': 9432,
     }

  The hostname and port must be such that they are reachable from the Django application server.


Each ``ViewSet`` that should support reactivity, must be registered by using:

.. code::

   from rest_framework_reactive.pool import pool
   pool.register_viewset(MyViewSet)

The best place to do this is inside ``models.py`` or better, inside the ``ready`` handler
of an ``AppConfig``.

At the moment, you are required to change your project's ``manage.py`` to monkey patch
the ``runobservers`` command with support for gevent coroutines. Note that regular Django
application server still runs as normal, only the observer process runs using coroutines.

The modified ``manage.py`` should look as follows:

.. code::

   #!/usr/bin/env python
   import os
   import sys

   if __name__ == "__main__":
       os.environ.setdefault("DJANGO_SETTINGS_MODULE", "genesis.settings.development")

       # This is needed here so the monkey patching is done before Django ORM is loaded. If we
       # do it inside the 'runobservers' management command, it is already too late as a database
       # connection has already been created using thread identifiers, which become invalid
       # after monkey patching.
       if 'runobservers' in sys.argv:
           import gevent.monkey
           import psycogreen.gevent

           # Patch the I/O primitives and psycopg2 database driver to be greenlet-enabled.
           gevent.monkey.patch_all()
           psycogreen.gevent.patch_psycopg()

       from django.core.management import execute_from_command_line

       execute_from_command_line(sys.argv)

And finally, ``urls.py`` need to be updated to include some additional paths:

.. code::

   urlpatterns = [
     # ...
     url(r'^api/queryobserver/', include('rest_framework_reactive.api_urls')),
     # ...
   ]

Run
===

In addition to running a Django application server instance, you need to also run a
separate observer process. You may start it by running:

.. code::

   python manage.py runobservers

