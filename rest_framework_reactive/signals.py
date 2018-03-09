from django import dispatch
from django.db import transaction
from django.db.models import signals as model_signals

from asgiref.sync import async_to_sync
from channels.exceptions import ChannelFull
from channels.layers import get_channel_layer

from .models import Observer, Subscriber
from .protocol import *


def notify_observers(table, kind, primary_key=None):
    """Transmit ORM table change notifcation.

    :param table: Name of the table that has changed
    :param kind: Change type
    :param primary_key: Primary key of the affected instance
    """

    try:
        async_to_sync(get_channel_layer().send)(
            CHANNEL_WORKER_NOTIFY,
            {
                'type': TYPE_ORM_NOTIFY_TABLE,
                'table': table,
                'kind': kind,
                'primary_key': primary_key,
            }
        )
    except ChannelFull:
        pass


@dispatch.receiver(model_signals.post_save)
def model_post_save(sender, instance, created=False, **kwargs):
    """Signal emitted after any model is saved via Django ORM.

    :param sender: Model class that was saved
    :param instance: The actual instance that was saved
    :param created: True if a new row was created
    """

    def notify():
        table = sender._meta.db_table
        if created:
            notify_observers(table, ORM_NOTIFY_KIND_CREATE, instance.pk)
        else:
            notify_observers(table, ORM_NOTIFY_KIND_UPDATE, instance.pk)

    transaction.on_commit(notify)


@dispatch.receiver(model_signals.post_delete)
def model_post_delete(sender, instance, **kwargs):
    """Signal emitted after any model is deleted via Django ORM.

    :param sender: Model class that was deleted
    :param instance: The actual instance that was removed
    """

    def notify():
        table = sender._meta.db_table
        notify_observers(table, ORM_NOTIFY_KIND_DELETE, instance.pk)

    transaction.on_commit(notify)


@dispatch.receiver(model_signals.m2m_changed)
def model_m2m_changed(sender, instance, action, **kwargs):
    """
    Signal emitted after any M2M relation changes via Django ORM.

    :param sender: M2M intermediate model
    :param instance: The actual instance that was saved
    :param action: M2M action
    """

    def notify():
        table = sender._meta.db_table
        if action == 'post_add':
            notify_observers(table, ORM_NOTIFY_KIND_CREATE)
        elif action in ('post_remove', 'post_clear'):
            notify_observers(table, ORM_NOTIFY_KIND_DELETE)

    transaction.on_commit(notify)


@dispatch.receiver(model_signals.post_delete, sender=Subscriber)
def subscriber_removed(sender, instance, **kwargs):
    """Remove observer if all subscribers removed.

    Ensure that when all subscribers are removed from an observer, the
    observer itself is also removed.

    """
    Observer.objects.filter(subscribers=None).delete()
