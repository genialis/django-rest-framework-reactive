import gevent
import gevent.monkey
import gevent.select
from gevent import pywsgi, event
import psycogreen.gevent

# Patch the I/O primitives and psycopg2 database driver to be greenlet-enabled.
gevent.monkey.patch_all()
psycogreen.gevent.patch_psycopg()

import redis.connection
redis.connection.select = gevent.select.select

from django import db
from django.core import exceptions
from django.core.management import base

from ... import rpc, connection
from ...pool import pool


class Command(base.BaseCommand):
    """
    Runs the query observers.
    """

    help = 'Runs the query observers'

    def handle(self, *args, **options):
        # Check if we are using the correct database engine configuration.
        if db.connection.settings_dict['ENGINE'] != 'django_db_geventpool.backends.postgresql_psycopg2':
            raise exceptions.ImproperlyConfigured("Django REST Framework Reactive requires the geventpool database engine.")

        # Make the pool gevent-ready.
        pool.spawner = gevent.spawn
        pool.future_class = event.Event
        pool.thread_id = gevent.getcurrent

        # Register the event handler for receiving model updates from the Django ORM.
        event_handler = rpc.RedisObserverEventHandler()
        gevent.spawn(event_handler)

        # Prepare the RPC server.
        info = connection.get_queryobserver_settings()
        rpc_server = pywsgi.WSGIServer((info['host'], info['port']), application=rpc.WSGIObserverCommandHandler())
        rpc_server.serve_forever()
