# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""wsgi implement behaviour that provides service control as wsgi
middleware.

It provides the :class:`Middleware`, which is a WSGI middleware implementation
that wraps another WSGI application to uses a provided
:class:`google.scc.client.Client` to provide service control.

"""

from __future__ import absolute_import

from datetime import datetime
import httplib
import logging
import uuid
import urlparse
import wsgiref.util

from . import service
from .aggregators import check_request, report_request


logger = logging.getLogger(__name__)


_CONTENT_LENGTH = 'content-length'


def add_all(app, project_id, scc_client,
            loader=service.Loaders.FROM_SERVICE_MANAGEMENT):
    """Adds all endpoints middleware to a wsgi application.

    Sets up app to use all default endpoints middleware.

    Example:

      >>> app = MyWsgiApp()  # an existing WSGI application
      >>>
      >>> # the name of the controlled service
      >>> service_name = 'my-service-name'
      >>>
      >>> # A GCP project  with service control enabled
      >>> project_id = 'my-project-id'
      >>>
      >>> # wrap the app for service control
      >>> from google.scc import wsgi
      >>> scc_client = client.Loaders.DEFAULT.load(service_name)
      >>> scc_client.start()
      >>> wrapped_app = add_all(app, project_id, scc_client)
      >>>
      >>> # now use wrapped_app in place of app

    Args:
       application: the wrapped wsgi application
       project_id: the project_id thats providing service control support
       scc_client: the service control client instance
       loader (:class:`google.scc.service.Loader`): loads the service
          instance that configures this instance's behaviour
    """
    with_control = Middleware(app, scc_client, project_id)
    # TODO add the auth filter here
    return ServiceLoaderMiddleware(with_control, loader=loader)


def _next_operation_uuid():
    return uuid.uuid4().hex


class ServiceLoaderMiddleware(object):
    """A WSGI middleware implementation that loads a service and ensures
    it and related variables are in the environment

    If is service it attempts to add the following vars:

    - google.api.config.service
    - google.api.config.service_name
    - google.api.config.method_registry
    - google.api.config.reporting_rules
    - google.api.config.method_info
    """

    SERVICE = 'google.api.config.service'
    SERVICE_NAME = 'google.api.config.service_name'
    METHOD_REGISTRY = 'google.api.config.method_registry'
    METHOD_INFO = 'google.api.config.method_info'
    REPORTING_RULES = 'google.api.config.reporting_rules'

    def __init__(self, application,
                 loader=service.Loaders.FROM_SERVICE_MANAGEMENT):
        """Initializes a new Middleware instance.

        Args:
           application: the wrapped wsgi application
           loader (:class:`google.scc.service.Loader`): loads the service
              instance that configures this instance's behaviour
           """
        self._application = application
        s, method_registry, reporting_rules = self._configure(loader)
        self._service = s
        self._method_registry = method_registry
        self._reporting_rules = reporting_rules

    def _configure(self, loader):
        s = loader.load()
        if not s:
            logger.error('did not obtain a service instance, '
                         'dependent middleware will be disabled')
            return None, None, None

        registry = service.MethodRegistry(s)
        logs, metric_names, label_names = service.extract_report_spec(s)
        reporting_rules = report_request.ReportingRules.from_known_inputs(
            logs=logs,
            metric_names=metric_names,
            label_names=label_names)

        return s, registry, reporting_rules

    def __call__(self, environ, start_response):
        if self._service:  # service-related vars to the environment
            environ[self.SERVICE] = self._service
            environ[self.SERVICE_NAME] = self._service.name
            environ[self.METHOD_REGISTRY] = self._method_registry
            environ[self.REPORTING_RULES] = self._reporting_rules
            parsed_uri = urlparse.urlparse(wsgiref.util.request_uri(environ))
            http_method = environ.get('REQUEST_METHOD')
            method_info = self._method_registry.lookup(http_method, parsed_uri.path)
            if method_info:
                environ[self.METHOD_INFO] = method_info

        return self._application(environ, start_response)


class Middleware(object):
    """A WSGI middleware implementation that provides service control.

    Example:

      >>> app = MyWsgiApp()  # an existing WSGI application
      >>>
      >>> # the name of the controlled service
      >>> service_name = 'my-service-name'
      >>>
      >>> # A GCP project  with service control enabled
      >>> project_id = 'my-project-id'
      >>>
      >>> # wrap the app for service control
      >>> from google.scc import client, wsgi, service
      >>> scc_client = client.Loaders.DEFAULT.load(service_name)
      >>> scc_client.start()
      >>> wrapped_app = wsgi.Middleware(app, scc_client, project_id)
      >>> serviced_app = wsgi.ServiceLoaderMiddleware(wrapped,app)
      >>>
      >>> # now use serviced_app in place of app

    """
    # pylint: disable=too-few-public-methods, fixme

    def __init__(self,
                 application,
                 project_id,
                 scc_client,
                 next_operation_id=_next_operation_uuid,
                 timer=datetime.utcnow):
        """Initializes a new Middleware instance.

        Args:
           application: the wrapped wsgi application
           project_id: the project_id thats providing service control support
           scc_client: the service control client instance
           next_operation_id (func): produces the next operation
           timer (func[[datetime.datetime]]): a func that obtains the current time
           """
        self._application = application
        self._project_id = project_id
        self._next_operation_id = next_operation_id
        self._scc_client = scc_client
        self._timer = timer

    def __call__(self, environ, start_response):
        method_info = environ.get(ServiceLoaderMiddleware.METHOD_INFO)
        if not method_info:
            # just allow the wrapped application to handle the request
            logger.debug('method_info not present in the wsgi environment'
                         ', no service control')
            return self._application(environ, start_response)

        latency_timer = _LatencyTimer(self._timer)
        latency_timer.start()

        # Determine if the request can proceed
        http_method = environ.get('REQUEST_METHOD')
        parsed_uri = urlparse.urlparse(wsgiref.util.request_uri(environ))
        check_info = self._create_check_info(method_info, parsed_uri, environ)
        check_req = check_info.as_check_request()
        logger.debug('checking %s with %s', method_info, check_request)
        check_resp = self._scc_client.check(check_req)
        error_msg = self._handle_check_response(check_req, check_resp, start_response)
        if error_msg:
            return error_msg

        # update the client with the response
        logger.debug('adding a check response %s', check_resp)
        self._scc_client.add_check_response(check_req, check_resp)
        latency_timer.app_start()

        app_info = _AppInfo()
        # TODO: determine if any of the more complex ways of getting the request size
        # (e.g) buffering and counting the wsgi input stream is more appropriate here
        app_info.request_size = environ.get('CONTENT_LENGTH', 0)
        app_info.http_method = http_method
        app_info.url = parsed_uri

        # run the application request in an inner handler that sets the status
        # and response code on app_info
        def inner_start_response(status, response_headers, exc_info=None):
            app_info.response_code = int(status.partition(' ')[0])
            for name, value in response_headers:
                if name.lower() == _CONTENT_LENGTH:
                    app_info.response_size = int(value)
                    break
            return start_response(status, response_headers, exc_info)

        result = self._application(environ, inner_start_response)

        # perform reporting
        latency_timer.end()
        if not app_info.response_size:
            result = b''.join(result)
            app_info.response_size = len(result)
        rules = environ.get(ServiceLoaderMiddleware.REPORTING_RULES)
        report_req = self._create_report_request(method_info,
                                                 check_info,
                                                 app_info,
                                                 latency_timer,
                                                 rules)
        logger.debug('sending report_request %s', report_req)
        self._scc_client.report(report_req)
        return result

    def _create_report_request(self,
                               method_info,
                               check_info,
                               app_info,
                               latency_timer,
                               reporting_rules):
        report_info = report_request.Info(
            api_key=check_info.api_key,
            api_method=method_info.selector,
            consumer_project_id=self._project_id,  # TODO: switch this to producer_project_id
            location='',  # TODO: work out how to fill in location on all platforms
            method=app_info.http_method,
            operation_id=check_info.operation_id,
            operation_name=check_info.operation_name,
            overhead_time=latency_timer.overhead_time,
            platform=report_request.ReportedPlatforms.GAE,  # TODO: fill this in correctly
            producer_project_id=self._project_id,
            protocol=report_request.ReportedProtocols.HTTP,
            request_size=app_info.request_size,
            request_time=latency_timer.request_time,
            response_code=app_info.response_code,
            response_size=app_info.response_size,
            referer=check_info.referer,
            service_name=check_info.service_name,
            url=app_info.url
        )
        return report_info.as_report_request(reporting_rules, timer=self._timer)

    def _create_check_info(self, method_info, parsed_uri, environ):
        service_name = environ.get(ServiceLoaderMiddleware.SERVICE_NAME)
        operation_id = self._next_operation_id()
        api_key = _find_api_key_param(method_info, parsed_uri)
        if not api_key:
            api_key = _find_api_key_header(method_info, environ)

        check_info = check_request.Info(
            api_key=api_key,
            client_ip=environ.get('REMOTE_ADDR', ''),
            consumer_project_id=self._project_id,  # TODO: switch this to producer_project_id
            operation_id=operation_id,
            operation_name=method_info.selector,
            referer=environ.get('HTTP_REFERER', ''),
            service_name=service_name
        )
        return check_info

    def _handle_check_response(self, check_req, check_resp, start_response):
        # TODO: cache the bad_api_key error
        code, detail, dummy_bad_api_key = check_request.convert_response(
            check_resp, self._project_id)
        if code == httplib.OK:
            return None  # the check was OK

        # there was problem; the request cannot proceed
        self._scc_client.add_check_response(check_req, check_resp)
        logger.warn('Check failed %d, %s', code, detail)
        error_msg = '%d %s' % (code, detail)
        start_response(error_msg, [])
        return error_msg  # the request cannot continue


class _AppInfo(object):
    # pylint: disable=too-few-public-methods

    def __init__(self):
        self.response_code = httplib.INTERNAL_SERVER_ERROR
        self.response_size = 0
        self.request_size = 0
        self.http_method = None
        self.url = None


class _LatencyTimer(object):

    def __init__(self, timer):
        self._timer = timer
        self._start = None
        self._app_start = None
        self._end = None

    def start(self):
        self._start = self._timer()

    def app_start(self):
        self._app_start = self._timer()

    def end(self):
        self._end = self._timer()

    @property
    def request_time(self):
        if not self._start:
            return None
        if not self._end:
            return None
        return self._end - self._start

    @property
    def overhead_time(self):
        if not self._start:
            return None
        if not self._app_start:
            return None
        return self._app_start - self._start


def _find_api_key_param(info, parsed_uri):
    params = info.api_key_url_query_params
    if not params:
        return None

    param_dict = urlparse.parse_qs(parsed_uri.query)
    if not param_dict:
        return None

    for q in params:
        value = param_dict.get(q)
        if value:
            return value

    return None


def _find_api_key_header(info, environ):
    headers = info.api_key_http_header
    if not headers:
        return None

    for h in headers:
        value = environ.get('HTTP_' + h.upper())
        if value:
            return value

    return None
