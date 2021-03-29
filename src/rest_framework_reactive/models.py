from django.db import models


class Observer(models.Model):
    """State of an observer."""

    id = models.CharField(primary_key=True, max_length=64)
    request = models.BinaryField()
    last_evaluation = models.DateTimeField(null=True)
    poll_interval = models.IntegerField(null=True)
    subscribers = models.ManyToManyField('Subscriber')

    def __str__(self):
        return 'id={id}'.format(id=self.id)


class Item(models.Model):
    """Item part of the observer's result set."""

    observer = models.ForeignKey(
        Observer, related_name='items', on_delete=models.CASCADE
    )
    primary_key = models.CharField(max_length=200)
    order = models.IntegerField()
    data = models.JSONField()

    class Meta:
        unique_together = (('observer', 'order'), ('observer', 'primary_key'))
        ordering = ('observer', 'order')

    def __str__(self):
        return 'primary_key={primary_key} order={order} data={data}'.format(
            primary_key=self.primary_key, order=self.order, data=repr(self.data)
        )


class Dependency(models.Model):
    """Observer's dependency."""

    observer = models.ForeignKey(
        Observer, related_name='dependencies', on_delete=models.CASCADE
    )
    table = models.CharField(max_length=100)

    class Meta:
        unique_together = ('observer', 'table')

    def __str__(self):
        return 'table={table}'.format(table=self.table)


class Subscriber(models.Model):
    """Subscriber to an observer."""

    session_id = models.CharField(primary_key=True, max_length=100)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return 'session_id={session_id}'.format(session_id=self.session_id)
