class QueryObserverException(Exception):
    pass


class ViewSetAlreadyRegistered(QueryObserverException):
    pass


class ViewSetNotRegistered(QueryObserverException):
    pass


class ObserverStopped(QueryObserverException):
    pass
