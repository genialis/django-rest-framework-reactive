

class QueryObserverException(Exception):
    pass


class SerializerAlreadyRegistered(QueryObserverException):
    pass


class SerializerNotRegistered(QueryObserverException):
    pass


class ObserverStopped(QueryObserverException):
    pass
