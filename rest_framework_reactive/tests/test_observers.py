from django import test
from django.apps import apps
from django.conf import settings
from django.core import management
from django.test import utils
from django.db.models import query as django_query
from django.contrib.auth import models as auth_models

from guardian import shortcuts
from rest_framework import test as api_test, request as api_request

from . import models, serializers, views
from .. import request as observer_request
from ..pool import pool

# Override settings used during tests so we can include some test-only models.
TEST_SETTINGS = {
    'DEBUG': True,
    'INSTALLED_APPS': settings.INSTALLED_APPS + ('rest_framework_reactive.tests.apps.QueryObserverTestsConfig',),
}

# Create test request factory.
factory = api_test.APIRequestFactory()


@utils.override_settings(**TEST_SETTINGS)
class QueryObserversTestCase(test.TestCase):
    def setUp(self):
        apps.clear_cache()
        management.call_command('migrate', verbosity=0, interactive=False, load_initial_data=False)

        super(QueryObserversTestCase, self).setUp()

    @classmethod
    def setUpClass(cls):
        super(QueryObserversTestCase, cls).setUpClass()

        # Register observable viewsets.
        pool.register_viewset(views.ExampleItemViewSet)
        pool.register_viewset(views.ExampleSubItemViewSet)

    def tearDown(self):
        super(QueryObserversTestCase, self).tearDown()

        pool.stop_all()

    def request(self, viewset_class, **kwargs):
        return observer_request.Request(viewset_class, api_request.Request(factory.get('/', kwargs)))

    def test_observe_viewset(self):
        # Create a request and an observer for it.
        observer = pool.observe_viewset(self.request(views.ExampleItemViewSet), 'test-subscriber')
        items = observer.evaluate()

        self.assertEquals(observer.id, '8e40282bb959b6b6eefa424f594b5e32bc50aebedf1f6a66dc7f599e75c6a26f')
        self.assertEquals(items, [])

        # Add an item into the database.
        item = models.ExampleItem()
        item.name = 'Example'
        item.enabled = True
        item.save()

        shortcuts.assign_perm('queryobserver.view_exampleitem', auth_models.AnonymousUser(), item)

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

        shortcuts.assign_perm('queryobserver.view_exampleitem', auth_models.AnonymousUser(), item2)
        shortcuts.assign_perm('queryobserver.view_exampleitem', auth_models.AnonymousUser(), item3)

        added, changed, removed = observer.evaluate(return_emitted=True)
        self.assertEquals(len(added), 2)
        self.assertEquals(added[0], {'id': item2.pk, 'name': item2.name, 'enabled': item2.enabled})
        self.assertEquals(added[1], {'id': item3.pk, 'name': item3.name, 'enabled': item3.enabled})
        self.assertEquals(len(changed), 0)
        self.assertEquals(len(removed), 1)
        self.assertEquals(removed[0], expected_serialized_item)

    def test_conditions(self):
        observer = pool.observe_viewset(self.request(views.ExampleItemViewSet, enabled=True), 'test-subscriber')
        items = observer.evaluate()

        self.assertEquals(observer.id, '8903bb97f59dd10cfe6896f632ebcf9ea8240c9f2df39f966b4157b5811c5dad')
        self.assertEquals(len(items), 0)

        item = models.ExampleItem()
        item.name = 'Example'
        item.enabled = False
        item.save()

        shortcuts.assign_perm('queryobserver.view_exampleitem', auth_models.AnonymousUser(), item)

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
        # Create some items so that we get a valid query (otherwise the query would be empty as django-guardian
        # would discover that the user doesn't have permissions to get any items).
        item = models.ExampleItem()
        item.name = 'Example'
        item.enabled = False
        item.save()

        subitem = models.ExampleSubItem(parent=item, enabled=True)
        subitem.save()

        shortcuts.assign_perm('queryobserver.view_exampleitem', auth_models.AnonymousUser(), item)
        shortcuts.assign_perm('queryobserver.view_examplesubitem', auth_models.AnonymousUser(), subitem)

        observer = pool.observe_viewset(self.request(views.ExampleSubItemViewSet, parent__enabled=True), 'test-subscriber')
        items = observer.evaluate()

        self.assertEquals(observer.id, 'd23637692d98a517ccb7cbd92a6af2a187837f893aff9c2ce1ec0f0f3f2b850b')
        self.assertEquals(len(items), 0)
        self.assertIn(observer, pool._tables['queryobserver_exampleitem'])
        self.assertIn(observer, pool._tables['queryobserver_examplesubitem'])

    def test_order(self):
        observer = pool.observe_viewset(self.request(views.ExampleItemViewSet, ordering='name'), 'test-subscriber')
        items = observer.evaluate()

        self.assertEquals(len(items), 0)

        item = models.ExampleItem()
        item.name = 'D'
        item.enabled = False
        item.save()

        shortcuts.assign_perm('queryobserver.view_exampleitem', auth_models.AnonymousUser(), item)

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

        shortcuts.assign_perm('queryobserver.view_exampleitem', auth_models.AnonymousUser(), item2)

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

        shortcuts.assign_perm('queryobserver.view_exampleitem', auth_models.AnonymousUser(), item3)

        added, changed, removed = observer.evaluate(return_emitted=True)
        self.assertEquals(len(added), 1)
        self.assertEquals(added[0], {'id': item3.pk, 'name': item3.name, 'enabled': item3.enabled})
        self.assertEquals(added[0]._order, 1)
        self.assertEquals(len(changed), 1)
        self.assertEquals(changed[0], {'id': item.pk, 'name': item.name, 'enabled': item.enabled})
        self.assertEquals(changed[0]._order, 2)
        self.assertEquals(len(removed), 0)
