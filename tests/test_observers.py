import pickle

from django import test
from django.contrib.auth import models as auth_models
from guardian import shortcuts
from rest_framework import request as api_request
from rest_framework import test as api_test

from drfr_test_app import models, views
from rest_framework_reactive import models as observer_models
from rest_framework_reactive import request as observer_request
from rest_framework_reactive.observer import QueryObserver, remove_subscriber

# Create test request factory.
factory = api_test.APIRequestFactory()


def request(viewset_class, **kwargs):
    request = observer_request.Request(
        viewset_class, 'list', api_request.Request(factory.get('/', kwargs))
    )

    # Simulate serialization.
    return pickle.loads(pickle.dumps(request))


class QueryObserversTestCase(test.TestCase):
    def test_paginated_viewset(self):
        observer = QueryObserver(request(views.PaginatedViewSet, offset=0, limit=10))
        items = observer.subscribe('test-session')

        self.assertEqual(len(items), 0)

        items = []
        for index in range(20):
            items.append(
                models.ExampleItem.objects.create(name='Example', enabled=True)
            )

        # Evaluate the observer again (in reality this would be done automatically, triggered by signals
        # from Django ORM).
        added, changed, removed = observer._evaluate()

        self.assertEqual(len(added), 10)
        expected_serialized_item = {
            'id': items[0].pk,
            'name': items[0].name,
            'enabled': items[0].enabled,
        }
        self.assertEqual(added[0]['data'], expected_serialized_item)
        self.assertEqual(len(changed), 0)
        self.assertEqual(len(removed), 0)

    def test_item_serialization(self):
        item = models.ExampleItem.objects.create(name='Example', enabled=True)
        shortcuts.assign_perm(
            'rest_framework_reactive.view_exampleitem',
            auth_models.AnonymousUser(),
            item,
        )

        observer = QueryObserver(request(views.ExampleItemViewSet))
        items = observer.subscribe('test-session')

        # Ensure items can be serialized into JSON.
        # json.dumps(items)

    def test_observe_viewset(self):
        # Create a request and an observer for it.
        observer = QueryObserver(request(views.ExampleItemViewSet))
        items = observer.subscribe('test-session')

        self.assertEqual(
            observer.id,
            'fa87c86f1e032942b699e9902ac38ca232ce3566724b3891914c80083b676ed4',
        )
        self.assertEqual(len(items), 0)

        # Add an item into the database.
        item = models.ExampleItem()
        item.name = 'Example'
        item.enabled = True
        item.save()

        shortcuts.assign_perm(
            'rest_framework_reactive.view_exampleitem',
            auth_models.AnonymousUser(),
            item,
        )

        # Evaluate the observer again (in reality this would be done automatically, triggered by signals
        # from Django ORM).
        added, changed, removed = observer._evaluate()

        self.assertEqual(len(added), 1)
        expected_serialized_item = {
            'id': item.pk,
            'name': item.name,
            'enabled': item.enabled,
        }
        self.assertEqual(added[0]['data'], expected_serialized_item)
        self.assertEqual(len(changed), 0)
        self.assertEqual(len(removed), 0)

        # Change the existing item.
        item.enabled = False
        expected_serialized_item['enabled'] = False
        item.save()

        added, changed, removed = observer._evaluate()
        self.assertEqual(len(added), 0)
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]['data'], expected_serialized_item)
        self.assertEqual(len(removed), 0)

        # Remove the first item.
        item.delete()

        # Add another two items.
        item2 = models.ExampleItem()
        item2.name = 'Example 2'
        item2.enabled = True
        item2.save()

        item3 = models.ExampleItem()
        item3.name = 'Example 3'
        item3.enabled = True
        item3.save()

        shortcuts.assign_perm(
            'rest_framework_reactive.view_exampleitem',
            auth_models.AnonymousUser(),
            item2,
        )
        shortcuts.assign_perm(
            'rest_framework_reactive.view_exampleitem',
            auth_models.AnonymousUser(),
            item3,
        )

        added, changed, removed = observer._evaluate()
        self.assertEqual(len(added), 2)
        self.assertEqual(
            added[0]['data'],
            {'id': item2.pk, 'name': item2.name, 'enabled': item2.enabled},
        )
        self.assertEqual(
            added[1]['data'],
            {'id': item3.pk, 'name': item3.name, 'enabled': item3.enabled},
        )
        self.assertEqual(len(changed), 0)
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]['data'], expected_serialized_item)

    def test_conditions(self):
        observer = QueryObserver(request(views.ExampleItemViewSet, enabled=True))
        items = observer.subscribe('test-session')

        self.assertEqual(
            observer.id,
            '5333b85599fd24ed4e2f7eeaefb599cbbd39894b437e9b9d3b80d5d21639b4bb',
        )
        self.assertEqual(len(items), 0)

        item = models.ExampleItem()
        item.name = 'Example'
        item.enabled = False
        item.save()

        shortcuts.assign_perm(
            'rest_framework_reactive.view_exampleitem',
            auth_models.AnonymousUser(),
            item,
        )

        added, changed, removed = observer._evaluate()

        self.assertEqual(len(added), 0)
        self.assertEqual(len(changed), 0)
        self.assertEqual(len(removed), 0)

        item.enabled = True
        item.save()

        added, changed, removed = observer._evaluate()

        self.assertEqual(len(added), 1)
        self.assertEqual(
            added[0]['data'],
            {'id': item.pk, 'name': item.name, 'enabled': item.enabled},
        )
        self.assertEqual(len(changed), 0)
        self.assertEqual(len(removed), 0)

    def test_joins(self):
        # Create some items so that we get a valid query (otherwise the query would be empty as django-guardian
        # would discover that the user doesn't have permissions to get any items).
        item = models.ExampleItem()
        item.name = 'Example'
        item.enabled = False
        item.save()

        subitem = models.ExampleSubItem(parent=item, enabled=True)
        subitem.save()

        shortcuts.assign_perm(
            'rest_framework_reactive.view_exampleitem',
            auth_models.AnonymousUser(),
            item,
        )
        shortcuts.assign_perm(
            'rest_framework_reactive.view_examplesubitem',
            auth_models.AnonymousUser(),
            subitem,
        )

        observer = QueryObserver(
            request(views.ExampleSubItemViewSet, parent__enabled=True)
        )
        items = observer.subscribe('test-session')

        self.assertEqual(
            observer.id,
            '92b1698976bf1e04d155f9c60ac74c054ef872f547a59d771fc3c046998bbba8',
        )
        self.assertEqual(len(items), 0)

        observer_state = observer_models.Observer.objects.get(pk=observer.id)
        dependencies = observer_state.dependencies.all().values_list('table', flat=True)
        self.assertIn('drfr_test_app_exampleitem', dependencies)
        self.assertIn('drfr_test_app_examplesubitem', dependencies)

    def test_aggregations(self):
        item = models.ExampleItem()
        item.name = 'Example'
        item.enabled = False
        item.save()

        m2m_item = models.ExampleM2MItem()
        m2m_item.save()

        shortcuts.assign_perm(
            'rest_framework_reactive.view_exampleitem',
            auth_models.AnonymousUser(),
            item,
        )

        observer = QueryObserver(
            request(views.AggregationTestViewSet, items=[m2m_item.pk])
        )
        observer.subscribe('test-session')

        # There should be a dependency on the intermediate table.
        observer_state = observer_models.Observer.objects.get(pk=observer.id)
        dependencies = observer_state.dependencies.all().values_list('table', flat=True)
        self.assertIn('drfr_test_app_examplem2mitem_items', dependencies)

    def test_order(self):
        observer = QueryObserver(request(views.ExampleItemViewSet, ordering='name'))
        items = observer.subscribe('test-session')

        self.assertEqual(len(items), 0)

        item = models.ExampleItem()
        item.name = 'D'
        item.enabled = False
        item.save()

        shortcuts.assign_perm(
            'rest_framework_reactive.view_exampleitem',
            auth_models.AnonymousUser(),
            item,
        )

        added, changed, removed = observer._evaluate()

        self.assertEqual(len(added), 1)
        self.assertEqual(
            added[0]['data'],
            {'id': item.pk, 'name': item.name, 'enabled': item.enabled},
        )
        self.assertEqual(added[0]['order'], 0)
        self.assertEqual(len(changed), 0)
        self.assertEqual(len(removed), 0)

        item2 = models.ExampleItem()
        item2.name = 'A'
        item2.enabled = True
        item2.save()

        shortcuts.assign_perm(
            'rest_framework_reactive.view_exampleitem',
            auth_models.AnonymousUser(),
            item2,
        )

        added, changed, removed = observer._evaluate()

        self.assertEqual(len(added), 1)
        self.assertEqual(
            added[0]['data'],
            {'id': item2.pk, 'name': item2.name, 'enabled': item2.enabled},
        )
        self.assertEqual(added[0]['order'], 0)
        # Check that the first item has changed, because its order has changed.
        self.assertEqual(len(changed), 1)
        self.assertEqual(
            changed[0]['data'],
            {'id': item.pk, 'name': item.name, 'enabled': item.enabled},
        )
        self.assertEqual(changed[0]['order'], 1)
        self.assertEqual(len(removed), 0)

        item3 = models.ExampleItem()
        item3.name = 'C'
        item3.enabled = True
        item3.save()

        shortcuts.assign_perm(
            'rest_framework_reactive.view_exampleitem',
            auth_models.AnonymousUser(),
            item3,
        )

        added, changed, removed = observer._evaluate()
        self.assertEqual(len(added), 1)
        self.assertEqual(
            added[0]['data'],
            {'id': item3.pk, 'name': item3.name, 'enabled': item3.enabled},
        )
        self.assertEqual(added[0]['order'], 1)
        self.assertEqual(len(changed), 1)
        self.assertEqual(
            changed[0]['data'],
            {'id': item.pk, 'name': item.name, 'enabled': item.enabled},
        )
        self.assertEqual(changed[0]['order'], 2)
        self.assertEqual(len(removed), 0)

        # Check order change between two existing items.

        item.name = 'B'
        item.save()

        added, changed, removed = observer._evaluate()

        self.assertEqual(len(added), 0)
        self.assertEqual(len(changed), 2)
        self.assertEqual(
            changed[0]['data'],
            {'id': item3.pk, 'name': item3.name, 'enabled': item3.enabled},
        )
        self.assertEqual(changed[0]['order'], 2)
        self.assertEqual(
            changed[1]['data'],
            {'id': item.pk, 'name': item.name, 'enabled': item.enabled},
        )
        self.assertEqual(changed[1]['order'], 1)
        self.assertEqual(len(removed), 0)

    def test_no_dependencies(self):
        observer = QueryObserver(request(views.NoDependenciesViewSet))
        items = observer.subscribe('test-session')

        # Observer is created even when there are no dependencies.
        self.assertEqual(len(items), 1)
        self.assertTrue(observer_models.Observer.objects.exists())

    def test_remove_subscriber(self):
        # Simulate opening a WebSocket.
        # This should create an observer and subscribe a subscriber.
        query_observer = QueryObserver(request(views.ExampleItemViewSet))
        items = query_observer.subscribe('test-session')
        observer = observer_models.Observer.objects.get(id=query_observer.id)

        self.assertEqual(observer_models.Observer.objects.count(), 1)
        self.assertEqual(observer.subscribers.count(), 1)

        # Simulate closing a WebSocket.
        # This removes the subscriber but the observer remains.
        remove_subscriber('test-session', observer.id)
        self.assertEqual(observer_models.Observer.objects.count(), 1)
        self.assertEqual(observer.subscribers.count(), 0)

        # Simulate opening a WebSocket again.
        # This should add a subscriber to existing observer.
        query_observer = QueryObserver(request(views.ExampleItemViewSet))
        items = query_observer.subscribe('test-session')
        self.assertEqual(observer_models.Subscriber.objects.count(), 1)
        self.assertEqual(observer.subscribers.count(), 1)

    def test_tables_of_empty_results(self):
        models.ExampleItem.objects.all().delete()
        query_observer = QueryObserver(
            request(views.ExampleItemViewSet, offset=10, limit=0)
        )
        items = query_observer.subscribe('test-session')
        print(items)


