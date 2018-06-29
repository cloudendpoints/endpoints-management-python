# Copyright 2017 Google Inc. All Rights Reserved.
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

"""Provides a method for fetching Service Configuration from Google Service
Management API."""

from __future__ import absolute_import

import logging
import json
import os
import urllib3

from apitools.base.py import encoding
from ..gen import servicemanagement_v1_messages as messages
from oauth2client import client
from urllib3.contrib import appengine


logger = logging.getLogger(__name__)

_GOOGLE_API_SCOPE = u"https://www.googleapis.com/auth/cloud-platform"

_SERVICE_MGMT_URL_TEMPLATE = (u"https://servicemanagement.googleapis.com"
                              u"/v1/services/{}/configs/{}")

_SERVICE_NAME_ENV_KEY = u"ENDPOINTS_SERVICE_NAME"
_SERVICE_VERSION_ENV_KEY = u"ENDPOINTS_SERVICE_VERSION"


class ServiceConfigException(Exception):
    pass


def fetch_service_config(service_name=None, service_version=None):
    """Fetches the service config from Google Service Management API.

    Args:
      service_name: the service name. When this argument is unspecified, this
        method uses the value of the "SERVICE_NAME" environment variable as the
        service name, and raises ValueError if the environment variable is unset.
      service_version: the service version. When this argument is unspecified,
        this method uses the value of the "SERVICE_VERSION" environment variable
        as the service version, and raises ValueError if the environment variable
        is unset.

    Returns: the fetched service config JSON object.

    Raises:
      ValueError: when the service name/version is neither provided as an
        argument or set as an environment variable; or when the fetched service
        config fails validation.
      Exception: when the Google Service Management API returns non-200 response.
    """
    if not service_name:
        service_name = _get_env_var_or_raise(_SERVICE_NAME_ENV_KEY)
    if not service_version:
        service_version = _get_service_version(_SERVICE_VERSION_ENV_KEY,
                                               service_name)

    response = _make_service_config_request(service_name, service_version)
    logger.debug(u'obtained service json from the management api:\n%s', response.data)
    service = encoding.JsonToMessage(messages.Service, response.data)
    _validate_service_config(service, service_name, service_version)
    return service


def _get_access_token():
    credentials = client.GoogleCredentials.get_application_default()
    if credentials.create_scoped_required():
        credentials = credentials.create_scoped(_GOOGLE_API_SCOPE)
    return credentials.get_access_token().access_token


def _get_http_client():
    if appengine.is_appengine_sandbox():
        return appengine.AppEngineManager()
    else:
        return urllib3.PoolManager()


def _get_env_var_or_raise(env_variable_name):
    if env_variable_name not in os.environ:
        message_template = u'The "{}" environment variable is not set'
        _log_and_raise(ValueError, message_template.format(env_variable_name))
    return os.environ[env_variable_name]


def _make_service_config_request(service_name, service_version=''):
    url = _SERVICE_MGMT_URL_TEMPLATE.format(service_name,
                                            service_version).rstrip('/')

    http_client = _get_http_client()
    headers = {u"Authorization": u"Bearer {}".format(_get_access_token())}
    response = http_client.request(u"GET", url, headers=headers)

    status_code = response.status
    if status_code == 403:
        message = (u"No service '{0}' found or permission denied. If this is a new "
                   u"Endpoints service, make sure you've deployed the "
                   u"service config using gcloud.").format(service_name)
        _log_and_raise(ServiceConfigException, message)
    elif status_code == 404:
        message = (u"The service '{0}' was found, but no service config was "
                   u"found for version '{1}'.").format(service_name, service_version)
        _log_and_raise(ServiceConfigException, message)
    elif status_code != 200:
        message_template = u"Fetching service config failed (status code {})"
        _log_and_raise(ServiceConfigException, message_template.format(status_code))

    return response


def _get_service_version(env_variable_name, service_name):
    service_version = os.environ.get(env_variable_name)

    if service_version:
        return service_version

    response = _make_service_config_request(service_name)
    logger.debug(u'obtained service config list from api: \n%s', response.data)

    services = encoding.JsonToMessage(messages.ListServiceConfigsResponse,
                                      response.data)

    try:
        logger.debug(u"found latest service version of %s",
                     services.serviceConfigs[0].id)
        return services.serviceConfigs[0].id
    except:
        # catches IndexError if no versions or anything else that would
        # indicate a failed reading of the response.
        message_template = u"Couldn't retrieve service version from environment or server"
        _log_and_raise(ServiceConfigException, message_template)


def _validate_service_config(service, expected_service_name,
                             expected_service_version):
    service_name = service.name
    if not service_name:
        _log_and_raise(ValueError, u"No service name in the service config")
    if service_name != expected_service_name:
        message_template = u"Unexpected service name in service config: {}"
        _log_and_raise(ValueError, message_template.format(service_name))

    service_version = service.id
    if not service_version:
        _log_and_raise(ValueError, u"No service version in the service config")
    if service_version != expected_service_version:
        message_template = u"Unexpected service version in service config: {}"
        _log_and_raise(ValueError, message_template.format(service_version))


def _log_and_raise(exception_class, message):
    logger.error(message)
    raise exception_class(message)
