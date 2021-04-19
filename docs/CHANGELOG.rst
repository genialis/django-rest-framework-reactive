##########
Change Log
##########

All notable changes to this project are documented in this file.


================
6.0.0 2021-04-19
================

Changed
-------
- **BACKWARD INCOMPATIBLE:** Require ``Django`` 3.x
- **BACKWARD INCOMPATIBLE:** Require ``Django Channels`` version 3.0.x
- Bump ``Django REST framework`` requirement to version ``3.12``

Added
-----
- Add support for Python 3.9
- Use Github Actions to run the tests


================
5.1.0 2020-02-13
================

Added
-----
- Add support for Python 3.8


================
5.0.1 2019-06-26
================

Fixed
-----
- Pass dependencies and other arguments to list decorator when decorating class


================
5.0.0 2019-05-06
================

Changed
-------
- **BACKWARD INCOMPATIBLE:** Bump ``Django`` requirement to version ``2.2``
- **BACKWARD INCOMPATIBLE:** Bump ``Django REST framework`` requirement to
  version ``3.9``

Added
-----
- Support Python 3.7


================
4.2.1 2019-05-06
================

Fixed
-----
- Pin ``django-priority-batch`` to version ``1.1`` to fix compatibility issues


================
4.2.0 2019-04-15
================

Changed
-------
- Bump ``channels`` requirement to version 2.2


================
4.1.0 2019-03-28
================

Changed
-------
- Use ``django-filter`` instead of ``djangorestframework-filters``
- Bump ``django-filter`` requirement to version 2.0

Fixed
-----
- Wrap ``observable`` decorator with ``functools.wraps`` to preserve metadata


================
4.0.0 2019-03-19
================

Changed
-------
- **BACKWARD INCOMPATIBLE:** Protocol has changed, including the names of
  Channels workers.
- **BACKWARD INCOMPATIBLE:** Observe changes in the queryset model only (by
  default). Other tables can be tracked by explicitly listing the dependencies
  in @observable decorator.
- **BACKWARD INCOMPATIBLE:** Ensure observers exist when subscribing. Subscribe
  (and observer creation) was separated from the evaluation step. Subscribe
  includes subscriber and observer creation if needed, and executes in single
  query. Observer instances are not removed from database anymore. Observers
  without subscribers are skipped to optimize performance. Observers and
  subscribers can be deleted using ``clearobservers`` Django command.
- **BACKWARD INCOMPATIBLE:** Overhaul Python source distribution (sdist)
- Support PostgreSQL 10

Added
-----
- Observers with the same ID are throttled. The default throttle rate is 2
  seconds.


================
3.1.0 2018-10-19
================

Added
-----
- Optionally batch observer notifications


================
3.0.9 2018-09-07
================

Fixed
-----
- Retry taking the observer lock before evaluation on IntegrityError due
  to concurrent observer creation


================
3.0.8 2018-07-10
================

Fixed
-----
- Do not mutate received update message in client consumer
- Use a bounded cache with LRU eviction policy for executors


================
3.0.7 2018-06-19
================

Fixed
-----
- Do not generate notification messages when there are no updates


================
3.0.6 2018-06-15
================

Fixed
-----
- Fix IntegrityError on concurrent evaluations


================
3.0.5 2018-06-12
================

Fixed
-----
- Rewrite query interceptor to properly handle multiple threads


================
3.0.4 2018-06-08
================

Added
-----
- Add ``clearobservers`` management command which clears all observer
  state from the database.

Fixed
-----
- Fix viewsets without dependencies returning no results
- Fix issues with handling observer subscribers


================
3.0.3 2018-06-08
================

Fixed
-----
- Defer ordering unique constraints when updating items
- Dispatch observer evaluations to other workers instead of processing
  everything in the same worker
- Fix issues with query interceptor in multiple threads
- Cast primary keys in ORM signals to string to avoid JSON serialization
  failures


================
3.0.2 2018-06-04
================

Fixed
-----
- Ignore own ORM updates when processing observers


================
3.0.1 2018-05-16
================

Fixed
-----
- Fix issues with handling observer subscribers


================
3.0.0 2018-05-15
================

Changed
-------
- **BACKWARD INCOMPATIBLE:** Port to Django Channels 2.1 and add support
  for running multiple workers.


================
2.0.1 2018-02-05
================

Fixed
-----
- Do not override primary key when an endpoint returns a single item and
  it already has a primary key set
- Fix Channels dependencies


================
2.0.0 2017-11-24
================

Changed
-------
- **BACKWARD INCOMPATIBLE:** Use Django Channels for WebSockets


================
1.0.0 2017-10-26
================

Changed
-------
- **BACKWARD INCOMPATIBLE:** Bump Django requirement to version 1.11.x

Fixed
-----
- Dependency detection when subqueries are used
- Reactivity when M2M relationships are modified


=================
0.13.0 2017-08-24
=================

Added
-----
- Python 3 compatibility
- Improve logging for use with Sentry

Fixed
-----
- Force evaluation when full results requested

=================
0.12.0 2017-06-22
=================

Added
-----
- Logging of slow observers and automatic stopping of very slow
  observers (both are configurable)
- Status endpoint to track server status
- Configurable update batch delay
- Polling observers

Fixed
-----
- ``META`` passthrough in requests
- Correct passthrough of ``request.method``
- Improved observer concurrency

Changed
-------
- More easily support different concurrency backends


=================
0.11.0 2017-01-24
=================

Changed
-------
- Transparently support paginated viewsets
