from django import test
from django.apps import apps
from django.conf import settings
from django.core import management
from django.test import utils
from django.db.models import query as django_query

from . import models, serializers, views
from ..pool import pool

# Override settings used during tests so we can include some test-only models.
TEST_SETTINGS = {
    'DEBUG': True,
    'INSTALLED_APPS': settings.INSTALLED_APPS + ('genesis.queryobserver.tests.apps.QueryObserverTestsConfig',),
}


@utils.override_settings(**TEST_SETTINGS)
class QueryObserversTestCase(test.TestCase):
    def setUp(self):
        apps.clear_cache()
        management.call_command('migrate', verbosity=0, interactive=False, load_initial_data=False)

        super(QueryObserversTestCase, self).setUp()

    @classmethod
    def setUpClass(cls):
        super(QueryObserversTestCase, cls).setUpClass()

        # Register observable models.
        pool.register_model(models.ExampleItem, serializers.ExampleItemSerializer, views.ExampleItemViewSet)
        pool.register_model(models.ExampleSubItem, serializers.ExampleSubItemSerializer, views.ExampleSubItemViewSet)

    def tearDown(self):
        super(QueryObserversTestCase, self).tearDown()

        pool.stop_all()

    def test_observe_queryset(self):
        # Create a queryset and an observer for it.
        queryset = models.ExampleItem.objects.all()
        observer = pool.observe_queryset(queryset, 'test-subscriber')
        items = observer.evaluate()

        self.assertEquals(observer.id, 'fcad4a3e696d9328956d4052638958a067c6406e314b6ba9f20ee5c69e9564b4')
        self.assertEquals(items, [])
        self.assertEquals(list(queryset), [])

        # Add an item into the database.
        item = models.ExampleItem()
        item.name = 'Example'
        item.enabled = True
        item.save()

        # Evaluate the observer again (in reality this would be done automatically, triggered by signals
        # from Django ORM).
        added, changed, removed = observer.evaluate(return_emitted=True)

        self.assertEquals(len(added), 1)
        expected_serialized_item = {'id': item.pk, 'name': item.name, 'enabled': item.enabled}
        self.assertEquals(added[0], expected_serialized_item)
        self.assertEquals(len(changed), 0)
        self.assertEquals(len(removed), 0)

        # Change the existing item.
        item.enabled = False
        expected_serialized_item['enabled'] = False
        item.save()

        added, changed, removed = observer.evaluate(return_emitted=True)
        self.assertEquals(len(added), 0)
        self.assertEquals(len(changed), 1)
        self.assertEquals(changed[0], expected_serialized_item)
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

        added, changed, removed = observer.evaluate(return_emitted=True)
        self.assertEquals(len(added), 2)
        self.assertEquals(added[0], {'id': item2.pk, 'name': item2.name, 'enabled': item2.enabled})
        self.assertEquals(added[1], {'id': item3.pk, 'name': item3.name, 'enabled': item3.enabled})
        self.assertEquals(len(changed), 0)
        self.assertEquals(len(removed), 1)
        self.assertEquals(removed[0], expected_serialized_item)

    def test_empty_queryset(self):
        # Create a queryset that always returns no results.
        queryset = models.ExampleItem.objects.filter(pk__in=[])
        observer = pool.observe_queryset(queryset, 'test-subscriber')
        items = observer.evaluate()

        self.assertEquals(observer.id, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
        self.assertEquals(len(items), 0)

        # Create another empty queryset which should have the exact same identifier.
        queryset = models.ExampleItem.objects.filter(name__in=[])
        observer = pool.observe_queryset(queryset, 'test-subscriber')
        items = observer.evaluate()

        self.assertEquals(observer.id, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
        self.assertEquals(len(items), 0)

    def test_conditions(self):
        queryset = models.ExampleItem.objects.filter(enabled=True)
        observer = pool.observe_queryset(queryset, 'test-subscriber')
        items = observer.evaluate()

        self.assertEquals(observer.id, '39f8802cd119c90e4051dd86d6ccb2455f044bd92bf36bbad7a276e9f7b73524')
        self.assertEquals(len(items), 0)

        item = models.ExampleItem()
        item.name = 'Example'
        item.enabled = False
        item.save()

        added, changed, removed = observer.evaluate(return_emitted=True)

        self.assertEquals(len(added), 0)
        self.assertEquals(len(changed), 0)
        self.assertEquals(len(removed), 0)

        item.enabled = True
        item.save()

        added, changed, removed = observer.evaluate(return_emitted=True)

        self.assertEquals(len(added), 1)
        self.assertEquals(added[0], {'id': item.pk, 'name': item.name, 'enabled': item.enabled})
        self.assertEquals(len(changed), 0)
        self.assertEquals(len(removed), 0)

    def test_joins(self):
        queryset = models.ExampleSubItem.objects.filter(parent__enabled=True)
        observer = pool.observe_queryset(queryset, 'test-subscriber')
        items = observer.evaluate()

        self.assertEquals(observer.id, 'b9c76c88531870f2b4de44f508f4db96e52c2e4f8fbbc9791105e7cf13ba0380')
        self.assertEquals(len(items), 0)
        self.assertIn(observer, pool._tables['queryobserver_exampleitem'])
        self.assertIn(observer, pool._tables['queryobserver_examplesubitem'])

    def test_order(self):
        queryset = models.ExampleItem.objects.all().order_by('name')
        observer = pool.observe_queryset(queryset, 'test-subscriber')
        items = observer.evaluate()

        self.assertEquals(len(items), 0)

        item = models.ExampleItem()
        item.name = 'D'
        item.enabled = False
        item.save()

        added, changed, removed = observer.evaluate(return_emitted=True)

        self.assertEquals(len(added), 1)
        self.assertEquals(added[0], {'id': item.pk, 'name': item.name, 'enabled': item.enabled})
        self.assertEquals(added[0]._order, 0)
        self.assertEquals(len(changed), 0)
        self.assertEquals(len(removed), 0)

        item2 = models.ExampleItem()
        item2.name = 'A'
        item2.enabled = True
        item2.save()

        added, changed, removed = observer.evaluate(return_emitted=True)

        self.assertEquals(len(added), 1)
        self.assertEquals(added[0], {'id': item2.pk, 'name': item2.name, 'enabled': item2.enabled})
        self.assertEquals(added[0]._order, 0)
        # Check that the first item has changed, because its order has changed.
        self.assertEquals(len(changed), 1)
        self.assertEquals(changed[0], {'id': item.pk, 'name': item.name, 'enabled': item.enabled})
        self.assertEquals(changed[0]._order, 1)
        self.assertEquals(len(removed), 0)

        item3 = models.ExampleItem()
        item3.name = 'C'
        item3.enabled = True
        item3.save()

        added, changed, removed = observer.evaluate(return_emitted=True)
        self.assertEquals(len(added), 1)
        self.assertEquals(added[0], {'id': item3.pk, 'name': item3.name, 'enabled': item3.enabled})
        self.assertEquals(added[0]._order, 1)
        self.assertEquals(len(changed), 1)
        self.assertEquals(changed[0], {'id': item.pk, 'name': item.name, 'enabled': item.enabled})
        self.assertEquals(changed[0]._order, 2)
        self.assertEquals(len(removed), 0)
