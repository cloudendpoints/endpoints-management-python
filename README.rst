Google Endpoints API Management
===============================

Google Endpoints API Management manages the 'control plane' of an API by
providing support for authentication, billing, monitoring and quota control.

It achieves this by

- allowing HTTP servers to control access to their APIs using the
Google Service Management and Google Service Control APIs.
- providing built-in, standards-compliant support for third-party authentication
- doing this with minimal performance impact via the use of advanced
  caching and aggregation algorithms.
- making this easy to integrate via a set of WSGI middleware


Example:

   >>> application = MyWsgiApp()  # an existing WSGI application
   >>>
   >>> # the name of the controlled service
   >>> service_name = 'my-service-name'
   >>>
   >>> # The Id of a Google Cloud project with the Service Control and Service Management
   >>> # APIs enabled
   >>> project_id = 'my-project-id'
   >>>
   >>> # wrap the app for service control
   >>> from google.api.control import client, wsgi
   >>> control_client = client.Loaders.DEFAULT.load(service_name)
   >>> control_client.start()
   >>> controlled_app = wsgi.add_all(application, project_id, control_client)
   >>>
   >>> # now use the controlled in place of application
   >>> my_server.serve(controlled_app)


Installation
-------------

Install using pip

  ::
     [sudo] pip install google-endpoints-api-management


Python Versions
---------------

google-endpoints-api-management is currently tested with Python 2.7.


Contributing
------------

Contributions to this library are always welcome and highly encouraged.

See the `CONTRIBUTING`_ documentation for more information on how to get started.


Versioning
----------

This library follows `Semantic Versioning`_

It is currently in major version zero (``0.y.z``), which means that anything may
change at any time and the public API should not be considered stable.


Details
-------

For detailed documentation of the modules in google-endpoints-api-management, please watch `DOCUMENTATION`_.


License
-------

Apache - See `LICENSE`_ for more information.

.. _`CONTRIBUTING`: https://github.com/googleapis/google-endpoints-api-management/blob/master/CONTRIBUTING.rst
.. _`LICENSE`: https://github.com/googleapis/google-endpoints-api-management/blob/master/LICENSE
.. _`Install virtualenv`: http://docs.python-guide.org/en/latest/dev/virtualenvs/
.. _`pip`: https://pip.pypa.io
.. _`Semantic Versioning`: http://semver.org/
.. _`DOCUMENTATION`: https://google-endpoints-api-management.readthedocs.org/
