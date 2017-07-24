from __future__ import absolute_import, division, print_function, unicode_literals


class QueryObserverException(Exception):
    pass


class ViewSetAlreadyRegistered(QueryObserverException):
    pass


class ViewSetNotRegistered(QueryObserverException):
    pass


class ObserverStopped(QueryObserverException):
    pass


class MissingPrimaryKey(QueryObserverException):
    pass
