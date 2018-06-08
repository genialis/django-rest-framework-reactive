from concurrent.futures import CancelledError

import async_timeout
import pytest

from django.conf.urls import url

from channels.db import database_sync_to_async
from channels.testing import ApplicationCommunicator, WebsocketCommunicator
from channels.routing import URLRouter
from channels.layers import get_channel_layer
from rest_framework import test as api_test, request as api_request

from rest_framework_reactive import request as observer_request, models as observer_models
from rest_framework_reactive.consumers import ClientConsumer, PollObserversConsumer, WorkerConsumer
from rest_framework_reactive.protocol import *
from rest_framework_reactive.observer import QueryObserver, add_subscriber, remove_subscriber

from . import models, views

# Create test request factory.
factory = api_test.APIRequestFactory()


def create_request(viewset_class, **kwargs):
    request = observer_request.Request(
        viewset_class,
        'list',
        api_request.Request(factory.get('/', kwargs))
    )

    return request


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_worker_and_client():
    client_consumer = URLRouter([
        url(r'^ws/(?P<subscriber_id>.+)$', ClientConsumer),
    ])

    client = WebsocketCommunicator(client_consumer, '/ws/test-session')
    worker = ApplicationCommunicator(WorkerConsumer, {
        'type': 'channel',
        'channel': CHANNEL_WORKER_NOTIFY,
    })

    # Connect client.
    status, _ = await client.connect()
    assert status is True

    # Create an observer.
    @database_sync_to_async
    def create_observer():
        observer = QueryObserver(create_request(views.PaginatedViewSet, offset=0, limit=10))
        items = observer.evaluate()
        assert not items

        add_subscriber('test-session', observer.id)
        return observer.id

    observer_id = await create_observer()

    # Create a single model instance for the observer model.
    @database_sync_to_async
    def create_model():
        return models.ExampleItem.objects.create(enabled=True, name="hello world").pk

    primary_key = await create_model()

    # Check that ORM signal was generated.
    channel_layer = get_channel_layer()

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

    # Run observer again and it should remove itself because there are no more subscribers.
    await worker.send_input({'type': TYPE_EVALUATE_OBSERVER, 'observer': observer_id})
    assert await worker.receive_nothing() is True

    # Ensure that subscriber and observer have been removed.
    @database_sync_to_async
    def check_subscribers():
        assert observer_models.Subscriber.objects.all().count() == 0
        assert observer_models.Observer.objects.all().count() == 0

    await check_subscribers()


@pytest.mark.asyncio
async def test_poll_observer():
    poller = ApplicationCommunicator(PollObserversConsumer, {
        'type': 'channel',
        'channel': CHANNEL_POLL_OBSERVER,
    })

    await poller.send_input({
        'type': TYPE_POLL_OBSERVER,
        'observer': 'test',
        'interval': 5,
    })

    channel_layer = get_channel_layer()

    # Nothing should be received in the frist 4 seconds.
    async with async_timeout.timeout(4):
        try:
            await channel_layer.receive(CHANNEL_WORKER_NOTIFY)
            assert False
        except CancelledError:
            pass

    # Then after two more seconds we should get a notification.
    notify = await channel_layer.receive(CHANNEL_WORKER_NOTIFY)
    assert notify['type'] == TYPE_EVALUATE_OBSERVER
    assert notify['observer'] == 'test'


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_poll_observer_integration():
    client_consumer = URLRouter([
        url(r'^ws/(?P<subscriber_id>.+)$', ClientConsumer),
    ])

    client = WebsocketCommunicator(client_consumer, '/ws/test-session')
    worker = ApplicationCommunicator(WorkerConsumer, {
        'type': 'channel',
        'channel': CHANNEL_WORKER_NOTIFY,
    })
    poller = ApplicationCommunicator(PollObserversConsumer, {
        'type': 'channel',
        'channel': CHANNEL_POLL_OBSERVER,
    })

    # Connect client.
    status, _ = await client.connect()
    assert status is True

    # Create an observer.
    @database_sync_to_async
    def create_observer():
        observer = QueryObserver(create_request(views.PollingObservableViewSet))
        items = observer.evaluate()
        assert len(items) == 1

        add_subscriber('test-session', observer.id)
        return observer.id

    observer_id = await create_observer()

    # Ensure that a notification message was sent to the poller.
    channel_layer = get_channel_layer()

    notify = await channel_layer.receive(CHANNEL_POLL_OBSERVER)
    assert notify['type'] == TYPE_POLL_OBSERVER
    assert notify['interval'] == 5
    assert notify['observer'] == observer_id

    # Dispatch notification to poller as our poller uses a dummy queue.
    await poller.send_input(notify)

    # Nothing should be received in the frist 4 seconds.
    async with async_timeout.timeout(4):
        try:
            await channel_layer.receive(CHANNEL_WORKER_NOTIFY)
            assert False
        except CancelledError:
            pass

    # Then after two more seconds we should get a notification.
    notify = await channel_layer.receive(CHANNEL_WORKER_NOTIFY)

    # Dispatch notification to worker.
    await worker.send_input(notify)

    # Ensure another notification message was sent to the poller.
    notify = await channel_layer.receive(CHANNEL_POLL_OBSERVER)
    assert notify['type'] == TYPE_POLL_OBSERVER
    assert notify['interval'] == 5
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
