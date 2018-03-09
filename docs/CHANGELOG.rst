##########
Change Log
##########

All notable changes to this project are documented in this file.

==========
Unreleased
==========

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
