import asyncio

import async_timeout
import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import ApplicationCommunicator, WebsocketCommunicator
from django.urls import path
from django.core.cache import cache
from django.test import override_settings
from rest_framework import request as api_request
from rest_framework import test as api_test

from drfr_test_app import models, views
from rest_framework_reactive import models as observer_models
from rest_framework_reactive import request as observer_request
from rest_framework_reactive.consumers import (
    ClientConsumer,
    MainConsumer,
    WorkerConsumer,
    throttle_cache_key,
)
from rest_framework_reactive.observer import QueryObserver
from rest_framework_reactive.protocol import *

# Create test request factory.
factory = api_test.APIRequestFactory()


def create_request(viewset_class, **kwargs):
    request = observer_request.Request(
        viewset_class, 'list', api_request.Request(factory.get('/', kwargs))
    )

    return request


@database_sync_to_async
def assert_subscribers(num, observer_id=None):
    """Test the number of subscribers."""
    if observer_id:
        observer = observer_models.Observer.objects.get(id=observer_id)
        assert observer.subscribers.all().count() == num
    else:
        assert observer_models.Subscriber.objects.all().count() == num


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_worker_and_client():
    client_consumer = URLRouter(
        [path('ws/<slug:subscriber_id>', ClientConsumer().as_asgi())]
    )

    client = WebsocketCommunicator(client_consumer, '/ws/test-session')
    main = ApplicationCommunicator(
        MainConsumer(), {'type': 'channel', 'channel': CHANNEL_MAIN}
    )
    worker = ApplicationCommunicator(
        WorkerConsumer(), {'type': 'channel', 'channel': CHANNEL_WORKER}
    )

    # Connect client.
    status, _ = await client.connect()
    assert status is True

    # Create an observer.
    @database_sync_to_async
    def create_observer():
        observer = QueryObserver(
            create_request(views.PaginatedViewSet, offset=0, limit=10)
        )
        items = observer.subscribe('test-session')
        assert not items
        return observer.id

    observer_id = await create_observer()
    await assert_subscribers(1)
    await assert_subscribers(1, observer_id)

    # Create a single model instance for the observer model.
    @database_sync_to_async
    def create_model():
        return models.ExampleItem.objects.create(enabled=True, name="hello world").pk

    primary_key = await create_model()
    channel_layer = get_channel_layer()

    async with async_timeout.timeout(1):
        # Check that ORM signal was generated.
        notify = await channel_layer.receive(CHANNEL_MAIN)
        assert notify['type'] == TYPE_ORM_NOTIFY
        assert notify['kind'] == ORM_NOTIFY_KIND_CREATE
        assert notify['primary_key'] == str(primary_key)

        # Propagate notification to worker.
        await main.send_input(notify)

        # Check that observer evaluation was requested.
        notify = await channel_layer.receive(CHANNEL_WORKER)
        assert notify['type'] == TYPE_EVALUATE
        assert notify['observer'] == observer_id

        # Propagate notification to worker.
        await worker.send_input(notify)
        response = await client.receive_json_from()
        assert response['msg'] == 'added'
        assert response['primary_key'] == 'id'
        assert response['order'] == 0
        assert response['item'] == {
            'id': primary_key,
            'enabled': True,
            'name': 'hello world',
        }

    # No other messages should be sent.
    assert await client.receive_nothing() is True
    await client.disconnect()

    # Ensure that subscriber has been removed.
    await assert_subscribers(0)

    async with async_timeout.timeout(1):
        # Run observer again and it should skip evaluation because there are no more subscribers.
        await worker.send_input({'type': TYPE_EVALUATE, 'observer': observer_id})

    assert await worker.receive_nothing() is True


