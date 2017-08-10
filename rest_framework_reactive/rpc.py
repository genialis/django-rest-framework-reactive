from __future__ import absolute_import, division, print_function, unicode_literals

import redis
import redis.connection
import pickle
import logging
import traceback
import json

from django import db
from django.utils.encoding import force_str

from .__about__ import __version__
from . import connection
from .pool import pool

# Logger.
logger = logging.getLogger(__name__)


class RedisObserverEventHandler(object):
    """
    Query observer handler that receives events via Redis.
    """

    def __call__(self):
        """
        Entry point.
        """

        # Establish a connection with Redis server.
        self._redis = redis.StrictRedis(**connection.get_redis_settings())
        self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        self._pubsub.subscribe(connection.QUERYOBSERVER_REDIS_CHANNEL)

        while self._pubsub.subscribed:
            event = self._pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if not event:
                continue

            # Events are assumed to be pickled data.
            try:
                event = pickle.loads(event['data'])
            except ValueError:
                logger.error("Ignoring received malformed event '{}'.", event['data'][:20])
                continue

            # Handle event.
            try:
                event_name = event.pop('event')
                handler = getattr(self, 'event_%s' % event_name)
            except AttributeError:
                logger.error("Ignoring unimplemented event '{}'.", event_name)
                continue
            except KeyError:
                logger.error("Ignoring received malformed event '{}'.", event)
                continue

            try:
                handler(**event)
            except:
                logger.error("Unhandled exception while executing event '{}'.", event_name)
                logger.error(traceback.format_exc())
            finally:
                db.close_old_connections()

        self._pubsub.close()

    def shutdown(self):
        self._pubsub.unsubscribe()
        self._pubsub.punsubscribe()

    def event_table_insert(self, table):
        pool.notify_update(table)

    def event_table_update(self, table):
        pool.notify_update(table)

    def event_table_remove(self, table):
        pool.notify_update(table)

    def event_subscriber_gone(self, subscriber):
        pool.remove_subscriber(subscriber)


class WSGIObserverCommandHandler(object):
    """
    A WSGI-based RPC server for the query observer API.
    """

    def __call__(self, environ, start_response):
        """
        Handles an incoming RPC request.
        """

        def respond(status, content):
            """Response generation helper."""
            headers = [(str('Content-Type'), str('text/json'))]
            start_response(force_str(status), headers)
            return [json.dumps(content)]

        content_length = int(environ['CONTENT_LENGTH'])

        try:
            request = pickle.loads(environ['wsgi.input'].read(content_length))
            if not isinstance(request, dict):
                raise ValueError

            command = request.pop('command')
            handler = getattr(self, 'command_%s' % command)
        except (KeyError, ValueError, AttributeError, EOFError):
            return respond('400 Bad Request', {'error': "Bad request."})

        try:
            response = handler(**request)
            return respond('200 OK', response)
        except TypeError:
            logger.exception("Observer request failed with bad request error.")
            return respond('400 Bad Request', {'error': "Bad request."})
        except:
            logger.error("Unhandled exception while executing command '{}'.", command)
            logger.error(traceback.format_exc())

            return respond('500 Internal Server Error', {'error': "Internal server error."})
        finally:
            db.close_old_connections()

    def command_status(self):
        """
        Return some status information about the observer pool.
        """

        return {
            'version': __version__,
            'backend': '{}.{}'.format(
                pool.backend.__class__.__module__,
                pool.backend.__class__.__name__
            ),
            'statistics': pool.statistics,
        }

    def command_stop_all(self):
        """
        Stops all observers.
        """

        pool.stop_all()

    def command_create_observer(self, request, subscriber):
        """
        Starts observing a specific viewset.

        :param request: The `queryobservers.request.Request` to observe
        :param subscriber: Subscriber channel name
        :return: Serialized current query results
        """

        observer = pool.observe_viewset(request, subscriber)
        return {
            'observer': observer.id,
            'items': observer.evaluate(),
        }

    def command_unsubscribe_observer(self, observer, subscriber):
        """
        Unsubscribes a specific subscriber from an observer.

        :param observer: Query observer identifier
        :param subscriber: Subscriber channel name
        """

        pool.unobserve_viewset(observer, subscriber)