class QueryObserversTransactionTestCase(test.TransactionTestCase):
    def test_subscribe(self):
        observer = QueryObserver(request(views.ExampleItemViewSet))
        observer_qs = observer_models.Observer.objects

        # Subscribe new subscriber to new observer.
        observer.subscribe('test-session')
        self.assertEqual(observer_qs.count(), 1)
        self.assertEqual(observer_qs.first().subscribers.count(), 1)

        # Subscribe new subscriber to existing observer.
        observer.subscribe('test-session2')
        self.assertEqual(observer_qs.count(), 1)
        self.assertEqual(observer_qs.first().subscribers.count(), 2)

        # Subscribe existing subscriber to new observer.
        observer_qs.all().delete()
        self.assertEqual(observer_qs.count(), 0)
        self.assertEqual(observer_models.Subscriber.objects.count(), 2)
        observer.subscribe('test-session')
        self.assertEqual(observer_qs.count(), 1)
        self.assertEqual(observer_qs.first().subscribers.count(), 1)

        # Subscribe existing subscriber to existing observer.
        # Note that when a subscriber is already subscribed to the observer,
        # we should ignore duplicate key violation.
        observer.subscribe('test-session')
        self.assertEqual(observer_qs.count(), 1)
        self.assertEqual(observer_qs.first().subscribers.count(), 1)

        # Test that custom SQL query in subscribe serializes the request
        # string the same as Django create.
        observer_obj = observer_qs.first()
        observer_with_same_request = observer_models.Observer.objects.create(
            id='request-comparisson', request=pickle.dumps(observer._request)
        )

        self.assertEqual(
            bytes(observer_obj.request), bytes(observer_with_same_request.request)
        )

    def test_decorate_class(self):
        """Decorating class should pass dependencies to the list method"""
        observer = QueryObserver(request(views.AggregationTestViewSet))
        observer.subscribe('test-session')
        self.assertEqual(
            observer_models.Dependency.objects.filter(observer=observer.id).count(), 2
        )