@pytest.mark.asyncio
async def test_poll_observer():
    main = ApplicationCommunicator(
        MainConsumer(), {'type': 'channel', 'channel': CHANNEL_MAIN}
    )
    await main.send_input({'type': TYPE_POLL, 'observer': 'test', 'interval': 2})
    channel_layer = get_channel_layer()

    # Nothing should be received in the first second.
    with pytest.raises(asyncio.TimeoutError):
        async with async_timeout.timeout(1):
            await channel_layer.receive(CHANNEL_WORKER)
            assert False

    # Then after another second we should get a notification.
    async with async_timeout.timeout(2):
        notify = await channel_layer.receive(CHANNEL_WORKER)
        assert notify['type'] == TYPE_EVALUATE
        assert notify['observer'] == 'test'


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_poll_observer_integration():
    client_consumer = URLRouter(
        [path('ws/<slug:subscriber_id>', ClientConsumer().as_asgi())]
    )

    client = WebsocketCommunicator(client_consumer, '/ws/test-session')
    main = ApplicationCommunicator(
        MainConsumer(), {'type': 'channel', 'channel': CHANNEL_MAIN}
    )
    worker = ApplicationCommunicator(
        WorkerConsumer(), {'type': 'channel', 'channel': CHANNEL_WORKER}
    )

    # Connect client.
    status, _ = await client.connect()
    assert status is True

    # Create an observer.
    @database_sync_to_async
    def create_observer():
        observer = QueryObserver(create_request(views.PollingObservableViewSet))
        items = observer.subscribe('test-session')
        assert len(items) == 1
        return observer.id

    observer_id = await create_observer()
    await assert_subscribers(1)
    await assert_subscribers(1, observer_id)

    channel_layer = get_channel_layer()

    async with async_timeout.timeout(1):
        # Ensure that a notification message was sent to the poller.
        notify = await channel_layer.receive(CHANNEL_MAIN)
        assert notify['type'] == TYPE_POLL
        assert notify['interval'] == 2
        assert notify['observer'] == observer_id

        # Dispatch notification to poller as our poller uses a dummy queue.
        await main.send_input(notify)

    # Nothing should be received in the first second.
    with pytest.raises(asyncio.TimeoutError):
        async with async_timeout.timeout(1):
            await channel_layer.receive(CHANNEL_WORKER)
            assert False

    async with async_timeout.timeout(2):
        # Then after another second we should get a notification.
        notify = await channel_layer.receive(CHANNEL_WORKER)

        # Dispatch notification to worker.
        await worker.send_input(notify)

        # Ensure another notification message was sent to the poller.
        notify = await channel_layer.receive(CHANNEL_MAIN)
        assert notify['type'] == TYPE_POLL
        assert notify['interval'] == 2
        assert notify['observer'] == observer_id

        # Ensure client got notified of changes.
        response = await client.receive_json_from()
        assert response['msg'] == 'changed'
        assert response['primary_key'] == 'id'
        assert response['order'] == 0
        assert response['item']['static'].startswith('This is a polling observable:')

    # No other messages should be sent.
    assert await client.receive_nothing() is True
    await client.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_throttle_observer():
    with override_settings(DJANGO_REST_FRAMEWORK_REACTIVE={'throttle_rate': 2}):
        channel_layer = get_channel_layer()
        main = ApplicationCommunicator(
            MainConsumer(), {'type': 'channel', 'channel': CHANNEL_MAIN}
        )
        worker = ApplicationCommunicator(
            WorkerConsumer(), {'type': 'channel', 'channel': CHANNEL_WORKER}
        )

        @database_sync_to_async
        def create_observer():
            observer = QueryObserver(
                create_request(views.ExampleItemViewSet, offset=0, limit=10)
            )
            items = observer.subscribe('test-session')
            return observer.id

        @database_sync_to_async
        def get_last_evaluation(observer_id):
            return observer_models.Observer.objects.get(id=observer_id).last_evaluation

        def throttle_count(observer_id, value=None):
            cache_key = throttle_cache_key(observer_id)
            if value is None:
                return cache.get(cache_key)
            else:
                return cache.set(cache_key, value)

        observer_id = await create_observer()

        # Test that observer is evaluated
        async with async_timeout.timeout(1):
            await worker.send_input({'type': TYPE_EVALUATE, 'observer': observer_id})

            # Nothing should be in the main worker
            assert await main.receive_nothing()

            # Get last evaluation time for later comparisson
            last_evaluation = await get_last_evaluation(observer_id)

            # Throttle count should be 1 (one process)
            assert throttle_count(observer_id) == 1

            # Ensure last_evaluated time change before the next test
            await asyncio.sleep(0.001)

            # Observer evaluation is delayed while another is evaluated
            await worker.send_input({'type': TYPE_EVALUATE, 'observer': observer_id})

            # Delayed observer should be scheduled
            notify = await channel_layer.receive(CHANNEL_MAIN)
            assert notify['type'] == TYPE_POLL
            assert notify['observer'] == observer_id

            # Throttle count should be 2 (two processes)
            assert throttle_count(observer_id) == 2

            # Observer should not be evaluated
            assert last_evaluation == await get_last_evaluation(observer_id)

            # Observer evaluation is discarded when delayed observer scheduled
            await worker.send_input({'type': TYPE_EVALUATE, 'observer': observer_id})

            # Nothing should be in the main worker
            assert await main.receive_nothing()

            # Observer should not be evaluated
            assert last_evaluation == await get_last_evaluation(observer_id)

            # Throttle count should be 3 (three processes)
            assert throttle_count(observer_id) == 3
