# Copyright 2016, Google Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

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
import wsgiref

from . import service
from .aggregators import check_request, report_request


logger = logging.getLogger(__name__)


_CONTENT_LENGTH = 'content-length'


def _next_operation_uuid():
    return uuid.uuid4().hex


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
      >>> wrapped_app = wsgi.Middleware(
      ...    app, scc_client, project_id, service.Loaders.ENVIRONMENT)
      >>>
      >>> # now use wrapped_app in place of app

    """
    # pylint: disable=too-many-arguments,too-many-instance-attributes
    # pylint: disable=too-few-public-methods, fixme
    NO_SERVICE_ERROR = 'could not obtain a service; will disable service control'
    DISABLED_SERVICE = 'DISABLED'

    def __init__(self,
                 application,
                 project_id,
                 scc_client,
                 fail_fast=False,
                 loader=service.Loaders.SIMPLE,
                 next_operation_id=_next_operation_uuid,
                 timer=datetime.now):
        """Initializes a new Middleware instance.

        Args:
           application: the wrapped wsgi application
           scc_client: the service control client instance
           project_id: the project_id thats providing service control support
           fail_fast (bool): determines whether to disable or continue if
               no service was loaded
           loader (:class:`google.scc.service.Loader`): loads the service
              instance that configures this instance's behaviour
           next_operation_id (func): produces the next operation
           timer (func[[datetime.datetime]]): a func that obtains the current time
           """
        self._application = application
        self._disabled = False
        self._project_id = project_id
        self._next_operation_id = next_operation_id
        self._scc_client = scc_client
        self._timer = timer
        s, method_registry, reporting_rules = self._configure(loader, fail_fast)
        self._service = s
        self._method_registry = method_registry
        self._reporting_rules = reporting_rules

    def _configure(self, loader, fail_fast):
        s = loader.load()
        if not s:
            if fail_fast:
                raise RuntimeError('the service config was not loaded successfully')
            else:
                logger.error('did not obtain a service instance, disabling service control')
                self._disabled = True
                return None, None, None

        registry = service.MethodRegistry(s)
        logs, metric_names, label_names = service.extract_report_spec(s)
        reporting_rules = report_request.ReportingRules.from_known_inputs(
            logs=logs,
            metric_names=metric_names,
            label_names=label_names)

        return s, registry, reporting_rules

    @property
    def service_name(self):
        if not self._service:
            return self.DISABLED_SERVICE
        else:
            return self._service.name

    def __call__(self, environ, start_response):
        if self._disabled:
            # just allow the wrapped application to handle the request
            return self._application(environ, start_response)
        latency_timer = _LatencyTimer(self._timer)

        latency_timer.start()
        parsed_uri = urlparse.urlparse(wsgiref.util.request_uri(environ))
        http_method = environ.get('REQUEST_METHOD')

        # Determine if this request should be handled
        method_info = self._method_registry.lookup(http_method, parsed_uri.path)
        if not method_info:
            # just allow the wrapped application to handle the request
            return self._application(environ, start_response)

        # Determine if the request can proceed
        check_info = self._create_check_info(method_info, parsed_uri, environ)
        check_req = check_info.as_check_request()
        logger.debug('checking with %s', check_request)
        check_resp = self._scc_client.check(check_req)
        error_msg = self._handle_check_response(check_req, check_resp, start_response)
        if error_msg:
            return error_msg

        # update the client with the response
        logger.debug('adding check response %s', check_resp)
        self._scc_client.add_check_response(check_req, check_resp)
        latency_timer.app_start()

        app_info = _AppInfo()
        # TODO: determine if any of the more complex ways of getting the request size
        # (e.g) buffering and counting the wsgi input stream is more appropriate here
        app_info.request_size = environ.get('CONTENT_LENGTH', 0)
        app_info.http_method = http_method

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
            app_info.response_size = len(b''.join(result))
        report_req = self._create_report_request(method_info,
                                                 check_info,
                                                 app_info,
                                                 latency_timer)
        logger.debug('sending report_request %s', report_req)
        self._scc_client.report(report_req)
        return result

    def _create_report_request(self,
                               method_info,
                               check_info,
                               app_info,
                               latency_timer):
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
            url=check_info.url
        )
        return report_info.as_report_request(self._reporting_rules, timer=self._timer)

    def _create_check_info(self, method_info, parsed_uri, environ):
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
            service_name=self.service_name
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
        return self._end - self.start

    @property
    def overhead_time(self):
        if not self._start:
            return None
        if not self._app_start:
            return None
        return self._app_start - self.start


def _find_api_key_param(info, parsed_uri):
    params = info.api_key_url_query_params()
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
    headers = info.api_key_http_headers()
    if not headers:
        return None

    for h in headers:
        value = environ.get('HTTP_' + h.upper())
        if value:
            return value

    return None
