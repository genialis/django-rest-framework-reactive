##########
Change Log
##########

All notable changes to this project are documented in this file.

==========
Unreleased
==========

Fixed
-----
* Fix IntegrityError on concurrent evaluations


================
3.0.5 2018-06-12
================

Fixed
-----
* Rewrite query interceptor to properly handle multiple threads


================
3.0.4 2018-06-08
================

Added
-----
* Add ``clearobservers`` management command which clears all observer
  state from the database.

Fixed
-----
* Fix viewsets without dependencies returning no results
* Fix issues with handling observer subscribers


================
3.0.3 2018-06-08
================

Fixed
-----
* Defer ordering unique constraints when updating items
* Dispatch observer evaluations to other workers instead of processing
  everything in the same worker
* Fix issues with query interceptor in multiple threads
* Cast primary keys in ORM signals to string to avoid JSON serialization
  failures


================
3.0.2 2018-06-04
================

Fixed
-----
* Ignore own ORM updates when processing observers


================
3.0.1 2018-05-16
================

Fixed
-----
* Fix issues with handling observer subscribers


================
3.0.0 2018-05-15
================

Changed
-------
* **BACKWARD INCOMPATIBLE:** Port to Django Channels 2.1 and add support
  for running multiple workers.


================
2.0.1 2018-02-05
================

Fixed
-----
* Do not override primary key when an endpoint returns a single item and
  it already has a primary key set
* Fix Channels dependencies


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
* Dependency detection when subqueries are used
* Reactivity when M2M relationships are modified


=================
0.13.0 2017-08-24
=================

Added
-----
* Python 3 compatibility
* Improve logging for use with Sentry

Fixed
-----
* Force evaluation when full results requested

=================
0.12.0 2017-06-22
=================

Added
-----
* Logging of slow observers and automatic stopping of very slow
  observers (both are configurable)
* Status endpoint to track server status
* Configurable update batch delay
* Polling observers

Fixed
-----
* ``META`` passthrough in requests
* Correct passthrough of ``request.method``
* Improved observer concurrency

Changed
-------
* More easily support different concurrency backends


=================
0.11.0 2017-01-24
=================

Changed
-------
* Transparently support paginated viewsets
