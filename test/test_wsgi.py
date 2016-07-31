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

from __future__ import absolute_import

import mock
import os
import tempfile
import unittest2
from expects import be_false, be_none, be_true, expect, equal, raise_error

import google.apigen.servicecontrol_v1_messages as messages
from google.api.control import client, wsgi
from google.scc import service



def _dummy_start_response(content, dummy_response_headers):
    pass


_DUMMY_RESPONSE = ('All must answer "here!"',)


class _DummyWsgiApp(object):

    def __call__(self, environ, dummy_start_response):
        return _DUMMY_RESPONSE


class TestServiceLoaderMiddleware(unittest2.TestCase):

    def test_should_add_service_et_al_to_environment(self):
        cls = wsgi.ServiceLoaderMiddleware
        wrappee = _DummyWsgiApp()
        wrapped = cls(wrappee, loader=service.Loaders.SIMPLE)

        given = {
            'wsgi.url_scheme': 'http',
            'HTTP_HOST': 'localhost',
            'REQUEST_METHOD': 'GET'
        }
        wrapped(given, _dummy_start_response)
        wanted_service = service.Loaders.SIMPLE.load()
        expect(given.get(cls.SERVICE)).to(equal(wanted_service))
        expect(given.get(cls.SERVICE_NAME)).to(equal(wanted_service.name))
        expect(given.get(cls.METHOD_REGISTRY)).not_to(be_none)
        expect(given.get(cls.REPORTING_RULES)).not_to(be_none)
        expect(given.get(cls.METHOD_INFO)).not_to(be_none)


class TestMiddleware(unittest2.TestCase):
    PROJECT_ID = 'middleware'

    def test_should_not_send_requests_if_there_is_no_service(self):
        wrappee = _DummyWsgiApp()
        control_client = mock.MagicMock(spec=client.Client)

        given = {
            'wsgi.url_scheme': 'http',
            'PATH_INFO': '/any/method',
            'REMOTE_ADDR': '192.168.0.3',
            'HTTP_HOST': 'localhost',
            'HTTP_REFERER': 'example.myreferer.com',
            'REQUEST_METHOD': 'GET'
        }
        dummy_response = messages.CheckResponse(operationId='fake_operation_id')
        wrapped = wsgi.Middleware(wrappee, self.PROJECT_ID, control_client)
        wrapped(given, _dummy_start_response)
        expect(control_client.check.called).to(be_false)
        expect(control_client.report.called).to(be_false)

    def test_should_not_send_requests_is_service_loading_failed(self):
        wrappee = _DummyWsgiApp()
        control_client = mock.MagicMock(spec=client.Client)

        given = {
            'wsgi.url_scheme': 'http',
            'PATH_INFO': '/any/method',
            'REMOTE_ADDR': '192.168.0.3',
            'HTTP_HOST': 'localhost',
            'HTTP_REFERER': 'example.myreferer.com',
            'REQUEST_METHOD': 'GET'
        }
        mock_loader = mock.MagicMock(load=lambda: None)
        dummy_response = messages.CheckResponse(operationId='fake_operation_id')
        with_control = wsgi.Middleware(wrappee, self.PROJECT_ID, control_client)
        wrapped = wsgi.ServiceLoaderMiddleware(
            with_control,
            loader=mock_loader)
        control_client.check.return_value = dummy_response
        wrapped(given, _dummy_start_response)
        expect(control_client.check.called).to(be_false)
        expect(control_client.report.called).to(be_false)

    def test_should_send_requests_using_the_client(self):
        wrappee = _DummyWsgiApp()
        control_client = mock.MagicMock(spec=client.Client)

        given = {
            'wsgi.url_scheme': 'http',
            'PATH_INFO': '/any/method',
            'REMOTE_ADDR': '192.168.0.3',
            'HTTP_HOST': 'localhost',
            'HTTP_REFERER': 'example.myreferer.com',
            'REQUEST_METHOD': 'GET'
        }
        dummy_response = messages.CheckResponse(operationId='fake_operation_id')
        with_control = wsgi.Middleware(wrappee, self.PROJECT_ID, control_client)
        wrapped = wsgi.ServiceLoaderMiddleware(
            with_control,
            loader=service.Loaders.SIMPLE)
        control_client.check.return_value = dummy_response
        wrapped(given, _dummy_start_response)
        expect(control_client.check.called).to(be_true)
        expect(control_client.report.called).to(be_true)

    def test_should_not_send_report_request_if_check_fails(self):
        wrappee = _DummyWsgiApp()
        control_client = mock.MagicMock(spec=client.Client)
        given = {
            'wsgi.url_scheme': 'http',
            'PATH_INFO': '/any/method',
            'REMOTE_ADDR': '192.168.0.3',
            'HTTP_HOST': 'localhost',
            'HTTP_REFERER': 'example.myreferer.com',
            'REQUEST_METHOD': 'GET'
        }
        dummy_response = messages.CheckResponse(
            operationId = 'fake_operation_id',
            checkErrors = [
                messages.CheckError(
                    code=messages.CheckError.CodeValueValuesEnum.PROJECT_DELETED)
            ]
        )
        wrapped = wsgi.add_all(wrappee,
                               self.PROJECT_ID,
                               control_client,
                               loader=service.Loaders.SIMPLE)
        control_client.check.return_value = dummy_response
        wrapped(given, _dummy_start_response)
        expect(control_client.check.called).to(be_true)
        expect(control_client.report.called).to(be_false)


