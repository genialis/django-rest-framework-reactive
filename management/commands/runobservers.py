import gevent
import gevent.monkey
from gevent import pywsgi
import psycogreen.gevent

# Patch the I/O primitives and psycopg2 database driver to be greenlet-enabled.
gevent.monkey.patch_all(thread=False)
psycogreen.gevent.patch_psycopg()

import redis
import redis.connection
import cPickle as pickle
import logging
import traceback
import json

from django import db
from django.core import exceptions
from django.core.management import base

from genesis.utils.formatters import BraceMessage as __
from genesis.queryobserver import connection
from genesis.queryobserver.pool import pool

# Logger.
logger = logging.getLogger(__name__)


class RedisObserverEventHandler(gevent.Greenlet):
    """
    Query observer handler that receives events via Redis.
    """

    def __init__(self):
        super(RedisObserverEventHandler, self).__init__()

    def _run(self):
        """
        Greenlet entry point.
        """

        # Establish a connection with Redis server.
        self._redis = redis.StrictRedis(**connection.get_redis_settings())
        self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        self._pubsub.subscribe(connection.QUERYOBSERVER_REDIS_CHANNEL)

        for event in self._pubsub.listen():
            # Events are assumed to be pickled data.
            try:
                event = pickle.loads(event['data'])
            except ValueError:
                logger.error(__("Ignoring received malformed event '{}'.", event['data'][:20]))
                continue

            # Handle event.
            try:
                event_name = event.pop('event')
                handler = getattr(self, 'event_%s' % event_name)
            except AttributeError:
                logger.error(__("Ignoring unimplemented event '{}'.", event_name))
                continue
            except KeyError:
                logger.error(__("Ignoring received malformed event '{}'.", event))
                continue

            try:
                handler(**event)
            except:
                logger.error(__("Unhandled exception while executing event '{}'.", event_name))
                logger.error(traceback.format_exc())
            finally:
                db.close_old_connections()

    def event_table_insert(self, table):
        pool.notify_update(table)

    def event_table_update(self, table):
        pool.notify_update(table)

    def event_table_remove(self, table):
        pool.notify_update(table)


class WSGIObserverCommandHandler(pywsgi.WSGIServer):
    """
    A WSGI-based RPC server for the query observer API.
    """

    def __init__(self, *args, **kwargs):
        """
        Constructs a new WSGI server for handling query observer RPC.
        """

        kwargs['application'] = self.handle_rpc_request
        super(WSGIObserverCommandHandler, self).__init__(*args, **kwargs)

    def handle_rpc_request(self, environ, start_response):
        """
        Handles an incoming RPC request.
        """

        try:
            request = pickle.loads(environ['wsgi.input'].read())
            if not isinstance(request, dict):
                raise ValueError

            command = request.pop('command')
            handler = getattr(self, 'command_%s' % command)
        except (KeyError, ValueError, AttributeError, EOFError):
            start_response('400 Bad Request', [('Content-Type', 'text/json')])
            return [json.dumps({'error': "Bad request."})]

        try:
            response = handler(**request)
            start_response('200 OK', [('Content-Type', 'text/json')])
            return [json.dumps(response)]
        except TypeError:
            start_response('400 Bad Request', [('Content-Type', 'text/json')])
            return [json.dumps({'error': "Bad request."})]
        except:
            logger.error(__("Unhandled exception while executing command '{}'.", command))
            logger.error(traceback.format_exc())

            start_response('500 Internal Server Error', [('Content-Type', 'text/json')])
            return [json.dumps({'error': "Internal server error."})]
        finally:
            db.close_old_connections()

    def command_create_observer(self, query, subscriber):
        """
        Starts observing a specific query.

        :param query: Query instance to observe
        :param subscriber: Subscriber channel name
        :return: Serialized current query results
        """

        # Create a queryset back from the pickled query.
        queryset = query.model.objects.all()
        queryset.query = query
        return pool.observe_queryset(queryset, subscriber)


class Command(base.BaseCommand):
    """
    Runs the query observers.
    """

    help = 'Runs the query observers'

    def handle(self, *args, **options):
        # Check if we are using the correct database engine configuration.
        if db.connection.settings_dict['ENGINE'] != 'django_db_geventpool.backends.postgresql_psycopg2':
            raise exceptions.ImproperlyConfigured("Query observers require the geventpool database engine.")

        # Register the event handler for receiving model updates from the Django ORM.
        event_handler = RedisObserverEventHandler()
        event_handler.start()

        # Prepare the RPC server.
        info = connection.get_queryobserver_settings()
        rpc_server = WSGIObserverCommandHandler((info['host'], info['port']))
        rpc_server.serve_forever()
