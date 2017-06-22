##########
Change Log
##########

All notable changes to this project are documented in this file.


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
