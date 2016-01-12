import gevent
import gevent.monkey
import gevent.select
from gevent import pywsgi, event
import psycogreen.gevent

# Patch the I/O primitives and psycopg2 database driver to be greenlet-enabled.
gevent.monkey.patch_all(thread=False)
psycogreen.gevent.patch_psycopg()

import redis.connection
redis.connection.select = gevent.select.select

from django import db
from django.core import exceptions
from django.core.management import base

from genesis.queryobserver import rpc, connection
from genesis.queryobserver.pool import pool


class Command(base.BaseCommand):
    """
    Runs the query observers.
    """

    help = 'Runs the query observers'

    def handle(self, *args, **options):
        # Check if we are using the correct database engine configuration.
        if 'queryobservers' not in db.connections:
            raise exceptions.ImproperlyConfigured("Database configuration named 'queryobservers' must be configured.")

        if db.connections['queryobservers'].settings_dict['ENGINE'] != 'django_db_geventpool.backends.postgresql_psycopg2':
            raise exceptions.ImproperlyConfigured("Query observers require the geventpool database engine.")

        # Make the pool gevent-ready.
        pool.spawner = gevent.spawn
        pool.future_class = event.Event

        # Register the event handler for receiving model updates from the Django ORM.
        event_handler = rpc.RedisObserverEventHandler()
        gevent.spawn(event_handler)

        # Prepare the RPC server.
        info = connection.get_queryobserver_settings()
        rpc_server = pywsgi.WSGIServer((info['host'], info['port']), application=rpc.WSGIObserverCommandHandler(database='queryobservers'))
        rpc_server.serve_forever()