_SYSTEM_PARAMETER_CONFIG_TEST = """
{
    "name": "system-parameter-config",
    "systemParameters": {
       "rules": [{
         "selector": "Uvw.Method1",
         "parameters": [{
            "name": "name1",
            "httpHeader": "Header-Key1",
            "urlQueryParameter": "param_key1"
         }, {
            "name": "name2",
            "httpHeader": "Header-Key2",
            "urlQueryParameter": "param_key2"
         }, {
            "name": "api_key",
            "httpHeader": "ApiKeyHeader",
            "urlQueryParameter": "ApiKeyParam"
         }, {
            "httpHeader": "Ignored-NoName-Key3",
            "urlQueryParameter": "Ignored-NoName-key3"
         }]
       }, {
         "selector": "Bad.NotConfigured",
         "parameters": [{
            "name": "neverUsed",
            "httpHeader": "NeverUsed-Key1",
            "urlQueryParameter": "NeverUsed_key1"
         }]
       }]
    },
    "http": {
        "rules": [{
            "selector": "Uvw.Method1",
            "get": "/uvw/method1/*"
        }, {
            "selector": "Uvw.DefaultParameters",
            "get": "/uvw/default_parameters"
        }]
    }
}
"""

class TestMiddlewareWithParams(unittest2.TestCase):
    PROJECT_ID = 'middleware-with-params'

    def setUp(self):
        _config_fd = tempfile.NamedTemporaryFile(delete=False)
        with _config_fd as f:
            f.write(_SYSTEM_PARAMETER_CONFIG_TEST)
        self._config_file = _config_fd.name
        os.environ[service.CONFIG_VAR] = self._config_file

    def tearDown(self):
        if os.path.exists(self._config_file):
            os.remove(self._config_file)

    def test_should_send_requests_with_no_param(self):
        wrappee = _DummyWsgiApp()
        control_client = mock.MagicMock(spec=client.Client)
        given = {
            'wsgi.url_scheme': 'http',
            'PATH_INFO': '/uvw/method1/with_no_param',
            'REMOTE_ADDR': '192.168.0.3',
            'HTTP_HOST': 'localhost',
            'HTTP_REFERER': 'example.myreferer.com',
            'REQUEST_METHOD': 'GET'
        }
        dummy_response = messages.CheckResponse(operationId='fake_operation_id')
        wrapped = wsgi.add_all(wrappee,
                               self.PROJECT_ID,
                               control_client,
                               loader=service.Loaders.ENVIRONMENT)
        control_client.check.return_value = dummy_response
        wrapped(given, _dummy_start_response)
        expect(control_client.check.called).to(be_true)
        req = control_client.check.call_args[0][0]
        expect(req.checkRequest.operation.consumerId).to(
            equal('project:middleware-with-params'))
        expect(control_client.report.called).to(be_true)

    def test_should_send_requests_with_api_key_param(self):
        wrappee = _DummyWsgiApp()
        control_client = mock.MagicMock(spec=client.Client)
        given = {
            'wsgi.url_scheme': 'http',
            'QUERY_STRING': 'ApiKeyParam=my-query-value',
            'PATH_INFO': '/uvw/method1/with_query_param',
            'REMOTE_ADDR': '192.168.0.3',
            'HTTP_HOST': 'localhost',
            'HTTP_REFERER': 'example.myreferer.com',
            'REQUEST_METHOD': 'GET'
        }
        dummy_response = messages.CheckResponse(operationId='fake_operation_id')
        wrapped = wsgi.add_all(wrappee,
                               self.PROJECT_ID,
                               control_client,
                               loader=service.Loaders.ENVIRONMENT)
        control_client.check.return_value = dummy_response
        wrapped(given, _dummy_start_response)
        expect(control_client.check.called).to(be_true)
        req = control_client.check.call_args[0][0]
        expect(req.checkRequest.operation.consumerId).to(
            equal('api_key:my-query-value'))
        expect(control_client.report.called).to(be_true)

    def test_should_send_requests_with_header_param(self):
        wrappee = _DummyWsgiApp()
        control_client = mock.MagicMock(spec=client.Client)
        given = {
            'wsgi.url_scheme': 'http',
            'PATH_INFO': '/uvw/method1/with_query_param',
            'REMOTE_ADDR': '192.168.0.3',
            'HTTP_HOST': 'localhost',
            'HTTP_APIKEYHEADER': 'my-header-value',
            'HTTP_REFERER': 'example.myreferer.com',
            'REQUEST_METHOD': 'GET'
        }
        dummy_response = messages.CheckResponse(operationId='fake_operation_id')
        wrapped = wsgi.add_all(wrappee,
                               self.PROJECT_ID,
                               control_client,
                               loader=service.Loaders.ENVIRONMENT)
        control_client.check.return_value = dummy_response
        wrapped(given, _dummy_start_response)
        expect(control_client.check.called).to(be_true)
        check_request = control_client.check.call_args_list[0].checkRequest
        req = control_client.check.call_args[0][0]
        expect(req.checkRequest.operation.consumerId).to(
            equal('api_key:my-header-value'))
        expect(control_client.report.called).to(be_true)
