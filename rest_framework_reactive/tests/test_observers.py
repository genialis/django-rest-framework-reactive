import json
import pickle

from django import test
from django.contrib.auth import models as auth_models

from guardian import shortcuts
from rest_framework import test as api_test, request as api_request

from . import models, views
from rest_framework_reactive import models as observer_models
from rest_framework_reactive import request as observer_request
from rest_framework_reactive.observer import add_subscriber, QueryObserver

# Create test request factory.
factory = api_test.APIRequestFactory()


class QueryObserversTestCase(test.TestCase):
    def request(self, viewset_class, **kwargs):
        request = observer_request.Request(
            viewset_class,
            'list',
            api_request.Request(factory.get('/', kwargs))
        )

        # Simulate serialization.
        return pickle.loads(pickle.dumps(request))

    def test_paginated_viewset(self):
        observer = QueryObserver(self.request(views.PaginatedViewSet, offset=0, limit=10))
        items = observer.evaluate()

        add_subscriber('test-session', observer.id)

        self.assertEquals(len(items), 0)

        items = []
        for index in range(20):
            items.append(models.ExampleItem.objects.create(name='Example', enabled=True))

        # Evaluate the observer again (in reality this would be done automatically, triggered by signals
        # from Django ORM).
        added, changed, removed = observer.evaluate(return_emitted=True)

        self.assertEquals(len(added), 10)
        expected_serialized_item = {'id': items[0].pk, 'name': items[0].name, 'enabled': items[0].enabled}
        self.assertEquals(added[0]['data'], expected_serialized_item)
        self.assertEquals(len(changed), 0)
        self.assertEquals(len(removed), 0)

    def test_item_serialization(self):
        item = models.ExampleItem.objects.create(name='Example', enabled=True)
        shortcuts.assign_perm('rest_framework_reactive.view_exampleitem', auth_models.AnonymousUser(), item)

        observer = QueryObserver(self.request(views.ExampleItemViewSet))
        items = observer.evaluate()

        add_subscriber('test-session', observer.id)

        # Ensure items can be serialized into JSON.
        json.dumps(items)

    def test_observe_viewset(self):
        # Create a request and an observer for it.
        observer = QueryObserver(self.request(views.ExampleItemViewSet))
        items = observer.evaluate()

        add_subscriber('test-session', observer.id)

        self.assertEquals(observer.id, 'fdd1312a8082540528908c32f4a94cac55365ef7acadc8e5ae8d4795cd7b5fa6')
        self.assertEquals(len(items), 0)

        # Add an item into the database.
        item = models.ExampleItem()
        item.name = 'Example'
        item.enabled = True
        item.save()

        shortcuts.assign_perm('rest_framework_reactive.view_exampleitem', auth_models.AnonymousUser(), item)

        # Evaluate the observer again (in reality this would be done automatically, triggered by signals
        # from Django ORM).
        added, changed, removed = observer.evaluate(return_emitted=True)

        self.assertEquals(len(added), 1)
        expected_serialized_item = {'id': item.pk, 'name': item.name, 'enabled': item.enabled}
        self.assertEquals(added[0]['data'], expected_serialized_item)
        self.assertEquals(len(changed), 0)
        self.assertEquals(len(removed), 0)

        # Change the existing item.
        item.enabled = False
        expected_serialized_item['enabled'] = False
        item.save()

        added, changed, removed = observer.evaluate(return_emitted=True)
        self.assertEquals(len(added), 0)
        self.assertEquals(len(changed), 1)
        self.assertEquals(changed[0]['data'], expected_serialized_item)
        self.assertEquals(len(removed), 0)

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

        shortcuts.assign_perm('rest_framework_reactive.view_exampleitem', auth_models.AnonymousUser(), item2)
        shortcuts.assign_perm('rest_framework_reactive.view_exampleitem', auth_models.AnonymousUser(), item3)

        added, changed, removed = observer.evaluate(return_emitted=True)
        self.assertEquals(len(added), 2)
        self.assertEquals(added[0]['data'], {'id': item2.pk, 'name': item2.name, 'enabled': item2.enabled})
        self.assertEquals(added[1]['data'], {'id': item3.pk, 'name': item3.name, 'enabled': item3.enabled})
        self.assertEquals(len(changed), 0)
        self.assertEquals(len(removed), 1)
        self.assertEquals(removed[0]['data'], expected_serialized_item)

    def test_conditions(self):
        observer = QueryObserver(self.request(views.ExampleItemViewSet, enabled=True))
        items = observer.evaluate()

        add_subscriber('test-session', observer.id)

        self.assertEquals(observer.id, '0c2544b340aeb1919180ee6898a8e117de76b4a09dcedff7d6d172f3caa677c2')
        self.assertEquals(len(items), 0)

        item = models.ExampleItem()
        item.name = 'Example'
        item.enabled = False
        item.save()

        shortcuts.assign_perm('rest_framework_reactive.view_exampleitem', auth_models.AnonymousUser(), item)

        added, changed, removed = observer.evaluate(return_emitted=True)

        self.assertEquals(len(added), 0)
        self.assertEquals(len(changed), 0)
        self.assertEquals(len(removed), 0)

        item.enabled = True
        item.save()

        added, changed, removed = observer.evaluate(return_emitted=True)

        self.assertEquals(len(added), 1)
        self.assertEquals(added[0]['data'], {'id': item.pk, 'name': item.name, 'enabled': item.enabled})
        self.assertEquals(len(changed), 0)
        self.assertEquals(len(removed), 0)

    def test_joins(self):
        # Create some items so that we get a valid query (otherwise the query would be empty as django-guardian
        # would discover that the user doesn't have permissions to get any items).
        item = models.ExampleItem()
        item.name = 'Example'
        item.enabled = False
        item.save()

        subitem = models.ExampleSubItem(parent=item, enabled=True)
        subitem.save()

        shortcuts.assign_perm('rest_framework_reactive.view_exampleitem', auth_models.AnonymousUser(), item)
        shortcuts.assign_perm('rest_framework_reactive.view_examplesubitem', auth_models.AnonymousUser(), subitem)

        observer = QueryObserver(self.request(views.ExampleSubItemViewSet, parent__enabled=True))
        items = observer.evaluate()

        add_subscriber('test-session', observer.id)

        self.assertEquals(observer.id, '009955bdb64c21f679a7dfa2f747d6025ffef3185e5e01805662ebe8ca89c1d3')
        self.assertEquals(len(items), 0)

        observer_state = observer_models.Observer.objects.get(pk=observer.id)
        dependencies = observer_state.dependencies.all().values_list('table', flat=True)
        self.assertIn('rest_framework_reactive_tests_exampleitem', dependencies)
        self.assertIn('rest_framework_reactive_tests_examplesubitem', dependencies)

    def test_aggregations(self):
        item = models.ExampleItem()
        item.name = 'Example'
        item.enabled = False
        item.save()

        m2m_item = models.ExampleM2MItem()
        m2m_item.save()

        shortcuts.assign_perm('rest_framework_reactive.view_exampleitem', auth_models.AnonymousUser(), item)

        observer = QueryObserver(self.request(views.AggregationTestViewSet, items=[m2m_item.pk]))
        observer.evaluate()

        add_subscriber('test-session', observer.id)

        # There should be a dependency on the intermediate table.
        observer_state = observer_models.Observer.objects.get(pk=observer.id)
        dependencies = observer_state.dependencies.all().values_list('table', flat=True)
        self.assertIn('rest_framework_reactive_tests_examplem2mitem_items', dependencies)

    def test_order(self):
        observer = QueryObserver(self.request(views.ExampleItemViewSet, ordering='name'))
        items = observer.evaluate()

        add_subscriber('test-session', observer.id)

        self.assertEquals(len(items), 0)

        item = models.ExampleItem()
        item.name = 'D'
        item.enabled = False
        item.save()

        shortcuts.assign_perm('rest_framework_reactive.view_exampleitem', auth_models.AnonymousUser(), item)

        added, changed, removed = observer.evaluate(return_emitted=True)

        self.assertEquals(len(added), 1)
        self.assertEquals(added[0]['data'], {'id': item.pk, 'name': item.name, 'enabled': item.enabled})
        self.assertEquals(added[0]['order'], 0)
        self.assertEquals(len(changed), 0)
        self.assertEquals(len(removed), 0)

        item2 = models.ExampleItem()
        item2.name = 'A'
        item2.enabled = True
        item2.save()

        shortcuts.assign_perm('rest_framework_reactive.view_exampleitem', auth_models.AnonymousUser(), item2)

        added, changed, removed = observer.evaluate(return_emitted=True)

        self.assertEquals(len(added), 1)
        self.assertEquals(added[0]['data'], {'id': item2.pk, 'name': item2.name, 'enabled': item2.enabled})
        self.assertEquals(added[0]['order'], 0)
        # Check that the first item has changed, because its order has changed.
        self.assertEquals(len(changed), 1)
        self.assertEquals(changed[0]['data'], {'id': item.pk, 'name': item.name, 'enabled': item.enabled})
        self.assertEquals(changed[0]['order'], 1)
        self.assertEquals(len(removed), 0)

        item3 = models.ExampleItem()
        item3.name = 'C'
        item3.enabled = True
        item3.save()

        shortcuts.assign_perm('rest_framework_reactive.view_exampleitem', auth_models.AnonymousUser(), item3)

        added, changed, removed = observer.evaluate(return_emitted=True)
        self.assertEquals(len(added), 1)
        self.assertEquals(added[0]['data'], {'id': item3.pk, 'name': item3.name, 'enabled': item3.enabled})
        self.assertEquals(added[0]['order'], 1)
        self.assertEquals(len(changed), 1)
        self.assertEquals(changed[0]['data'], {'id': item.pk, 'name': item.name, 'enabled': item.enabled})
        self.assertEquals(changed[0]['order'], 2)
        self.assertEquals(len(removed), 0)

        # Check order change between two existing items.

        item.name = 'B'
        item.save()

        added, changed, removed = observer.evaluate(return_emitted=True)

        self.assertEquals(len(added), 0)
        self.assertEquals(len(changed), 2)
        self.assertEquals(changed[0]['data'], {'id': item3.pk, 'name': item3.name, 'enabled': item3.enabled})
        self.assertEquals(changed[0]['order'], 2)
        self.assertEquals(changed[1]['data'], {'id': item.pk, 'name': item.name, 'enabled': item.enabled})
        self.assertEquals(changed[1]['order'], 1)
        self.assertEquals(len(removed), 0)

    def test_no_dependencies(self):
        observer = QueryObserver(self.request(views.NoDependenciesViewSet))
        items = observer.evaluate()

        add_subscriber('test-session', observer.id)

        self.assertEquals(len(items), 1)
        self.assertEqual(items[0], {'id': 1, 'static': 'This has no dependencies'})

        # Observer should have been removed because there are no dependencies.

        self.assertFalse(observer_models.Observer.objects.exists())
