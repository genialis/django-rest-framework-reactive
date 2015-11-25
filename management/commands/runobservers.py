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
from django.conf import settings


# Redis channel for receiving control messages.
QUERYOBSERVER_REDIS_CHANNEL = 'genesis:queryobserver:control'

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
        defaults = {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
        }
        defaults.update(getattr(settings, 'REDIS_CONNECTION', {}))
        self._redis = redis.StrictRedis(**defaults)
        self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        self._pubsub.subscribe(QUERYOBSERVER_REDIS_CHANNEL)

        for event in self._pubsub.listen():
            # Events are assumed to be pickled data.
            try:
                event = pickle.loads(event['data'])
            except ValueError:
                logger.error("Ignoring received malformed event '%s'." % event['data'][:20])
                continue

            # Handle event.
            try:
                event_name = event.pop('name')
                handler = getattr(self, 'event_%s' % event_name)
            except AttributeError:
                logger.error("Ignoring unimplemented event '%s'." % event_name)
                continue
            except KeyError:
                logger.error("Ignoring received malformed event '%s'." % event)
                continue

            try:
                handler(**event)
            except:
                logger.error("Unhandled exception while executing event '%s'." % event_name)
                logger.error(format_exc())

    def event_model_insert(self):
        pass

    def event_model_update(self):
        pass

    def event_model_remove(self):
        pass


class WSGIObserverCommandHandler(pywsgi.WSGIServer):
    def __init__(self, *args, **kwargs):
        kwargs['application'] = self.handle_rpc_request
        super(WSGIObserverCommandHandler, self).__init__(*args, **kwargs)

    def handle_rpc_request(self, environ, start_response):
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
            start_response('500 Internal Server Error', [('Content-Type', 'text/json')])
            return [json.dumps({'error': "Internal server error."})]

    def command_create_observer(self, queryset):
        # TODO
        return {}


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
        defaults = {
            'host': 'localhost',
            'port': 9432,
        }
        defaults.update(getattr(settings, 'QUERYOBSERVER', {}))
        rpc_server = WSGIObserverCommandHandler((defaults['host'], defaults['port']))
        rpc_server.serve_forever()
