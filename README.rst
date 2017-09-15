Google Endpoints API Management
===============================


.. image:: https://travis-ci.org/cloudendpoints/endpoints-management-python.svg?branch=master
    :target: https://travis-ci.org/cloudendpoints/endpoints-management-python
.. image:: https://codecov.io/gh/cloudendpoints/endpoints-management-python/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/cloudendpoints/endpoints-management-python


Google Endpoints API Management manages the 'control plane' of an API by
providing support for authentication, billing, monitoring and quota control.

It achieves this by

- allowing HTTP servers to control access to their APIs using the Google Service Management and Google Service Control APIs
- providing built-in, standards-compliant support for third-party authentication
- doing this with minimal performance impact via the use of advanced caching and aggregation algorithms
- making this easy to integrate via a set of `WSGI`_ middleware

.. _`WSGI`: https://wsgi.readthedocs.io/en/latest/


Example:

  .. code:: python

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
   >>> from endpoints_management.control import client, wsgi
   >>> control_client = client.Loaders.DEFAULT.load(service_name)
   >>> control_client.start()
   >>> controlled_app = wsgi.add_all(application, project_id, control_client)
   >>>
   >>> # now use the controlled in place of application
   >>> my_server.serve(controlled_app)


Installation
-------------

Install using `pip`_

  .. code:: bash

     [sudo] pip install google-endpoints-api-management

.. _`pip`: https://pip.pypa.io


Python Versions
---------------

endpoints-management-python is currently tested with Python 2.7 and Python 3.6.


Contributing
------------

Contributions to this library are always welcome and highly encouraged.

See the `CONTRIBUTING documentation`_ for more information on how to get started.

.. _`CONTRIBUTING documentation`: https://github.com/cloudendpoints/endpoints-management-python/blob/master/CONTRIBUTING.rst


Versioning
----------

This library follows `Semantic Versioning`_

.. _`Semantic Versioning`: http://semver.org/


Details
-------

For detailed documentation of the modules in endpoints-management-python, please watch `DOCUMENTATION`_.

.. _`DOCUMENTATION`: https://endpoints-management-python.readthedocs.org/


License
-------

Apache - See `the full LICENSE`_ for more information.

.. _`the full LICENSE`: https://github.com/cloudendpoints/endpoints-management-python/blob/master/LICENSE
