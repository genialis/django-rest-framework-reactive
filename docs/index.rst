
.. _index:

==============================
Django REST Framework Reactive
==============================

This package enables regular `Django REST Framework`_ views to become reactive,
that is so that client-side applications may get notified of changes to the
underlying data as soon as they happen, without the need to poll the API again.
While the initial request is done as a regular HTTP request, all the update
notifications come through WebSockets.

.. _Django REST Framework: https://www.django-rest-framework.org/

Contents
========

.. toctree::
   :maxdepth: 2

   CHANGELOG
