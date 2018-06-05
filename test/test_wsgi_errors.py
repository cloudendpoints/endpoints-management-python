# Copyright 2018 Google Inc. All Rights Reserved.
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

"""Test WSGI responses when check/quota errors occur."""

import mock
import pytest
import webtest
from webtest.debugapp import debug_app as DEBUG_APP

from apitools.base.py import encoding
from endpoints_management.control import (
    client, quota_request, sc_messages, sm_messages, wsgi,
)
from .test_wsgi import _SYSTEM_PARAMETER_CONFIG_TEST


@pytest.fixture(scope='module')
def project_id():
    return 'middleware-errors'


@pytest.fixture()
def control_client():
    return mock.MagicMock(spec=client.Client)


@pytest.fixture()
def service_config_loader():
    service = encoding.JsonToMessage(sm_messages.Service, _SYSTEM_PARAMETER_CONFIG_TEST)
    loader = mock.Mock()
    loader.load.return_value = service
    return loader


@pytest.fixture()
def wrapped_app(project_id, control_client, service_config_loader):
    return wsgi.add_all(DEBUG_APP, project_id, control_client, loader=service_config_loader)


@pytest.fixture()
def test_app(wrapped_app):
    return webtest.TestApp(wrapped_app, lint=False)


def test_handle_missing_api_key(control_client, test_app):
    url = '/uvw/method_needs_api_key/more_stuff'
    check_resp = sc_messages.CheckResponse(
        operationId=u'fake_operation_id')
    control_client.check.return_value = check_resp
    resp = test_app.get(url, expect_errors=True)
    assert resp.status_code == 401
    assert resp.content_type == 'application/json'
    assert wsgi.Middleware._NO_API_KEY_MSG in resp.json['message']


def test_handle_out_of_quota(control_client, test_app):
    quota_resp = sc_messages.AllocateQuotaResponse(
        allocateErrors = [
            sc_messages.QuotaError(
                code=quota_request._QuotaErrors.RESOURCE_EXHAUSTED,
                description=u'details')
        ]
    )
    check_resp = sc_messages.CheckResponse(
        operationId=u'fake_operation_id')
    control_client.check.return_value = check_resp
    control_client.allocate_quota.return_value = quota_resp
    url = '/uvw/method2/with_no_param'
    resp = test_app.get(url, expect_errors=True)
    expected_status, expected_detail = quota_request._QUOTA_ERROR_CONVERSION[
        quota_request._QuotaErrors.RESOURCE_EXHAUSTED]
    assert resp.status_code == expected_status
    assert resp.content_type == 'application/json'
    assert expected_detail in resp.json['message']
