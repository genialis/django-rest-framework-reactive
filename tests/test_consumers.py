from concurrent.futures import CancelledError

import async_timeout
import pytest

from django.conf.urls import url

from channels.db import database_sync_to_async
from channels.testing import ApplicationCommunicator, WebsocketCommunicator
from channels.routing import URLRouter
from channels.layers import get_channel_layer
from rest_framework import test as api_test, request as api_request

from rest_framework_reactive import (
    request as observer_request,
    models as observer_models,
)
from rest_framework_reactive.consumers import (
    ClientConsumer,
    PollObserversConsumer,
    WorkerConsumer,
)
from rest_framework_reactive.protocol import *
from rest_framework_reactive.observer import QueryObserver, remove_subscriber

from drfr_test_app import models, views

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
    client_consumer = URLRouter([url(r'^ws/(?P<subscriber_id>.+)$', ClientConsumer)])

    client = WebsocketCommunicator(client_consumer, '/ws/test-session')
    worker = ApplicationCommunicator(
        WorkerConsumer, {'type': 'channel', 'channel': CHANNEL_WORKER_NOTIFY}
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
        notify = await channel_layer.receive(CHANNEL_WORKER_NOTIFY)
        assert notify['type'] == TYPE_ORM_NOTIFY_TABLE
        assert notify['kind'] == ORM_NOTIFY_KIND_CREATE
        assert notify['primary_key'] == str(primary_key)

        # Propagate notification to worker.
        await worker.send_input(notify)

        # Check that observer evaluation was requested.
        notify = await channel_layer.receive(CHANNEL_WORKER_NOTIFY)
        assert notify['type'] == TYPE_EVALUATE_OBSERVER
        assert notify['observer'] == observer_id

        # Propagate notification to worker.
        await worker.send_input(notify)
        response = await client.receive_json_from()
        assert response['msg'] == 'added'
        assert response['primary_key'] == 'id'
        assert response['order'] == 0
        assert response['item'] == {'id': 1, 'enabled': True, 'name': 'hello world'}

    # No other messages should be sent.
    assert await client.receive_nothing() is True
    await client.disconnect()

    # Ensure that subscriber has been removed.
    await assert_subscribers(0)

    async with async_timeout.timeout(1):
        # Run observer again and it should skip evaluation because there are no more subscribers.
        await worker.send_input(
            {'type': TYPE_EVALUATE_OBSERVER, 'observer': observer_id}
        )

    assert await worker.receive_nothing() is True


@pytest.mark.asyncio
async def test_poll_observer():
    poller = ApplicationCommunicator(
        PollObserversConsumer, {'type': 'channel', 'channel': CHANNEL_POLL_OBSERVER}
    )

    await poller.send_input(
        {'type': TYPE_POLL_OBSERVER, 'observer': 'test', 'interval': 2}
    )

    channel_layer = get_channel_layer()

    # Nothing should be received in the first second.
    async with async_timeout.timeout(1):
        try:
            await channel_layer.receive(CHANNEL_WORKER_NOTIFY)
            assert False
        except CancelledError:
            pass

    async with async_timeout.timeout(2):
        # Then after another second we should get a notification.
        notify = await channel_layer.receive(CHANNEL_WORKER_NOTIFY)
        assert notify['type'] == TYPE_EVALUATE_OBSERVER
        assert notify['observer'] == 'test'


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_poll_observer_integration():
    client_consumer = URLRouter([url(r'^ws/(?P<subscriber_id>.+)$', ClientConsumer)])

    client = WebsocketCommunicator(client_consumer, '/ws/test-session')
    worker = ApplicationCommunicator(
        WorkerConsumer, {'type': 'channel', 'channel': CHANNEL_WORKER_NOTIFY}
    )
    poller = ApplicationCommunicator(
        PollObserversConsumer, {'type': 'channel', 'channel': CHANNEL_POLL_OBSERVER}
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
        notify = await channel_layer.receive(CHANNEL_POLL_OBSERVER)
        assert notify['type'] == TYPE_POLL_OBSERVER
        assert notify['interval'] == 2
        assert notify['observer'] == observer_id

        # Dispatch notification to poller as our poller uses a dummy queue.
        await poller.send_input(notify)

    # Nothing should be received in the first second.
    async with async_timeout.timeout(1):
        try:
            await channel_layer.receive(CHANNEL_WORKER_NOTIFY)
            assert False
        except CancelledError:
            pass

    async with async_timeout.timeout(2):
        # Then after another second we should get a notification.
        notify = await channel_layer.receive(CHANNEL_WORKER_NOTIFY)

        # Dispatch notification to worker.
        await worker.send_input(notify)

        # Ensure another notification message was sent to the poller.
        notify = await channel_layer.receive(CHANNEL_POLL_OBSERVER)
        assert notify['type'] == TYPE_POLL_OBSERVER
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
